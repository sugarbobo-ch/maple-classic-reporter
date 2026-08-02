# ADR 0010: Hybrid Dual-OCR Engine (RapidOCR & Gemini Vision API)

- **Status**: Accepted
- **Date**: 2026-08-01

## Context

《新楓之谷：經典版》遊戲字體為 9~10pt 微小點陣像素字 (Pixel-art typography)，深色底框與點陣文字的模糊鋸齒導致 Windows 原生 OCR (OcrEngine) 辨識率無法滿足玩家滿意度。

## Decision

1. **RapidOCR ONNX 本地引擎**：
   - 引入 `rapidocr_onnxruntime` 套件做為本機強化的離線 OCR 引擎，專門處理 9pt 點陣字、綠底白字與區域切片。
2. **Gemini Vision API 手動複核**：
   - AI 僅在使用者於預覽視窗主動要求複核時執行，且每次只分析一張影格。預設流程不會掃描整段影片的所有影格，避免網路延遲阻塞確認作業。
3. **優雅降級 (Graceful Fallback)**：
   - Gemini 是使用者主動觸發的複核功能；未設定 `gemini_api_key` 或網路離線時，預設流程仍使用 RapidOCR 本機引擎。若 RapidOCR 初始化失敗，再退回 Windows OCR 掃描。
4. **預覽視窗 ID 放大圖對照 (ID Magnified Crop Preview)**：
   - 在 `ReportPreviewModal` 彈窗中顯示 ID 畫面的 4x 放大切片圖，供玩家視覺化秒級比對與確權。
5. **獨立發行封裝**：
   - PyInstaller spec 會將 RapidOCR 的 `config.yaml` 與三個 ONNX 模型一起封裝；下載版不依賴 Python、uv 或額外 Chrome。

## Consequences

- **優點**:
  - 本地 RapidOCR 立即提供候選清單；Gemini 作為需要時才使用的精度升級。
  - 提供玩家視覺化圖片比對，大幅提升檢舉體驗。
