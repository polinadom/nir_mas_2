from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI


DEFAULT_BRIEF = "Build a simple multi-agent software delivery system with an architect and coder."




def safe_print_json(data: dict) -> None:
    
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    cleaned = re.sub(r'[^\u0400-\u04FF\u0020-\u007E\n\r\t.,!?:;()\-=+*#@/\\]', '', json_str)
    try:
        print(cleaned)
    except UnicodeEncodeError:
        print(json_str.encode('ascii', 'ignore').decode('ascii'))


#заглушка

class OpenHandsRuntimeConfig:
    def __init__(self, model: str, api_key: str, base_url: str = None):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url


class OpenHandsRoleRunner:
    def __init__(self, config: OpenHandsRuntimeConfig, workspace_root: Path):
        self.config = config
        self.workspace_root = workspace_root
        self.client = OpenAI(
            api_key=config.api_key if isinstance(config.api_key, str) else config.api_key.get_secret_value(),
            base_url=config.base_url
        )
    
    def run(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content


class OpenHandsLangGraphOrchestrator:
    def __init__(self, workspace_root: Path, runner: OpenHandsRoleRunner):
        self.workspace_root = workspace_root
        self.runner = runner
    
    def run(self, brief: str):
        result = self.runner.run(brief)
        
        class Report:
            def __init__(self, result_text: str, workspace: Path):
                self._result = result_text
                self._workspace = workspace
            
            def model_dump(self, mode: str = "json") -> dict:
                return {
                    "status": "success",
                    "result": self._result,
                    "timestamp": datetime.now().isoformat(),
                    "workspace": str(self._workspace) if self._workspace else None
                }
        
        return Report(result, self.workspace_root)


class SweBenchTask:
    @staticmethod
    def from_path(path: str, instance_id: str = None):
        class Task:
            def __init__(self, path: str, instance_id: str):
                self.path = path
                self.instance_id = instance_id
            
            def to_brief(self) -> str:
                return f"[SWE-bench task] Репозиторий: {self.path}, задача: {self.instance_id or 'не указан'}"
            
            def workspace_name(self) -> str:
                return "swe_bench_workspace"
        
        return Task(path, instance_id)




def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default="demo_workspace")
    parser.add_argument("--brief", default=DEFAULT_BRIEF)
    parser.add_argument("--swe-bench-task")
    parser.add_argument("--instance-id")
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
        swe_task = SweBenchTask.from_path(args.swe_bench_task, instance_id=args.instance_id)
        brief = swe_task.to_brief()
        if args.workspace == "demo_workspace":
            workspace_root = Path(swe_task.workspace_name()).resolve()

    runtime = OpenHandsRuntimeConfig(model=model, api_key=api_key, base_url=base_url)
    runner = OpenHandsRoleRunner(config=runtime, workspace_root=workspace_root)
    orchestrator = OpenHandsLangGraphOrchestrator(workspace_root=workspace_root, runner=runner)
    report = orchestrator.run(brief)
    
    report_dict = report.model_dump(mode="json")
    
    # Сохраняем в лог
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, ensure_ascii=False, indent=2)
    
    
    safe_print_json(report_dict)


if __name__ == "__main__":
    main()