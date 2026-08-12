"""Small, deterministic image and OCR-text preprocessing helpers."""

from __future__ import annotations

from typing import Iterable

from PIL import Image


def normalize_ocr_text(text: str) -> str:
    """Remove OCR whitespace while preserving user-visible characters."""

    return str(text or "").strip().replace(" ", "")


def clean_map_ocr_text(text: str) -> str:
    """Correct recurring MapleStory mini-map glyph substitutions only."""

    value = normalize_ocr_text(text)
    value = value.replace("訓辣", "訓練").replace("訓場", "訓練場")
    if value.endswith(("!", "！")):
        value = f"{value[:-1]}Ⅰ"
    return value


def crop_minimap_region(image: Image.Image) -> Image.Image:
    """Return the top-left region where the mini-map title is rendered."""

    width, height = image.size
    return image.crop((0, 0, int(width * 0.38), int(height * 0.28)))


def bbox_center_y(bbox: Iterable[Iterable[float]]) -> float:
    """Return center Y of an OCR quadrilateral."""

    points = list(bbox)
    if not points:
        return 0.0
    return sum(float(point[1]) for point in points) / len(points)


def bbox_center(bbox: Iterable[Iterable[float]]) -> tuple[float, float]:
    points = list(bbox)
    if not points:
        return 0.0, 0.0
    return (
        sum(float(point[0]) for point in points) / len(points),
        sum(float(point[1]) for point in points) / len(points),
    )


__all__ = [
    "bbox_center",
    "bbox_center_y",
    "clean_map_ocr_text",
    "crop_minimap_region",
    "normalize_ocr_text",
]
