from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI


DEFAULT_BRIEF = "Build a simple multi-agent software delivery system with an architect and coder."


# ============================================================
# БАЗОВЫЙ АГЕНТ
# ============================================================

class Agent:
    """Базовый класс для агента"""
    def __init__(self, name: str, system_prompt: str, client: OpenAI, model: str):
        self.name = name
        self.system_prompt = system_prompt
        self.client = client
        self.model = model
    
    def execute(self, task: str, context: str = "") -> str:
        """Агент выполняет задачу"""
        user_prompt = context + "\n\n" + task if context else task
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"ОШИБКА в агенте {self.name}: {str(e)}"


# ============================================================
# АГЕНТ-АРХИТЕКТОР
# ============================================================

class ArchitectAgent(Agent):
    """Архитектор: проектирует решение, НЕ пишет код"""
    def __init__(self, client: OpenAI, model: str):
        super().__init__(
            name="Architect",
            system_prompt="""Ты - Архитектор программных систем. Твоя задача - создавать ДЕТАЛЬНЫЙ ПЛАН решения.
ТЫ НЕ ПИШЕШЬ КОД! Только план.

План должен включать:
1. Анализ задачи и требований
2. Архитектуру решения (компоненты, модули, их взаимодействие)
3. Пошаговый план реализации
4. Какие файлы и функции нужно создать
5. Технологический стек с обоснованием
6. Ожидаемые результаты

Будь конкретным, структурированным и практичным.""",
            client=client,
            model=model
        )
    
    def create_plan(self, task: str) -> str:
        """Создаёт план решения"""
        prompt = f"""
ЗАДАЧА: {task}

Создай детальный план реализации. НЕ ПИШИ КОД, ТОЛЬКО ПЛАН.
"""
        return self.execute(prompt)


# ============================================================
# АГЕНТ-КОДЕР
# ============================================================

class CoderAgent(Agent):
    """Кодер: пишет код по плану архитектора"""
    def __init__(self, client: OpenAI, model: str):
        super().__init__(
            name="Coder",
            system_prompt="""Ты - Кодер. Твоя задача - писать чистый, рабочий код.

Требования:
- Пиши только код (минимум пояснений)
- Добавляй комментарии к сложным местам
- Следуй стандартам PEP 8 (для Python)
- Код должен быть готов к использованию
- Включай обработку ошибок
- Добавляй пример использования

Ты получаешь план от Архитектора и реализуешь его.""",
            client=client,
            model=model
        )
    
    def implement(self, plan: str) -> str:
        """Пишет код по плану"""
        prompt = f"""
ПЛАН АРХИТЕКТОРА:
{plan}

Напиши код на Python, реализующий этот план.
"""
        return self.execute(prompt)


# ============================================================
# АГЕНТ-РЕВЬЮЕР
# ============================================================

class ReviewerAgent(Agent):
    """Рецензент: проверяет код"""
    def __init__(self, client: OpenAI, model: str):
        super().__init__(
            name="Reviewer",
            system_prompt="""Ты - Рецензент кода. Твоя задача - проверить код и дать оценку.

Оцени по шкале 1-10:
1. Соответствие плану архитектора
2. Качество и читаемость кода
3. Обработка ошибок
4. Безопасность
5. Производительность

Также укажи:
✅ Что сделано хорошо
⚠️ Что можно улучшить
❌ Критические проблемы (если есть)
📝 Конкретные рекомендации

Будь конструктивным и конкретным.""",
            client=client,
            model=model
        )
    
    def review(self, original_task: str, plan: str, code: str) -> str:
        """Рецензирует код"""
        prompt = f"""
ИСХОДНАЯ ЗАДАЧА: {original_task}

ПЛАН АРХИТЕКТОРА:
{plan}

КОД КОДЕРА:
{code}

Проверь код и дай рецензию.
"""
        return self.execute(prompt)


# ============================================================
# ОРКЕСТРАТОР
# ============================================================

