from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SweBenchTask(BaseModel):
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    version: str | None = None
    issue_url: str | None = None
    pr_url: str | None = None
    hints_text: str | None = None
    fail_to_pass: str | list[str] | None = Field(default=None, alias="FAIL_TO_PASS")
    pass_to_pass: str | list[str] | None = Field(default=None, alias="PASS_TO_PASS")

    @classmethod
    def from_path(cls, path: str | Path, instance_id: str | None = None) -> "SweBenchTask":
        source = Path(path)
        if source.suffix == ".json":
            payload = json.loads(source.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return cls._from_collection(payload, instance_id=instance_id)
            return cls.model_validate(payload)

        if source.suffix in {".jsonl", ".all"} or source.name.endswith(".jsonl.all"):
            items = [
                json.loads(line)
                for line in source.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            return cls._from_collection(items, instance_id=instance_id)

        raise ValueError(f"Unsupported SWE-bench file format: {source.name}")

    @classmethod
    def _from_collection(
        cls,
        items: list[dict[str, Any]],
        *,
        instance_id: str | None,
    ) -> "SweBenchTask":
        if instance_id is None:
            raise ValueError("instance_id is required when the input file contains multiple tasks")

        for item in items:
            if item.get("instance_id") == instance_id:
                return cls.model_validate(item)

        raise ValueError(f"Instance {instance_id!r} not found in input file")

    def to_brief(self) -> str:
        sections = [
            "Solve the following SWE-bench task.",
            "",
            f"Instance ID: {self.instance_id}",
            f"Repository: {self.repo}",
            f"Base commit: {self.base_commit}",
        ]

        if self.version:
            sections.append(f"Repository version: {self.version}")
        if self.issue_url:
            sections.append(f"Issue URL: {self.issue_url}")
        if self.pr_url:
            sections.append(f"Reference PR URL: {self.pr_url}")

        sections.extend(
            [
                "",
                "Problem statement:",
                self.problem_statement.strip(),
            ]
        )

        if self.hints_text:
            sections.extend(["", "Hints:", self.hints_text.strip()])

        fail_to_pass = self._render_test_field(self.fail_to_pass)
        pass_to_pass = self._render_test_field(self.pass_to_pass)
        if fail_to_pass:
            sections.extend(["", "FAIL_TO_PASS:", fail_to_pass])
        if pass_to_pass:
            sections.extend(["", "PASS_TO_PASS:", pass_to_pass])

        sections.extend(
            [
                "",
                "Expected process:",
                "1. Architect writes docs/architecture.md and docs/implementation_plan.md for this issue.",
                "2. Coder implements a minimal patch in src/ and tests/ based on those artifacts.",
                "3. Both agents preserve artifact traceability in docs/delivery_report.md and .mas/artifacts.json.",
            ]
        )
        return "\n".join(sections)

    def workspace_name(self) -> str:
        repo_slug = self.repo.replace("/", "__")
        return f"swebench_{repo_slug}_{self.instance_id}"

    @staticmethod
    def _render_test_field(value: str | list[str] | None) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return "\n".join(f"- {item}" for item in value)
        return str(value).strip()
