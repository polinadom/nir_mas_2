"""
Скачивание SWE-bench датасета и фильтрация задач FastAPI
"""

import json
from pathlib import Path

print("="*60)
print("ЗАГРУЗКА SWE-BENCH ДАТАСЕТА")
print("="*60)
print("Это может занять 2-5 минут...")
print()

try:
    from datasets import load_dataset
    
    # Загружаем датасет (только тренировочную часть)
    print("[1/3] Загрузка датасета...")
    dataset = load_dataset('SWE-bench/SWE-bench', split='train')
    
    print(f"[2/3] Датасет загружен. Всего задач: {len(dataset)}")
    
    # Фильтруем задачи FastAPI
    print("[3/3] Фильтрация задач FastAPI...")
    fastapi_tasks = []
    
    for i, item in enumerate(dataset):
        repo = item.get('repo', '')
        if 'fastapi' in repo.lower():
            fastapi_tasks.append(item)
            print(f"  Найдена задача FastAPI: {item.get('instance_id', 'unknown')}")
    
    print(f"\n✅ Найдено задач FastAPI: {len(fastapi_tasks)}")
    
    # Сохраняем в файл
    output_file = "swe_fastapi_tasks.json"
    with open(output_file, "w", encoding="utf-8") as f:
        # Преобразуем в список словарей для JSON
        tasks_to_save = []
        for task in fastapi_tasks:
            tasks_to_save.append({
                "instance_id": task.get("instance_id"),
                "repo": task.get("repo"),
                "base_commit": task.get("base_commit"),
                "problem_statement": task.get("problem_statement"),
                "patch": task.get("patch"),
                "FAIL_TO_PASS": task.get("FAIL_TO_PASS", []),
                "PASS_TO_PASS": task.get("PASS_TO_PASS", [])
            })
        json.dump(tasks_to_save, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Сохранено в {output_file}")
    
    # Показываем пример первой задачи
    if fastapi_tasks:
        print("\n" + "="*60)
        print("ПРИМЕР ПЕРВОЙ ЗАДАЧИ FASTAPI:")
        print("="*60)
        first = fastapi_tasks[0]
        print(f"ID: {first.get('instance_id')}")
        print(f"Репозиторий: {first.get('repo')}")
        print(f"Описание: {first.get('problem_statement')[:300]}...")
    
except ImportError:
    print("❌ Ошибка: библиотека datasets не установлена")
    print("Установите: pip install datasets")
except Exception as e:
    print(f"❌ Ошибка: {e}")

print("\n✅ Готово!")