from __future__ import annotations

import json
import operator
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from .a2a import A2AMessage, Performative, new_id
from .artifacts import ArtifactRegistry
from .openhands_roles import OpenHandsRoleRunner, RoleDefinition
from .workspace import WorkspaceManager


ARCHITECT_PROMPT = """You are the architecture agent in a two-agent software team.
Your responsibilities:
- analyse the product request
- produce architecture and implementation-plan artifacts
- communicate assumptions explicitly
- avoid implementation details unless they unblock the coder

You must create or update:
- docs/architecture.md
- docs/implementation_plan.md

Keep outputs practical, concrete, and implementation-ready.
"""


CODER_PROMPT = """You are the coding agent in a two-agent software team.
Your responsibilities:
- read architecture artifacts carefully
- implement only what follows from the architecture and current request
- keep changes coherent and minimal
- preserve artifact traceability by naming edited files clearly in docs/delivery_report.md

You must create or update code and tests in the shared workspace.
"""


class WorkflowState(TypedDict):
    brief: str
    thread_id: str
    status: str
    a2a_messages: Annotated[list[dict[str, Any]], operator.add]
    artifact_records: Annotated[list[dict[str, Any]], operator.add]
    architect_refs: list[dict[str, Any]]
    coder_refs: list[dict[str, Any]]


class OrchestrationReport(BaseModel):
    thread_id: str
    status: str
    workspace_root: str
    artifact_manifest: str
    artifact_count: int
    files: list[str] = Field(default_factory=list)


