# ADR 0002: OCR Engine Selection

- **Status**: Superseded by ADR 0010
- **Date**: 2026-08-01

## Context

《新楓之谷：經典版》的外掛角色 ID 常包含特殊符號或亂碼，需要從遊戲螢幕截圖中準確辨識文字。

## Decision

以 **RapidOCR ONNX** 作為主要本機文字辨識引擎，並保留 **Windows 原生 API (`Windows.Media.Ocr` / `winsdk`)** 作為 RapidOCR 無法初始化時的 fallback。

## Consequences

- **優點**:
  - RapidOCR 對遊戲點陣字與英數角色 ID 的辨識效果較佳，且可離線執行。
  - Windows OCR 保留作為不依賴 RapidOCR 模型的 Windows fallback。
  - 發行版透過 PyInstaller 將 RapidOCR 的 ONNX 模型一併封裝，使用者不需另外下載模型。
- **缺點**:
  - RapidOCR 模型會增加 EXE 體積；Windows OCR fallback 僅限 Windows 作業系統。
