from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, Field

from .a2a import ArtifactRef, new_id


class ArtifactRecord(BaseModel):
    artifact_id: str = Field(default_factory=new_id)
    path: str
    stage: str
    producer: str
    checksum: str
    size_bytes: int
    version: int = 1
    summary: str | None = None

    def to_ref(self) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=self.artifact_id,
            path=self.path,
            stage=self.stage,
            producer=self.producer,
            checksum=self.checksum,
            size_bytes=self.size_bytes,
            summary=self.summary,
            version=self.version,
        )


@dataclass(slots=True)
class FileFingerprint:
    checksum: str
    size_bytes: int


class ArtifactRegistry:
    def __init__(self, workspace_root: Path, manifest_path: str = ".mas/artifacts.json") -> None:
        self.workspace_root = workspace_root.resolve()
        self.manifest_path = self.workspace_root / manifest_path
        self.records: list[ArtifactRecord] = []
        self._versions: dict[str, int] = {}
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def snapshot(self) -> dict[str, FileFingerprint]:
        snapshot: dict[str, FileFingerprint] = {}
        for candidate in sorted(self.workspace_root.rglob("*")):
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(self.workspace_root)
            if self._is_ignored(relative):
                continue
            snapshot[relative.as_posix()] = FileFingerprint(
                checksum=self._checksum(candidate),
                size_bytes=candidate.stat().st_size,
            )
        return snapshot

    def collect_stage_artifacts(
        self,
        *,
        before: dict[str, FileFingerprint],
        stage: str,
        producer: str,
    ) -> list[ArtifactRecord]:
        after = self.snapshot()
        changed_paths = [
            path
            for path, fingerprint in after.items()
            if path not in before or before[path] != fingerprint
        ]

        stage_records: list[ArtifactRecord] = []
        for path in changed_paths:
            fingerprint = after[path]
            version = self._versions.get(path, 0) + 1
            self._versions[path] = version
            record = ArtifactRecord(
                path=path,
                stage=stage,
                producer=producer,
                checksum=fingerprint.checksum,
                size_bytes=fingerprint.size_bytes,
                version=version,
                summary=self._summarize_path(path),
            )
            self.records.append(record)
            stage_records.append(record)

        self.write_manifest()
        return stage_records

    def write_manifest(self) -> None:
        payload = {
            "artifact_count": len(self.records),
            "artifacts": [record.model_dump(mode="json") for record in self.records],
        }
        self.manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def refs(records: list[ArtifactRecord]) -> list[ArtifactRef]:
        return [record.to_ref() for record in records]

    @staticmethod
    def _summarize_path(path: str) -> str:
        if path.endswith(".md"):
            return "Documentation artifact"
        if path.endswith(".py"):
            return "Python source artifact"
        if path.endswith(".json"):
            return "Structured metadata artifact"
        return "Workspace artifact"

    @staticmethod
    def _checksum(path: Path) -> str:
        return sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _is_ignored(relative: Path) -> bool:
        ignored_roots = {".git", ".venv", "__pycache__"}
        if not relative.parts:
            return False
        if relative.parts[0] in ignored_roots:
            return True
        return relative.as_posix() == ".mas/artifacts.json"