class OpenHandsLangGraphOrchestrator:
    def __init__(self, workspace_root: Path, runner: OpenHandsRoleRunner) -> None:
        self.workspace = WorkspaceManager(workspace_root)
        self.workspace.ensure_layout()
        self.registry = ArtifactRegistry(self.workspace.root)
        self.runner = runner
        self.architect = RoleDefinition(name="architect", system_prompt=ARCHITECT_PROMPT)
        self.coder = RoleDefinition(name="coder", system_prompt=CODER_PROMPT)
        self.graph = self._build_graph()

    def run(self, brief: str) -> OrchestrationReport:
        thread_id = new_id()
        final_state = self.graph.invoke(
            {
                "brief": brief,
                "thread_id": thread_id,
                "status": "created",
                "a2a_messages": [],
                "artifact_records": [],
                "architect_refs": [],
                "coder_refs": [],
            }
        )
        before_report = self.registry.snapshot()
        self._write_delivery_report(final_state)
        self.registry.collect_stage_artifacts(
            before=before_report,
            stage="finalize",
            producer="orchestrator",
        )
        return OrchestrationReport(
            thread_id=thread_id,
            status=final_state["status"],
            workspace_root=str(self.workspace.root),
            artifact_manifest=str(self.registry.manifest_path),
            artifact_count=len(self.registry.records),
            files=self.workspace.list_files(),
        )

    def _build_graph(self):
        graph = StateGraph(WorkflowState)
        graph.add_node("architect", self._architect_node)
        graph.add_node("coder", self._coder_node)
        graph.add_node("finalize", self._finalize_node)
        graph.add_edge(START, "architect")
        graph.add_edge("architect", "coder")
        graph.add_edge("coder", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    def _architect_node(self, state: WorkflowState) -> dict[str, object]:
        request = A2AMessage(
            sender="orchestrator",
            recipient="architect",
            performative=Performative.REQUEST,
            topic="architecture.requested",
            thread_id=state["thread_id"],
            body={
                "brief": state["brief"],
                "required_artifacts": [
                    "docs/architecture.md",
                    "docs/implementation_plan.md",
                ],
            },
        )
        before = self.registry.snapshot()
        self.runner.run_task(self.architect, self._architect_task(request))
        records = self.registry.collect_stage_artifacts(
            before=before,
            stage="architecture",
            producer="architect",
        )
        refs = ArtifactRegistry.refs(records)
        handoff = A2AMessage(
            sender="architect",
            recipient="coder",
            performative=Performative.HANDOFF,
            topic="architecture.ready",
            thread_id=state["thread_id"],
            correlation_id=request.message_id,
            parent_message_id=request.message_id,
            body={
                "brief": state["brief"],
                "artifact_refs": [ref.model_dump(mode="json") for ref in refs],
                "instruction": "Implement the design using these artifacts as source of truth.",
            },
        )
        return {
            "status": "architecture_ready",
            "a2a_messages": [
                request.model_dump(mode="json"),
                handoff.model_dump(mode="json"),
            ],
            "artifact_records": [record.model_dump(mode="json") for record in records],
            "architect_refs": [ref.model_dump(mode="json") for ref in refs],
        }

    def _coder_node(self, state: WorkflowState) -> dict[str, object]:
        inbound = A2AMessage(
            sender="architect",
            recipient="coder",
            performative=Performative.HANDOFF,
            topic="implementation.requested",
            thread_id=state["thread_id"],
            body={
                "brief": state["brief"],
                "artifact_refs": state["architect_refs"],
                "required_outputs": [
                    "src/",
                    "tests/",
                    "docs/delivery_report.md",
                ],
            },
        )
        before = self.registry.snapshot()
        self.runner.run_task(self.coder, self._coder_task(inbound))
        records = self.registry.collect_stage_artifacts(
            before=before,
            stage="implementation",
            producer="coder",
        )
        refs = ArtifactRegistry.refs(records)
        result = A2AMessage(
            sender="coder",
            recipient="orchestrator",
            performative=Performative.RESULT,
            topic="implementation.completed",
            thread_id=state["thread_id"],
            correlation_id=inbound.message_id,
            parent_message_id=inbound.message_id,
            body={
                "artifact_refs": [ref.model_dump(mode="json") for ref in refs],
            },
        )
        return {
            "status": "implementation_ready",
            "a2a_messages": [
                inbound.model_dump(mode="json"),
                result.model_dump(mode="json"),
            ],
            "artifact_records": [record.model_dump(mode="json") for record in records],
            "coder_refs": [ref.model_dump(mode="json") for ref in refs],
        }

    def _finalize_node(self, state: WorkflowState) -> dict[str, object]:
        return {"status": "completed"}

    def _write_delivery_report(self, state: WorkflowState) -> None:
        report_path = self.workspace.resolve("docs/delivery_report.md")
        payload = {
            "thread_id": state["thread_id"],
            "status": state["status"],
            "architect_artifacts": state["architect_refs"],
            "coder_artifacts": state["coder_refs"],
            "a2a_messages": state["a2a_messages"],
            "artifact_manifest": str(self.registry.manifest_path.relative_to(self.workspace.root)),
        }
        report_path.write_text(
            "# Delivery Report\n\n```json\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
            + "\n```\n",
            encoding="utf-8",
        )

    @staticmethod
    def _architect_task(request: A2AMessage) -> str:
        return (
            "You are receiving an A2A request.\n\n"
            f"{json.dumps(request.model_dump(mode='json'), ensure_ascii=False, indent=2)}\n\n"
            "Work in the provided workspace. Produce the required documentation artifacts. "
            "Be explicit about assumptions, system boundaries, agent responsibilities, "
            "workspace conventions, and how artifacts should be handed off to the coder."
        )

    @staticmethod
    def _coder_task(request: A2AMessage) -> str:
        artifact_paths = [
            ref["path"]
            for ref in request.body.get("artifact_refs", [])
            if isinstance(ref, dict) and "path" in ref
        ]
        sources = ", ".join(artifact_paths) if artifact_paths else "the architecture artifacts"
        return (
            "You are receiving an A2A handoff.\n\n"
            f"{json.dumps(request.model_dump(mode='json'), ensure_ascii=False, indent=2)}\n\n"
            f"Use {sources} as the source of truth. "
            "Implement a minimal but coherent codebase skeleton in src/ and tests/. "
            "Update docs/delivery_report.md with the edited files and a short implementation summary."
        )
