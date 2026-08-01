"""Offline matching of OCR output against known Traditional Chinese map names."""
import json
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Optional

try:
    from opencc import OpenCC
    _TO_TRADITIONAL = OpenCC("s2twp")
except ImportError:  # Keeps the local OCR usable if an old install lacks OpenCC.
    _TO_TRADITIONAL = None

_CATALOG_PATH = Path(__file__).with_name("data") / "map_names_zh.json"
_SPACE_RE = re.compile(r"\s+")


def normalize_map_name(value: str) -> str:
    """Normalise OCR variants such as full-width digits and Roman numerals."""
    text = unicodedata.normalize("NFKC", value or "")
    if _TO_TRADITIONAL:
        text = _TO_TRADITIONAL.convert(text)
    return _SPACE_RE.sub("", text).upper()


@lru_cache(maxsize=1)
def load_map_names() -> tuple[str, ...]:
    try:
        data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        return tuple(name for name in data.get("maps", []) if isinstance(name, str) and name.strip())
    except (OSError, ValueError, TypeError):
        return ()


def best_map_name_match(ocr_text: str) -> tuple[Optional[str], float]:
    """Return the closest catalogue name and its similarity score."""
    query = normalize_map_name(ocr_text)
    if len(query) < 2:
        return None, 0.0

    best_name = None
    best_score = 0.0
    for candidate in load_map_names():
        score = SequenceMatcher(None, query, normalize_map_name(candidate)).ratio()
        if score > best_score:
            best_name, best_score = candidate, score
    return best_name, best_score


def resolve_map_name(ocr_text: str, minimum_score: float = 0.76) -> Optional[str]:
    """Return the closest catalogue name when the OCR result is sufficiently similar."""
    name, score = best_map_name_match(ocr_text)
    return name if name and score >= minimum_score else None
