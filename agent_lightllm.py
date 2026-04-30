from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import SecretStr

from mas.openhands_roles import OpenHandsRoleRunner, OpenHandsRuntimeConfig
from mas.orchestrator import OpenHandsLangGraphOrchestrator
from mas.swebench import SweBenchTask


DEFAULT_BRIEF = "Build a simple multi-agent software delivery system with an architect and coder."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the protocol-first multi-agent software-delivery demo."
    )
    parser.add_argument(
        "--workspace",
        default="demo_workspace",
        help="Target workspace root used by the workspace service.",
    )
    parser.add_argument(
        "--brief",
        default=DEFAULT_BRIEF,
        help="Product request that enters the orchestrator.",
    )
    parser.add_argument(
        "--swe-bench-task",
        help="Path to a SWE-bench task file in .json or .jsonl format.",
    )
    parser.add_argument(
        "--instance-id",
        help="SWE-bench instance_id to select when the input file contains multiple tasks.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL")
    base_url = os.getenv("LLM_BASE_URL")
    if not api_key or not model:
        raise RuntimeError("LLM_API_KEY and LLM_MODEL must be set.")

    brief = args.brief
    workspace_root = Path(args.workspace).resolve()
    if args.swe_bench_task:
        swe_task = SweBenchTask.from_path(
            args.swe_bench_task,
            instance_id=args.instance_id,
        )
        brief = swe_task.to_brief()
        if args.workspace == "demo_workspace":
            workspace_root = Path(swe_task.workspace_name()).resolve()

    runtime = OpenHandsRuntimeConfig(
        model=model,
        api_key=SecretStr(api_key),
        base_url=base_url,
    )
    runner = OpenHandsRoleRunner(config=runtime, workspace_root=workspace_root)
    orchestrator = OpenHandsLangGraphOrchestrator(
        workspace_root=workspace_root,
        runner=runner,
    )
    report = orchestrator.run(brief)

    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
