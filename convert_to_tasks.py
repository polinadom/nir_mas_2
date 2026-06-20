import json
from pathlib import Path

# Загружаем SWE-bench задачи
with open("swe_fastapi_tasks.json", "r", encoding="utf-8") as f:
    swe_tasks = json.load(f)

print(f"Загружено {len(swe_tasks)} SWE задач")

# Создаём папку для карточек
tasks_dir = Path("tasks")
tasks_dir.mkdir(exist_ok=True)

for task in swe_tasks:
    task_card = {
        "id": task["instance_id"],
        "name": f"SWE-bench: {task['instance_id']}",
        "prompt": task["problem_statement"],
        "keywords": ["fix", "bug", "implement", "change", "update"],
        "difficulty": "hard",
        "category": "swe_bench",
        "swe_metadata": {
            "repo": task["repo"],
            "base_commit": task["base_commit"],
            "patch": task["patch"]
        }
    }
    
    # Сохраняем
    output_file = tasks_dir / f"swe_{task['instance_id']}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(task_card, f, ensure_ascii=False, indent=2)
    
    print(f"Создана карточка: {output_file}")

print(f"\nГотово! Создано {len(swe_tasks)} карточек в папке tasks/")