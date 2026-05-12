import subprocess  # Позволяет запускать agent_lightllm.py из этого скрипта
import json         # Сохраняем результаты в JSON
import sys          # Доступ к Python (чтобы запускать тот же интерпретатор)
from pathlib import Path  # Работа с путями к папкам (Windows/Linux)
from datetime import datetime  # Добавляем время к именам файлов


EXPERIMENTS = [
    # 1. Базовый
    {
        "id": "01_baseline",      # Уникальное имя файла
        "type": "clean",           # Категория
        "prompt": "Напиши функцию для вычисления факториала числа на Python",
        "note": "Эталон - без изменений"
    },
    # 2. Неполнота
    {
        "id": "02_incomplete_data",
        "type": "not_full",
        "prompt": "Напиши функцию для вычисления",  # <-- отличается от оригинала
        "note": "Отсутствует слово 'факториал'"
    },
    # 3. Противоречие
    {
        "id": "03_contradiction",
        "type": "conflict",
        "prompt": "Напиши функцию факториала, но не используй циклы и рекурсию",
        "note": "Невозможно выполнить одновременно"
    },
    # 4. Шум
    {
        "id": "04_noise",
        "type": "garbage",
        "prompt": "Напиши [ШУМ] функцию факториала ^&*#@ на Python!!! asdf",
        "note": "Мусорные символы в запросе"
    }
]



def run_agent(prompt: str) -> dict:
    """Запускает agent_lightllm.py и возвращает результат"""
    
    try:
        # subprocess.run — запускает внешнюю команду
        # sys.executable — путь к текущему Python (например, python.exe)
        # ["python", "agent_lightllm.py", "--brief", prompt] — команда
        result = subprocess.run(
            [sys.executable, "agent_lightllm.py", "--brief", prompt],
            capture_output=True,  # Ловим вывод программы
            text=True,            # Как текст, а не байты
            timeout=120           # Если дольше 2 минут — прерываем
        )
        
        # Если программа завершилась без ошибок (returncode == 0)
        if result.returncode == 0:
            # Разбиваем вывод на строки
            lines = result.stdout.strip().split('\n')
            # Последняя строка — это JSON с ответом
            json_line = lines[-1] if lines else "{}"
            try:
                # Превращаем строку JSON в словарь Python
                data = json.loads(json_line)
                return {"success": True, "data": data}
            except:
                # Если JSON не получился, сохраняем как есть
                return {"success": True, "data": {"raw": result.stdout}}
        else:
            # Ошибка: агент вернул код ошибки
            return {"success": False, "error": result.stderr}
            
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Таймаут 120 секунд"}
    except Exception as e:
        return {"success": False, "error": str(e)}




def save_card(experiment: dict, result: dict) -> Path:
    """Сохраняет результат эксперимента в файл"""
    
    # Создаём папку experiments/cards/ (если её нет)
    cards_dir = Path("experiments/cards")
    cards_dir.mkdir(parents=True, exist_ok=True)
    
    # Берём текущее время: 2026-05-12 15:30:00 -> 20260512_153000
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Имя файла: 01_baseline_20260512_153000.json
    filename = cards_dir / f"{experiment['id']}_{timestamp}.json"
    
    # Открываем файл на запись
    with open(filename, "w", encoding="utf-8") as f:
        # Сохраняем словарь в JSON-формате
        json.dump({
            "experiment_id": experiment["id"],
            "experiment_type": experiment["type"],
            "prompt": experiment["prompt"],
            "note": experiment["note"],
            "result": result,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)  # indent=2 — красивые отступы
    
    return filename  # Возвращаем путь к файлу



def main():
    print("=" * 70)
    print("🔬 БЕНЧМАРК ОТКАЗОУСТОЙЧИВОСТИ МУЛЬТИАГЕНТНЫХ СИСТЕМ")
    print("=" * 70)
    print(f"📋 Всего экспериментов: {len(EXPERIMENTS)}")
    print(f"📁 Результаты: experiments/cards/")
    print("=" * 70)
    
    # Проходим по каждому эксперименту из списка
    # enumerate даёт номер (i) и сам эксперимент (exp)
    for i, exp in enumerate(EXPERIMENTS, 1):
        # Выводим информацию о текущем эксперименте
        print(f"\n[{i}/{len(EXPERIMENTS)}] 🔬 {exp['id']} - {exp['type']}")
        print(f"    📝 {exp['note']}")
        print(f"    💬 Промпт: {exp['prompt'][:80]}...")
        
        # ЗАПУСКАЕМ агента с этим промптом
        result = run_agent(exp['prompt'])
        
        # СОХРАНЯЕМ результат
        filename = save_card(exp, result)
        
        # Выводим статус
        status = "✅ УСПЕХ" if result["success"] else "❌ ОШИБКА"
        print(f"    {status} → {filename.name}")
    
    # Финальная сводка
    print("\n" + "=" * 70)
    print("✅ Все эксперименты завершены!")
    print("📂 Смотрите результаты в папке: experiments/cards/")
    print("=" * 70)


if __name__ == "__main__":
    main()