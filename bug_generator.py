"""
ГЕНЕРАТОР БАГОВ (FAULT INJECTION)
Создаёт деградацию входных данных
"""

import random
import string

class BugGenerator:
    """Генерирует баги разного типа и интенсивности"""
    
    # Уровни интенсивности (какой % данных портим)
    INTENSITY = {
        "low": 0.1,      # 10% повреждения
        "medium": 0.3,   # 30% повреждения
        "high": 0.6      # 60% повреждения
    }
    
    @staticmethod
    def incomplete(text: str, level: str = "medium") -> str:
        """НЕПОЛНОТА: удаляет часть слов"""
        factor = BugGenerator.INTENSITY.get(level, 0.3)
        
        words = text.split()
        if len(words) == 0:
            return text
        
        keep_count = max(1, int(len(words) * (1 - factor)))
        
        # Удаляем случайные слова
        indices = list(range(len(words)))
        random.shuffle(indices)
        keep_indices = sorted(indices[:keep_count])
        kept_words = [words[i] for i in keep_indices]
        
        result = ' '.join(kept_words)
        
        markers = ["...", "[пропущено]", "[неполные данные]"]
        return result + " " + random.choice(markers)
    
    @staticmethod
    def noise(text: str, level: str = "medium") -> str:
        """ШУМ: добавляет мусорные символы"""
        factor = BugGenerator.INTENSITY.get(level, 0.3)
        
        noise_types = [
            lambda: ''.join(random.choices(string.ascii_lowercase, k=int(5 * (1 + factor)))),
            lambda: random.choice(["asdf", "qwerty", "12345", "####", "@@@"]) * int(1 + factor * 3),
            lambda: random.choice(["шум", "мусор", "ошибка", "noise"]) * int(1 + factor * 2)
        ]
        
        noise = random.choice(noise_types)()
        
        if random.random() > 0.5:
            return noise + " " + text
        else:
            return text + " " + noise
    
    @staticmethod
    def contradiction(text: str, level: str = "medium") -> str:
        """ПРОТИВОРЕЧИЕ: добавляет невозможное требование"""
        contradictions = [
            "но не используй циклы",
            "однако сделай это без рекурсии",
            "при этом не используй стандартные библиотеки",
            "но сделай максимально неэффективно",
            "однако программа не должна ничего возвращать"
        ]
        
        if level == "high":
            contradiction = random.choice(contradictions) + " (это обязательно)"
        elif level == "medium":
            contradiction = random.choice(contradictions)
        else:
            contradiction = random.choice(contradictions[:2]) + " (если возможно)"
        
        return text + " " + contradiction
    
    # ============================================================
    # ГЛАВНЫЙ МЕТОД generate (тот, который вызывает run_experiments)
    # ============================================================
    @staticmethod
    def generate(text: str, bug_type: str, level: str = "medium") -> str:
        """Главный метод: создаёт баг заданного типа"""
        if bug_type == "incomplete":
            return BugGenerator.incomplete(text, level)
        elif bug_type == "noise":
            return BugGenerator.noise(text, level)
        elif bug_type == "contradiction":
            return BugGenerator.contradiction(text, level)
        else:
            return text