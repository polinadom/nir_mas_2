"""
ОЦЕНЩИК КАЧЕСТВА
Измеряет, насколько упало качество после внесения бага
"""

import re
from typing import Any, Dict, List, Optional, Union

ResponseInput = Union[str, Dict[str, Any], None]

# Термины из SWE-bench патчей и типичных фиксов
_PATCH_HINT_TERMS = {
    "def", "class", "import", "return", "if", "elif", "else", "for", "while",
    "try", "except", "raise", "pass", "async", "await", "yield",
}

_SWE_DOMAIN_TERMS = {
    "pydantic", "dataclass", "fastapi", "route", "router", "endpoint",
    "websocket", "middleware", "dependency", "validator", "schema",
    "response_model", "request", "openapi", "uvicorn", "starlette",
    "httpx", "json", "serialize", "validation", "type", "typing",
}


class QualityChecker:
    """Оценивает качество ответа MAS"""

    @staticmethod
    def _as_dict(response: ResponseInput) -> Dict[str, Any]:
        if isinstance(response, dict):
            return response
        if response:
            return {"result": str(response)}
        return {}

    @staticmethod
    def extract_text(response: ResponseInput) -> str:
        """Собирает текст из структуры MAS (plan+code+review) или plain string."""
        if isinstance(response, str):
            return response
        if not isinstance(response, dict):
            return str(response) if response else ""

        parts = []
        for key in ("plan", "code", "review", "result"):
            val = response.get(key)
            if val and str(val).strip():
                parts.append(str(val))
        return "\n\n".join(parts)

    @staticmethod
    def _component_flags(response: ResponseInput) -> Dict[str, bool]:
        data = QualityChecker._as_dict(response)
        if not data and isinstance(response, str) and response.strip():
            text = response
            has_code = "```" in text or "def " in text or "class " in text
            return {
                "has_plan": len(text) > 80 and not has_code,
                "has_code": has_code,
                "has_review": False,
            }
        return {
            "has_plan": bool(data.get("plan") and str(data["plan"]).strip()),
            "has_code": bool(data.get("code") and str(data["code"]).strip()),
            "has_review": bool(data.get("review") and str(data["review"]).strip()),
        }

    @staticmethod
    def _agent_completeness(flags: Dict[str, bool]) -> float:
        return sum(flags.values()) / 3.0

    @staticmethod
    def _keyword_coverage(text: str, keywords: List[str]) -> float:
        if not keywords:
            return 1.0
        matched = sum(1 for kw in keywords if kw.lower() in text.lower())
        return matched / len(keywords)

    @staticmethod
    def _extract_problem_terms(prompt: str) -> List[str]:
        """Извлекает значимые термины из описания SWE-bench задачи."""
        terms = set()
        lower = prompt.lower()

        for term in _SWE_DOMAIN_TERMS:
            if term in lower:
                terms.add(term)

        # Идентификаторы из кода в issue (Foo, get_bar, response_model)
        for match in re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", prompt):
            if len(match) > 2:
                terms.add(match.lower())

        for match in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\b", prompt):
            if match.lower() not in {"the", "and", "for", "with", "from", "this", "that", "error"}:
                if any(c.isupper() for c in match) or "_" in match:
                    terms.add(match.lower())

        return sorted(terms)

    @staticmethod
    def _extract_patch_terms(patch: str) -> List[str]:
        """Извлекает термины из git-патча (файлы, функции, символы)."""
        if not patch:
            return []

        terms = set()
        for line in patch.splitlines():
            if line.startswith("+++") or line.startswith("---"):
                path = line.split("/", 1)[-1].strip()
                if path.endswith(".py"):
                    terms.add(path.replace(".py", "").lower())
            elif line.startswith("+") and not line.startswith("+++"):
                content = line[1:].strip()
                for match in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", content):
                    if match in _PATCH_HINT_TERMS or len(match) > 4:
                        terms.add(match.lower())
                for match in re.findall(r"def\s+([A-Za-z_][A-Za-z0-9_]*)", content):
                    terms.add(match.lower())

        return sorted(terms)

    @staticmethod
    def _swe_terms(prompt: str, swe_metadata: Optional[Dict[str, Any]]) -> List[str]:
        terms = set(QualityChecker._extract_problem_terms(prompt))
        if swe_metadata:
            patch = swe_metadata.get("patch", "")
            terms.update(QualityChecker._extract_patch_terms(patch))
            repo = swe_metadata.get("repo", "")
            if repo:
                terms.add(repo.split("/")[-1].lower())
        return sorted(terms)

    @staticmethod
    def _code_block_quality(text: str) -> float:
        if not text:
            return 0.0
        if "```" in text:
            blocks = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
            if blocks:
                avg_len = sum(len(b.strip()) for b in blocks) / len(blocks)
                return min(1.0, avg_len / 120.0)
        if "def " in text or "class " in text:
            return 0.6
        return 0.0

    @staticmethod
    def score_component(text: str, expected_keywords: List[str]) -> float:
        """Оценка одного компонента (plan / code / review) от 0 до 1."""
        if not text or len(text.strip()) < 10:
            return 0.0

        kw_cov = QualityChecker._keyword_coverage(text, expected_keywords)
        code_q = QualityChecker._code_block_quality(text)
        length_bonus = 1.0 if len(text) > 200 else (0.5 if len(text) > 80 else 0.0)

        return min(1.0, 0.5 * kw_cov + 0.3 * code_q + 0.2 * length_bonus)

    @staticmethod
    def score(
        response: ResponseInput,
        expected_keywords: List[str],
        swe_metadata: Optional[Dict[str, Any]] = None,
        prompt: Optional[str] = None,
    ) -> float:
        """
        Оценивает качество ответа от 0 до 1.
        Принимает plain string или dict {plan, code, review, ...}.
        """
        text = QualityChecker.extract_text(response)
        if not text or len(text) < 20:
            flags = QualityChecker._component_flags(response)
            if not any(flags.values()):
                return 0.0

        flags = QualityChecker._component_flags(response)
        agent_completeness = QualityChecker._agent_completeness(flags)
        keyword_coverage = QualityChecker._keyword_coverage(text, expected_keywords)

        swe_terms: List[str] = []
        swe_coverage = 0.0
        if swe_metadata or (
            prompt and ("fastapi" in prompt.lower() or "pydantic" in prompt.lower())
        ):
            swe_terms = QualityChecker._swe_terms(prompt or text, swe_metadata)
            if swe_terms:
                swe_coverage = QualityChecker._keyword_coverage(text, swe_terms)

        code_quality = QualityChecker._code_block_quality(text)
        length_bonus = 1.0 if len(text) > 200 else (0.5 if len(text) > 80 else 0.0)

        # Взвешенная комбинация
        score = (
            0.25 * keyword_coverage
            + 0.20 * agent_completeness
            + 0.20 * code_quality
            + 0.10 * length_bonus
        )
        if swe_terms:
            score += 0.25 * swe_coverage
        else:
            score += 0.25 * keyword_coverage

        return min(1.0, score)

    @staticmethod
    def degradation(clean_score: float, buggy_score: float) -> dict:
        """
        Вычисляет падение качества из-за бага.
        Отрицательное падение (шум метрики) обнуляется.
        """
        absolute_loss = max(0.0, clean_score - buggy_score)

        if clean_score > 0:
            percent_loss = (absolute_loss / clean_score) * 100
        else:
            percent_loss = 100.0 if buggy_score < clean_score else 0.0

        return {
            "clean_score": round(clean_score, 3),
            "buggy_score": round(buggy_score, 3),
            "absolute_loss": round(absolute_loss, 3),
            "loss_percent": round(percent_loss, 1),
            "is_robust": percent_loss < 20,
            "is_vulnerable": percent_loss > 50,
        }

    @staticmethod
    def analyze(
        response: ResponseInput,
        expected_keywords: List[str],
        swe_metadata: Optional[Dict[str, Any]] = None,
        prompt: Optional[str] = None,
    ) -> dict:
        """Детальный анализ ответа MAS."""
        text = QualityChecker.extract_text(response)
        data = QualityChecker._as_dict(response)
        flags = QualityChecker._component_flags(response)
        swe_terms = QualityChecker._swe_terms(prompt or text, swe_metadata)

        component_scores = {}
        for name in ("plan", "code", "review"):
            comp_text = data.get(name, "")
            if comp_text:
                component_scores[name] = round(
                    QualityChecker.score_component(str(comp_text), expected_keywords), 3
                )

        keyword_coverage = QualityChecker._keyword_coverage(text, expected_keywords)
        swe_coverage = (
            QualityChecker._keyword_coverage(text, swe_terms) if swe_terms else None
        )

        return {
            "length": len(text),
            "has_plan": flags["has_plan"],
            "has_code": flags["has_code"],
            "has_review": flags["has_review"],
            "agent_completeness": round(QualityChecker._agent_completeness(flags), 3),
            "keyword_coverage": round(keyword_coverage, 3),
            "swe_term_coverage": round(swe_coverage, 3) if swe_coverage is not None else None,
            "swe_terms_checked": swe_terms[:20],
            "has_code_blocks": "```" in text or "def " in text or "class " in text,
            "has_keywords": [kw for kw in expected_keywords if kw.lower() in text.lower()],
            "missing_keywords": [kw for kw in expected_keywords if kw.lower() not in text.lower()],
            "component_scores": component_scores,
            "score": round(
                QualityChecker.score(response, expected_keywords, swe_metadata, prompt), 3
            ),
        }

    @staticmethod
    def analyze_response(
        response: ResponseInput,
        expected_keywords: List[str],
        swe_metadata: Optional[Dict[str, Any]] = None,
        prompt: Optional[str] = None,
    ) -> dict:
        """Алиас для analyze() — совместимость с run_robustness_test."""
        return QualityChecker.analyze(response, expected_keywords, swe_metadata, prompt)
