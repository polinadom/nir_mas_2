import subprocess  
import json         
import sys          
from pathlib import Path  
from datetime import datetime  


EXPERIMENTS = [
    # эталонная задача 

    {
        "id": "01_baseline",
        "type": "clean",
        "prompt": "Напиши функцию на Python, которая проверяет, является ли число простым",
        "note": "Эталон — полное и чёткое описание задачи"
    },

    # 2. Неполнота
    {
        "id": "02_incomplete_missing_details",
        "type": "incomplete",
        "prompt": "Напиши функцию на Python для проверки числа",
        "note": "Отсутствует указание — что именно проверять (простое? чётное? положительное?)"
    },
    {
        "id": "03_incomplete_no_language",
        "type": "incomplete",
        "prompt": "Напиши функцию для проверки простого числа",
        "note": "Не указан язык программирования"
    },
    {
        "id": "04_incomplete_no_return",
        "type": "incomplete",
        "prompt": "Напиши программу про простые числа",
        "note": "Не указано, нужна функция или скрипт, что возвращать"
    },
    

    # 3. Противоречия

    {
        "id": "05_contradiction_impossible",
        "type": "contradiction",
        "prompt": "Напиши функцию на Python, которая одновременно использует цикл for и не использует циклы",
        "note": "Прямое логическое противоречие"
    },
    {
        "id": "06_contradiction_type_mismatch",
        "type": "contradiction",
        "prompt": "Напиши функцию, которая принимает строку и возвращает её квадратный корень из числа",
        "note": "Тип не соответствует операции (корень из строки)"
    },
    {
        "id": "07_contradiction_performance",
        "type": "contradiction",
        "prompt": "Напиши рекурсивную функцию для вычисления чисел Фибоначчи, которая работает за O(1) по времени",
        "note": "Рекурсивный Фибоначчи не может быть O(1)"
    },
    

    # 4. ШУМ 
    {
        "id": "08_noise_random_chars",
        "type": "noise",
        "prompt": "Напиши функцию [ШУМ] asdfghjkl для сортировки ^&*#@ списка на Python!!! qwerty",
        "note": "Случайные символы в запросе"
    },
    {
        "id": "09_noise_irrelevant_text",
        "type": "noise",
        "prompt": "Напиши функцию бинарного поиска. Кстати, сегодня хорошая погода. Завтра будет дождь. Не забудь купить хлеб. Верни индекс элемента.",
        "note": "Посторонний текст, не относящийся к задаче"
    },
    {
        "id": "10_noise_emoji",
        "type": "noise",
        "prompt": "🚀 Напиши 🔥 функцию для 🐍 реверса строки 😊 на Python 💻",
        "note": "Эмодзи и спецсимволы"
    },
    

    # 5. СМЕШАННЫЕ (несколько типов багов одновременно)
    {
        "id": "11_mixed_noise_incomplete",
        "type": "mixed",
        "prompt": "Напиши [ШУМ] asdf функцию для поиска ***",
        "note": "Шум + неполнота (не указано, что искать)"
    },
    {
        "id": "12_mixed_contradiction_noise",
        "type": "mixed",
        "prompt": "Напиши рекурсивный цикл ^&* для обхода дерева, но без рекурсии и циклов",
        "note": "Противоречие + шум"
    },
]



def run_agent(prompt: str) -> dict:
    """Запускает agent_lightllm.py и возвращает результат"""
    
    try:

        result = subprocess.run(
            [sys.executable, "agent_lightllm.py", "--brief", prompt],
            capture_output=True, 
            text=True,            
            timeout=120          
        )
        
        
        if result.returncode == 0:
            
            lines = result.stdout.strip().split('\n')
            
            json_line = lines[-1] if lines else "{}"
            try:
                
                data = json.loads(json_line)
                return {"success": True, "data": data}
            except:
                
                return {"success": True, "data": {"raw": result.stdout}}
        else:
            
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
    print("БЕНЧМАРК ОТКАЗОУСТОЙЧИВОСТИ МУЛЬТИАГЕНТНЫХ СИСТЕМ")
    print("=" * 70)
    print(f"Всего экспериментов: {len(EXPERIMENTS)}")
    print(f"Результаты: experiments/cards/")
    print("=" * 70)
    
    # Проходим по каждому эксперименту из списка
    # enumerate даёт номер (i) и сам эксперимент (exp)
    for i, exp in enumerate(EXPERIMENTS, 1):
        
        print(f"\n[{i}/{len(EXPERIMENTS)}] 🔬 {exp['id']} - {exp['type']}")
        print(f"{exp['note']}")
        print(f" Промпт: {exp['prompt'][:80]}...")
        
        
        result = run_agent(exp['prompt'])
        
        
        filename = save_card(exp, result)
        
        
        status = "УСПЕХ" if result["success"] else "ОШИБКА"
        print(f"    {status} → {filename.name}")
    
    # Финальная сводка
    print("\n" + "=" * 70)
    print("Все эксперименты завершены!")
    print("Смотрите результаты в папке: experiments/cards/")
    print("=" * 70)


if __name__ == "__main__":
    main()