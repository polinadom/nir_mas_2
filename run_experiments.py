"""
ГЛАВНЫЙ СКРИПТ
1. Читает карточки задач из папки tasks/
2. Генерирует баги
3. Запускает MAS
4. Оценивает качество
5. Сохраняет результаты
"""

import argparse
import subprocess
import json
import sys
import time
import os
from pathlib import Path
from datetime import datetime

from bug_generator import BugGenerator
from quality_checker import QualityChecker


# ============================================================
# ЗАГРУЗКА ЗАДАЧ ИЗ КАРТОЧЕК
# ============================================================

def load_tasks(tasks_dir: Path = Path("tasks")):
    """Загружает все JSON-карточки из папки tasks/"""
    tasks = []

    if not tasks_dir.exists():
        print(f"ОШИБКА: Папка {tasks_dir} не найдена!")
        return tasks

    for json_file in tasks_dir.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                task = json.load(f)
                if 'id' not in task:
                    task['id'] = json_file.stem
                if 'name' not in task:
                    task['name'] = task.get('id', json_file.stem)
                tasks.append(task)
                print(f"Загружена задача: {task['id']} - {task['name']}")
        except Exception as e:
            print(f"Ошибка загрузки {json_file}: {e}")
            continue

    return tasks


# ============================================================
# ТИПЫ БАГОВ И УРОВНИ
# ============================================================

BUG_TYPES = ["incomplete", "noise", "contradiction"]
LEVELS = ["low", "medium", "high"]


# ============================================================
# ЗАПУСК MAS
# ============================================================

def run_agent(prompt: str, timeout: int = 600) -> dict:
    """Запускает agent_lightllm.py и возвращает ответ"""
    try:
        # Отключаем прокси для этого вызова
        env = os.environ.copy()
        env["HTTP_PROXY"] = ""
        env["HTTPS_PROXY"] = ""
        env["ALL_PROXY"] = ""
        env["PYTHONIOENCODING"] = "utf-8"
        
        result = subprocess.run(
            [sys.executable, "agent_lightllm.py", "--brief", prompt],
            capture_output=True,
            timeout=timeout,
            env=env
        )

        # Декодируем с обработкой ошибок
        stdout = result.stdout.decode('utf-8', errors='ignore')
        stderr = result.stderr.decode('utf-8', errors='ignore')

        # Проверяем stdout на JSON
        if stdout:
            try:
                # Ищем JSON в выводе
                lines = stdout.strip().split('\n')
                for line in reversed(lines):
                    if line.strip().startswith('{'):
                        data = json.loads(line)
                        if 'error' in data:
                            return {"success": False, "response": "", "error": data['error']}
                        # Извлекаем результат
                        if 'code' in data:
                            return {"success": True, "response": data['code'], "error": None}
                        elif 'plan' in data:
                            return {"success": True, "response": data['plan'], "error": None}
                        elif 'review' in data:
                            return {"success": True, "response": data['review'], "error": None}
                        elif 'result' in data:
                            return {"success": True, "response": data['result'], "error": None}
                        elif 'status' in data and data['status'] == 'success':
                            return {"success": True, "response": json.dumps(data, ensure_ascii=False), "error": None}
            except json.JSONDecodeError:
                pass
        
        # Если JSON не найден, но есть stdout
        if stdout:
            if "Error" in stdout or "error" in stdout:
                return {"success": False, "response": "", "error": stdout[:200]}
            return {"success": True, "response": stdout, "error": None}
        
        # Если stdout пустой, проверяем stderr
        if stderr:
            return {"success": False, "response": "", "error": stderr[:200]}
        
        # Если всё пусто
        if result.returncode != 0:
            return {"success": False, "response": "", "error": f"Return code {result.returncode}"}
        
        return {"success": True, "response": "No output", "error": None}
            
    except subprocess.TimeoutExpired:
        return {"success": False, "response": "", "error": f"Timeout после {timeout} секунд"}
    except Exception as e:
        return {"success": False, "response": "", "error": str(e)}


# ============================================================
# ЗАПУСК ВСЕХ ЭКСПЕРИМЕНТОВ
# ============================================================

