"""Small, deterministic image and OCR-text preprocessing helpers."""

from __future__ import annotations

from typing import Iterable

from PIL import Image


try:
    from opencc import OpenCC

    _TO_TRADITIONAL = OpenCC("s2twp")
except ImportError:
    _TO_TRADITIONAL = None


def normalize_ocr_text(text: str) -> str:
    """Remove OCR whitespace and normalize to Traditional Chinese."""

    value = str(text or "").strip().replace(" ", "")
    if _TO_TRADITIONAL:
        value = _TO_TRADITIONAL.convert(value)
    return value


def clean_map_ocr_text(text: str) -> str:
    """Clean mini-map OCR text using OpenCC conversion."""

    return normalize_ocr_text(text)


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
