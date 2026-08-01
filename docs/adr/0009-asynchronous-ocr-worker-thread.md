# ADR 0009: Asynchronous Non-blocking OCR Worker Thread

- **Status**: Accepted
- **Date**: 2026-08-01

## Context

當短影片錄製完成進行多影格滑動網格掃描 (Sliding Window Grid Scanning) 時，同步執行全圖 OCR 會花費約 3~8 秒。
若在 PySide6 主 UI 線程中同步執行，會導致畫面凍結 (UI Freeze)，玩家無法在此期間進行任何操作。

## Decision

1. **背景非阻塞 QThread Worker (`OcrWorkerThread`)**：
   - 實作獨立的 `OcrWorkerThread(QThread)`，將短影片影格網格掃描與 WinSDK OCR 辨識移至背景平行線程處理。
2. **預覽視窗秒開 (Instant Modal Display)**：
   - 錄影結束後 **立即彈出** `ReportPreviewModal` 預覽視窗，零等待時間。
   - 玩家可以隨時手動填寫角色 ID、選擇伺服器、變更地圖或備註。
3. **即時候選 ID 動態匯入 (Live Candidate Merging)**：
   - 背景 OCR 線程辨識出候選 ID 時，透過 Signal / Slot 即時將候選項目推播給 `ReportPreviewModal` 的下拉選單 (`id_combo`)。
   - 若玩家已手動輸入文字，系統會保護玩家輸入，不覆蓋使用者正在編輯的內容。

## Consequences

- **優點**:
  - 100% 解決介面卡頓 (UI Freeze) 問題。
  - 兼具極速手動輸入與背景自動辨識之優勢。
