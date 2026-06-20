"""
Полный тест отказоустойчивости MAS
1. Берёт задачу
2. Создаёт баги (неполнота, шум, противоречие)
3. Запускает LLM
4. Оценивает падение качества
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

from bug_generator import BugGenerator
from quality_checker import QualityChecker

# Задачи для тестирования
TASKS = [
    {
        "name": "factorial",
        "prompt": "Напиши функцию для вычисления факториала числа на Python",
        "keywords": ["факториал", "def", "return", "factorial"],
    },
    {
        "name": "prime_check",
        "prompt": "Напиши функцию для проверки, является ли число простым",
        "keywords": ["простое", "prime", "def", "return"],
    },
    {
        "name": "string_reverse",
        "prompt": "Напиши функцию для реверса строки на Python",
        "keywords": ["реверс", "reverse", "def", "return", "строка"],
    },
]

BUG_TYPES = ["incomplete", "noise", "contradiction"]
LEVELS = ["low", "medium", "high"]


def parse_agent_output(stdout: str) -> dict:
    stdout = stdout.strip()
    if not stdout:
        return {}
    lines = stdout.split("\n")
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"result": stdout}


def run_agent(prompt: str) -> dict:
    """Запускает агента и возвращает структурированный ответ."""
    try:
        env = os.environ.copy()
        for _proxy_key in (
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy",
        ):
            env.pop(_proxy_key, None)

        result = subprocess.run(
            [sys.executable, "agent_lightllm.py", "--brief", prompt],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )

        if result.returncode == 0:
            data = parse_agent_output(result.stdout)
            return {
                "success": True,
                "data": data,
                "text": QualityChecker.extract_text(data),
                "error": None,
            }
        return {"success": False, "data": {}, "text": "", "error": result.stderr}
    except Exception as e:
        return {"success": False, "data": {}, "text": "", "error": str(e)}


def run_test():
    results_dir = Path("robustness_results")
    results_dir.mkdir(exist_ok=True)

    all_results = []

    print("=" * 70)
    print("ТЕСТИРОВАНИЕ ОТКАЗОУСТОЙЧИВОСТИ MAS")
    print("=" * 70)

    for task in TASKS:
        print(f"\n\nЗАДАЧА: {task['name']}")
        print("-" * 50)

        print("  Чистый запрос...")
        clean_result = run_agent(task["prompt"])
        clean_source = clean_result["data"] if clean_result["success"] else clean_result["text"]
        clean_analysis = QualityChecker.analyze_response(
            clean_source, task["keywords"], prompt=task["prompt"]
        )
        print(f"    Качество: {clean_analysis['score']:.2f}")

        for bug_type in BUG_TYPES:
            for level in LEVELS:
                print(f"\n  Баг: {bug_type} ({level})...")

                buggy_prompt = BugGenerator.generate(task["prompt"], bug_type, level)
                buggy_result = run_agent(buggy_prompt)
                buggy_source = buggy_result["data"] if buggy_result["success"] else buggy_result["text"]
                buggy_analysis = QualityChecker.analyze_response(
                    buggy_source, task["keywords"], prompt=task["prompt"]
                )

                degradation = QualityChecker.degradation(
                    clean_analysis["score"],
                    buggy_analysis["score"],
                )

                print(
                    f"    Качество: {buggy_analysis['score']:.2f} "
                    f"(падение: {degradation['loss_percent']:.1f}%)"
                )

                result = {
                    "task": task["name"],
                    "bug_type": bug_type,
                    "intensity": level,
                    "clean": {
                        "prompt": task["prompt"],
                        "score": clean_analysis["score"],
                        "agent_completeness": clean_analysis["agent_completeness"],
                        "response_preview": clean_result["text"][:300],
                    },
                    "buggy": {
                        "prompt": buggy_prompt,
                        "score": buggy_analysis["score"],
                        "agent_completeness": buggy_analysis["agent_completeness"],
                        "response_preview": buggy_result["text"][:300],
                    },
                    "degradation": degradation,
                    "timestamp": datetime.now().isoformat(),
                }
                all_results.append(result)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = results_dir / f"robustness_report_{timestamp}.json"

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("ИТОГОВАЯ ТАБЛИЦА ПАДЕНИЯ КАЧЕСТВА (%)")
    print("=" * 70)

    summary = {}
    for r in all_results:
        key = (r["bug_type"], r["intensity"])
        summary.setdefault(key, []).append(r["degradation"]["loss_percent"])

    print("\nТип бага    | low | medium | high")
    print("-" * 40)
    for bug_type in BUG_TYPES:
        row = f"{bug_type:11} | "
        for level in LEVELS:
            key = (bug_type, level)
            if key in summary:
                avg = sum(summary[key]) / len(summary[key])
                row += f"{avg:5.1f} | "
            else:
                row += "     | "
        print(row)

    print(f"\n\nПолный отчёт сохранён: {report_file}")

    txt_file = results_dir / f"robustness_report_{timestamp}.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("ОТЧЁТ ОБ ОТКАЗОУСТОЙЧИВОСТИ MAS\n")
        f.write("=" * 70 + "\n\n")

        for r in all_results:
            f.write(f"\nЗадача: {r['task']}\n")
            f.write(f"Баг: {r['bug_type']} ({r['intensity']})\n")
            f.write(f"Чистый запрос: {r['clean']['prompt'][:100]}...\n")
            f.write(f"Баговый запрос: {r['buggy']['prompt'][:100]}...\n")
            f.write(f"Качество чистого: {r['clean']['score']:.2f}\n")
            f.write(f"Качество багового: {r['buggy']['score']:.2f}\n")
            f.write(f"Падение качества: {r['degradation']['loss_percent']:.1f}%\n")
            f.write("-" * 50 + "\n")

    print(f"Текстовый отчёт: {txt_file}")


if __name__ == "__main__":
    run_test()
