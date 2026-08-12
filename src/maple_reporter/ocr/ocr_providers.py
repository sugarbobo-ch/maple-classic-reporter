"""OCR provider adapters for Windows OCR and RapidOCR."""

from __future__ import annotations

import asyncio
import io
import logging

from PIL import Image


LOGGER = logging.getLogger(__name__)

try:  # Optional on non-Windows test hosts.
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter

    HAS_WINSDK = True
except ImportError:  # pragma: no cover - platform dependent
    HAS_WINSDK = False

try:
    from rapidocr_onnxruntime import RapidOCR

    RAPID_OCR_ENGINE = RapidOCR()
    HAS_RAPID_OCR = True
except Exception as error:  # pragma: no cover - model/runtime dependent
    LOGGER.warning("RapidOCR 初始化失敗 (%s)", type(error).__name__)
    RAPID_OCR_ENGINE = None
    HAS_RAPID_OCR = False


async def _async_windows_ocr(pil_image: Image.Image) -> str:
    image_buffer = io.BytesIO()
    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")
    pil_image.save(image_buffer, format="PNG")

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(bytearray(image_buffer.getvalue()))
    await writer.store_async()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()

    engine = OcrEngine.try_create_from_user_profile_languages()
    if not engine:
        languages = list(OcrEngine.available_recognizer_languages)
        if languages:
            engine = OcrEngine.try_create_from_language(languages[0])
    if not engine:
        return ""
    result = await engine.recognize_async(bitmap)
    raw_text = "".join(line.text for line in result.lines)
    return raw_text.replace(" ", "") or raw_text


def recognize_text_from_image(pil_image: Image.Image) -> str:
    if not HAS_WINSDK:
        return ""
    try:
        return asyncio.run(_async_windows_ocr(pil_image))
    except Exception as error:  # pragma: no cover - Windows OCR dependent
        LOGGER.debug("Windows OCR 失敗 (%s)", type(error).__name__)
        return ""


__all__ = [
    "HAS_RAPID_OCR",
    "HAS_WINSDK",
    "RAPID_OCR_ENGINE",
    "recognize_text_from_image",
]
