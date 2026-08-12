"""OCR provider adapters: Windows OCR, RapidOCR and Gemini vision."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
from typing import Callable

import requests
from PIL import Image


LOGGER = logging.getLogger(__name__)
_GEMINI_MODEL = "gemma-4-31b-it"
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

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


def recognize_with_gemini_unified(
    pil_image: Image.Image,
    api_key: str,
    request_post: Callable | None = None,
) -> tuple[list[str], str]:
    """Return player IDs and map name from one Gemini-compatible request."""

    key = str(api_key or "").strip()
    if not key:
        return [], ""

    try:
        buffer = io.BytesIO()
        pil_image.convert("RGB").save(buffer, format="JPEG", quality=85)
        image_b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
        prompt = (
            "這是《新楓之谷：經典版》遊戲截圖。請分析並以 JSON 格式回傳以下兩項資訊：\n"
            "1. \\\"ids\\\": 畫面中所有玩家角色 ID 的陣列（忽略怪物、NPC、裝備、選單文字）。\n"
            "   每個角色標籤由上到下為「角色ID → 公會名稱（若有）→ 勳章名稱（若有）」，"
            "公會名稱和勳章名稱請勿列入 ids。\n"
            "2. \\\"map_name\\\": 畫面左上角小地圖方框內顯示的地圖名稱（中文）。"
            "看不到地圖名稱請填空字串。\n只回傳純 JSON。"
        )
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                ]
            }]
        }
        response = (request_post or requests.post)(
            f"{_GEMINI_BASE}/{_GEMINI_MODEL}:generateContent",
            json=payload,
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
            timeout=12,
        )
        if response.status_code != 200:
            LOGGER.warning("Gemini OCR 回應非成功狀態 (%s)", response.status_code)
            return [], ""

        parts = (
            response.json()
            .get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])
        )
        reply = parts[0].get("text", "") if parts else ""
        if "{" not in reply or "}" not in reply:
            return [], ""
        data = json.loads(reply[reply.find("{") : reply.rfind("}") + 1])
        raw_ids = data.get("ids", [])
        ids = [str(value).strip() for value in raw_ids if str(value).strip()]
        map_name = str(data.get("map_name", "")).strip().replace(" ", "")
        if any(noise in map_name for noise in ("小地圖", "小地畫", "null", "None", "undefined")):
            map_name = ""
        if len(map_name) > 25:
            map_name = ""
        return ids, map_name
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as error:
        LOGGER.warning("Gemini OCR 回應格式無法解析 (%s)", type(error).__name__)
        return [], ""
    except requests.RequestException as error:
        LOGGER.warning("Gemini OCR 網路請求失敗 (%s)", type(error).__name__)
        return [], ""
    except Exception as error:  # pragma: no cover - remote API dependent
        LOGGER.warning("Gemini OCR 失敗 (%s)", type(error).__name__)
        return [], ""


__all__ = [
    "HAS_RAPID_OCR",
    "HAS_WINSDK",
    "RAPID_OCR_ENGINE",
    "recognize_text_from_image",
    "recognize_with_gemini_unified",
]
