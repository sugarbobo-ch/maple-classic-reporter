# ADR 0005: Workflow, Window Selection & Short Video Recording

- **Status**: Accepted
- **Date**: 2026-08-01

## Context

玩家希望在檢舉外掛前能夠確認與修改辨識出的資料，且外掛違規行為（如自動打怪、飛天吸怪）若以短影片事證舉報效果最佳。玩家可選擇 Google Drive 或 Discord 作為上傳目的地；大容量或官方審查用途建議使用 Google Drive。

## Decision

1. **目標視窗選擇 (Window Target Selection)**:
   - 提供視窗選取器 (Window Selector)，自動列出開啟中的遊戲視窗（如 Unity 引擎驅動之《新楓之谷》視窗），綁定座標與錄影目標。
2. **自動 short-clip 錄影功能**:
   - 支援拍攝截圖或錄製自訂秒數（例如 5~15 秒）短影片 (`.mp4`)。
   - 使用 `mss` + `opencv-python` / `ffmpeg` 進行遊戲視窗局部/全視窗背景錄製。
3. **依目的地上傳並產生連結**:
   - Google Drive 上傳後，程式自動設定 `type='anyone', role='reader'` 公開檢視權限並回傳分享連結。
   - Discord 僅接受 10 MiB 內的短片；超過時提示改用 Google Drive。
4. **發送前預覽編輯 Modal (Pre-submission Edit Modal)**:
   - 回報資料（ID、伺服器、地圖、備註、GDrive 連結）填妥後，顯示確認與編輯彈窗，玩家可修正 OCR 辨識結果或調整備註後再點擊「送出回報」。

## Consequences

- **優點**:
  - 提供極高說服力的影片事證，大幅提高官方封號處理成功率。
  - 確保 GDrive 分享連結全公開，避免營運團隊因權限不足無法開啟事證。
  - 送出前確認機制避免 OCR 錯字或誤發送。
