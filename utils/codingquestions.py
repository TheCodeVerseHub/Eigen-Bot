import copy
import json
import random
from pathlib import Path
from typing import Dict, List, Optional

DATA_PATH = Path(__file__).parent / "../cogs/data/coding_questions.json"

with open(DATA_PATH, "r", encoding="utf-8") as f:
    HARD_QUESTIONS: List[Dict] = json.load(f)

if not HARD_QUESTIONS:
    raise RuntimeError("coding_questions.json is empty")

# Keep a normalized language/category index for fast filtered retrieval.
# Example key: "system design", "python", "java"
_questions_by_language: Dict[str, List[Dict]] = {}
for q in HARD_QUESTIONS:
    lang = str(q.get("language", "General")).strip().lower()
    _questions_by_language.setdefault(lang, []).append(q)

# Non-repeating global question pool
_question_pool: List[Dict] = HARD_QUESTIONS.copy()
random.shuffle(_question_pool)
_index = 0


def _normalize_category(category: Optional[str]) -> Optional[str]:
    """Normalize category/language user input."""
    if category is None:
        return None
    normalized = category.strip().lower().replace("_", " ").replace("-", " ")
    return " ".join(normalized.split()) or None


def get_available_categories() -> List[str]:
    """Return sorted list of available language/category names."""
    return sorted(_questions_by_language.keys())


def get_random_question() -> Dict:
    """Return a non-repeating randomized question from all questions."""
    global _index

    if _index >= len(_question_pool):
        random.shuffle(_question_pool)
        _index = 0

    q = copy.deepcopy(_question_pool[_index])
    _index += 1
    return fix_question(q)


def get_random_question_by_category(category: str) -> Optional[Dict]:
    """
    Return one randomized question for a specific category/language.

    The lookup is case-insensitive and accepts underscores/hyphens as spaces.
    Returns None if category is invalid or has no questions.
    """
    key = _normalize_category(category)
    if not key:
        return None

    matched = _questions_by_language.get(key)
    if not matched:
        return None

    q = copy.deepcopy(random.choice(matched))
    return fix_question(q)


def fix_question(question: Dict) -> Dict:
    """Randomize options while keeping the correct answer accurate."""
    correct_letter = question["correct"]
    correct_idx = ord(correct_letter) - ord("a")
    correct_text = question["options"][correct_idx]

    random.shuffle(question["options"])
    question["correct"] = chr(question["options"].index(correct_text) + ord("a"))

    return question