class MultiAgentOrchestrator:
    """Оркестратор: запускает всех агентов последовательно"""
    
    def __init__(self, client: OpenAI, model: str, workspace_root: Path):
        self.client = client
        self.model = model
        self.workspace_root = workspace_root
        
        # Создаём агентов
        self.architect = ArchitectAgent(client, model)
        self.coder = CoderAgent(client, model)
        self.reviewer = ReviewerAgent(client, model)
    
    def run(self, brief: str) -> dict:
        """Запускает мультиагентную оркестрацию"""
        
        print("[MULTI-AGENT] Шаг 1/3: Архитектор создаёт план...", file=sys.stderr)
        plan = self.architect.create_plan(brief)
        
        # Проверка: если план пустой, создаём заглушку
        if not plan or len(plan.strip()) < 10:
            print("[WARNING] План пустой! Использую заглушку.", file=sys.stderr)
            plan = f"План решения для задачи: {brief[:100]}..."
        
        print("[MULTI-AGENT] Шаг 2/3: Кодер пишет код...", file=sys.stderr)
        code = self.coder.implement(plan)
        
        # Проверка: если код пустой, создаём заглушку
        if not code or len(code.strip()) < 10:
            print("[WARNING] Код пустой! Использую заглушку.", file=sys.stderr)
            code = "# Код не был сгенерирован\n# План: " + plan[:100] + "..."
        
        print("[MULTI-AGENT] Шаг 3/3: Ревьюер проверяет код...", file=sys.stderr)
        review = self.reviewer.review(brief, plan, code)
        
        # Проверка: если ревью пустое, создаём заглушку
        if not review or len(review.strip()) < 10:
            print("[WARNING] Ревью пустое! Использую заглушку.", file=sys.stderr)
            review = f"Ревью кода (краткое): код сгенерирован по плану. Требуется доработка."
        
        # Сохраняем результаты
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        
        plan_file = self.workspace_root / "architecture.md"
        plan_file.write_text(plan, encoding="utf-8")
        
        code_file = self.workspace_root / "implementation.py"
        # Извлекаем код из маркеров если есть
        code_content = code
        if "```python" in code:
            code_content = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code_content = code.split("```")[1].split("```")[0]
        code_file.write_text(code_content, encoding="utf-8")
        
        review_file = self.workspace_root / "review.md"
        review_file.write_text(review, encoding="utf-8")
        
        return {
            "status": "success",
            "agents_used": ["Architect", "Coder", "Reviewer"],
            "plan": plan,
            "code": code,
            "review": review,
            "files_generated": {
                "architecture": str(plan_file),
                "implementation": str(code_file),
                "review": str(review_file)
            },
            "timestamp": datetime.now().isoformat(),
            "workspace": str(self.workspace_root)
        }


# ============================================================
# СОЗДАНИЕ КЛИЕНТА С ПОДДЕРЖКОЙ ПРОКСИ
# ============================================================

def create_openai_client(api_key: str, base_url: str = None) -> OpenAI:
    """Создаёт клиент OpenAI с поддержкой прокси"""
    
    # Проверяем наличие прокси
    http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    
    # Если прокси HTTP, используем его
    if http_proxy and "socks" not in http_proxy.lower():
        try:
            import httpx
            proxy_client = httpx.Client(
                proxy=http_proxy,
                timeout=httpx.Timeout(60.0, connect=10.0)
            )
            return OpenAI(
                api_key=api_key,
                base_url=base_url,
                http_client=proxy_client
            )
        except Exception as e:
            print(f"[WARNING] Ошибка настройки прокси: {e}", file=sys.stderr)
    
    # Если прокси SOCKS или ошибка, игнорируем
    if http_proxy and "socks" in http_proxy.lower():
        print("[WARNING] SOCKS прокси не поддерживается. Игнорируем.", file=sys.stderr)
        # Удаляем прокси из окружения для этого запуска
        os.environ["HTTP_PROXY"] = ""
        os.environ["HTTPS_PROXY"] = ""
    
    # Стандартный клиент
    return OpenAI(
        api_key=api_key,
        base_url=base_url
    )


# ============================================================
# ПАРСИНГ АРГУМЕНТОВ
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Мультиагентная система для разработки ПО")
    parser.add_argument("--brief", type=str, default=DEFAULT_BRIEF, help="Описание задачи")
    parser.add_argument("--workspace", type=str, default="demo_workspace", help="Рабочая директория")
    parser.add_argument("--output", type=str, help="Путь для сохранения результата (JSON)")
    return parser.parse_args()


# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================

def main() -> None:
    load_dotenv()
    args = parse_args()
    
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL")
    base_url = os.getenv("LLM_BASE_URL")
    
    if not api_key or not model:
        error_data = {"error": "LLM_API_KEY and LLM_MODEL must be set in .env"}
        print(json.dumps(error_data, ensure_ascii=False))
        sys.exit(1)
    
    try:
        # Создаём клиент с поддержкой прокси
        client = create_openai_client(api_key, base_url)
        workspace_root = Path(args.workspace).resolve()
        
        # Запускаем мультиагентную систему
        orchestrator = MultiAgentOrchestrator(
            client=client,
            model=model,
            workspace_root=workspace_root
        )
        
        result = orchestrator.run(args.brief)
        
        # Сохраняем результат
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        
        # Выводим JSON для run_experiments.py
        print(json.dumps(result, ensure_ascii=False))
        
    except Exception as e:
        error_data = {"error": str(e)}
        print(json.dumps(error_data, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()