def main():
    # Парсим аргументы
    parser = argparse.ArgumentParser(description="Тестирование отказоустойчивости MAS")
    parser.add_argument('--limit', type=int, default=None, help='Max number of tasks to run')
    parser.add_argument('--timeout', type=int, default=600, help='Timeout per agent call (seconds)')
    args = parser.parse_args()

    # Создаём папки
    results_dir = Path("experiments")
    results_dir.mkdir(exist_ok=True)

    # Загружаем задачи
    print("="*70)
    print("ЗАГРУЗКА КАРТОЧЕК ЗАДАЧ")
    print("="*70)

    tasks = load_tasks()
    if args.limit is not None:
        tasks = tasks[:args.limit]

    if not tasks:
        print("Нет задач для тестирования!")
        return

    print(f"\nВсего задач: {len(tasks)}")

    all_results = []
    experiment_counter = 1

    print("\n" + "="*70)
    print("ТЕСТИРОВАНИЕ ОТКАЗОУСТОЙЧИВОСТИ MAS")
    print("Схема: Карточка задачи -> Генератор багов -> MAS -> Оценка")
    print("="*70)

    for task in tasks:
        print(f"\n{'='*70}")
        print(f"ЗАДАЧА: {task['id']} - {task['name']}")
        print(f"Категория: {task.get('category', 'unknown')}")
        print(f"Сложность: {task.get('difficulty', 'unknown')}")
        
        # Получаем промпт
        prompt = task.get('prompt', task.get('problem_statement', ''))
        if not prompt:
            print(f"  ⚠️ Нет промпта в задаче {task['id']}!")
            continue
            
        print(f"Промпт: {prompt[:200]}...")
        print(f"{'='*70}")

        # Получаем ключевые слова
        keywords = task.get('keywords', ['python', 'code', 'function', 'class'])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(',')]

        # 1. Базовый эксперимент (без бага)
        print(f"\n[Эксперимент {experiment_counter}] BASELINE (без бага)")
        print(f"  ⏳ Ожидание ответа от MAS...")
        baseline_result = run_agent(prompt, timeout=args.timeout)

        if baseline_result["success"]:
            baseline_quality = QualityChecker.score(baseline_result["response"], keywords)
            print(f"  ✅ Качество: {baseline_quality:.0%}")
            print(f"  📏 Длина ответа: {len(baseline_result['response'])} символов")
        else:
            baseline_quality = 0
            print(f"  ❌ ОШИБКА: {baseline_result['error'][:200]}")

        # Сохраняем baseline
        baseline_file = results_dir / f"{experiment_counter:02d}_baseline_{task['id']}.json"
        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump({
                "experiment_id": f"baseline_{task['id']}",
                "task": task,
                "bug_type": "none",
                "intensity": "none",
                "clean_prompt": prompt,
                "success": baseline_result["success"],
                "response": baseline_result["response"][:3000] if baseline_result["success"] else None,
                "error": baseline_result["error"],
                "quality_score": baseline_quality,
                "response_length": len(baseline_result["response"]) if baseline_result["success"] else 0,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)

        experiment_counter += 1

        # 2. Эксперименты с багами
        for bug_type in BUG_TYPES:
            for level in LEVELS:
                print(f"\n[Эксперимент {experiment_counter}] {bug_type.upper()} (уровень: {level})")

                # ГЕНЕРАЦИЯ БАГА
                buggy_prompt = BugGenerator.generate(prompt, bug_type, level)
                print(f"  📝 Баговый промпт: {buggy_prompt[:80]}...")
                print(f"  ⏳ Ожидание ответа от MAS...")

                # ЗАПУСК MAS
                start_time = time.time()
                buggy_result = run_agent(buggy_prompt, timeout=args.timeout)
                elapsed_time = time.time() - start_time

                if buggy_result["success"]:
                    buggy_quality = QualityChecker.score(buggy_result["response"], keywords)

                    # ОЦЕНКА ПАДЕНИЯ КАЧЕСТВА
                    degradation = QualityChecker.degradation(baseline_quality, buggy_quality)

                    print(f"  ✅ Качество: {buggy_quality:.0%}")
                    print(f"  📉 Падение: {degradation['loss_percent']:.1f}%")
                    print(f"  🛡️  Вывод: {'УСТОЙЧИВА' if degradation['is_robust'] else 'УЯЗВИМА'}")
                    print(f"  ⏱️  Время: {elapsed_time:.1f} сек")
                else:
                    buggy_quality = 0
                    degradation = {"loss_percent": 100, "is_robust": False, "is_vulnerable": True}
                    print(f"  ❌ ОШИБКА: {buggy_result['error'][:200]}")

                # СОХРАНЯЕМ РЕЗУЛЬТАТ В ОТДЕЛЬНЫЙ ФАЙЛ
                result_file = results_dir / f"{experiment_counter:02d}_{bug_type}_{level}_{task['id']}.json"

                experiment_data = {
                    "experiment_id": f"{bug_type}_{level}_{task['id']}",
                    "task_id": task["id"],
                    "task_name": task["name"],
                    "bug_type": bug_type,
                    "intensity": level,
                    "buggy_prompt": buggy_prompt,
                    "success": buggy_result["success"],
                    "response": buggy_result["response"][:3000] if buggy_result["success"] else None,
                    "error": buggy_result["error"],
                    "baseline_quality": baseline_quality,
                    "buggy_quality": buggy_quality,
                    "quality_loss_percent": degradation["loss_percent"],
                    "is_robust": degradation["is_robust"],
                    "response_length": len(buggy_result["response"]) if buggy_result["success"] else 0,
                    "elapsed_time": elapsed_time,
                    "timestamp": datetime.now().isoformat()
                }

                with open(result_file, "w", encoding="utf-8") as f:
                    json.dump(experiment_data, f, ensure_ascii=False, indent=2)

                print(f"  💾 Сохранён: {result_file.name}")

                all_results.append(experiment_data)
                experiment_counter += 1
                
                # Небольшая пауза между запросами
                time.sleep(1)

    # ============================================================
    # СОЗДАЁМ ИТОГОВУЮ ТАБЛИЦУ
    # ============================================================
    print("\n" + "="*70)
    print("📊 ИТОГОВАЯ ТАБЛИЦА ОТКАЗОУСТОЙЧИВОСТИ")
    print("="*70)

    # Группируем по типу бага и уровню
    summary = {}
    for r in all_results:
        key = (r["bug_type"], r["intensity"])
        if key not in summary:
            summary[key] = []
        summary[key].append(r["quality_loss_percent"])

    # Таблица
    table_lines = []
    table_lines.append("="*70)
    table_lines.append("ОТЧЁТ ОБ ОТКАЗОУСТОЙЧИВОСТИ MAS")
    table_lines.append(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    table_lines.append(f"Задач: {len(tasks)}")
    table_lines.append("="*70)
    table_lines.append("")
    table_lines.append("Таблица падения качества (%) при разных типах багов:")
    table_lines.append("")
    table_lines.append(f"{'Тип бага':<15} {'Low':<12} {'Medium':<12} {'High':<12}")
    table_lines.append("-"*51)

    for bug_type in BUG_TYPES:
        row = f"{bug_type:<15}"
        for level in LEVELS:
            key = (bug_type, level)
            if key in summary and summary[key]:
                avg_loss = sum(summary[key]) / len(summary[key])
                if avg_loss < 20:
                    row += f"🟢 {avg_loss:>5.1f}%    "
                elif avg_loss < 50:
                    row += f"🟡 {avg_loss:>5.1f}%    "
                else:
                    row += f"🔴 {avg_loss:>5.1f}%    "
            else:
                row += "   N/A     "
        table_lines.append(row)

    table_lines.append("-"*51)
    table_lines.append("")
    table_lines.append("Расшифровка:")
    table_lines.append("  🟢 <20% - система УСТОЙЧИВА к данному типу бага")
    table_lines.append("  🟡 20-50% - средняя уязвимость")
    table_lines.append("  🔴 >50% - система УЯЗВИМА к данному типу бага")
    table_lines.append("")
    table_lines.append("="*70)

    # Сохраняем таблицу
    table_file = results_dir / "summary_table.txt"
    with open(table_file, "w", encoding="utf-8") as f:
        f.write("\n".join(table_lines))

    # Выводим
    for line in table_lines:
        print(line)

    print(f"\n\n📁 РЕЗУЛЬТАТЫ СОХРАНЕНЫ:")
    print(f"  - Папка: {results_dir}/")
    print(f"  - Карточки задач: tasks/")
    print(f"  - Итоговая таблица: {table_file}")
    print("="*70)


if __name__ == "__main__":
    main()