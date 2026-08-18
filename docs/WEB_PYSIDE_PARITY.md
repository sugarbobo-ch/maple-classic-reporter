# React／PyWebView 與舊 PySide 功能一致性

逐項操作比對的最新可執行矩陣與實作狀態請見 [`UI_PARITY_OPERATIONS.md`](UI_PARITY_OPERATIONS.md)。本文件保留較高層的功能與實機驗證總覽。

React 是目前預設入口；PySide 仍以 `--pyside` 保留作為相容入口。兩者共用錄影、OCR、回放、上傳與設定的 Python 服務，React 透過 `PyWebViewBridge` 呼叫這些服務。

| 能力 | React／PyWebView | 舊 PySide | 目前驗證狀態 |
| --- | --- | --- | --- |
| 手動錄影、取消、進度 | `App` → `start_recording`／`cancel_recording` | `MainWindow` 錄影流程 | React UI mock 測試；真實遊戲視窗待人工驗證 |
| 回放緩衝、停止、儲存 | `App` → `start_replay`／`stop_replay`／`save_replay` | `ReplayController` | Python bridge／回放單元測試；真實音訊與遊戲待人工驗證 |
| OCR ID／地圖 | `PyWebViewBridge._perform_ocr` → `OCR_STATUS`／`OCR_RESULT` | 舊預覽／OCR worker 流程 | Python 開關測試與 React 事件流程測試；真實畫面待人工驗證 |
| 事證剪輯與還原 | `ReportFlowModal` → `trim_video_segment`／`restore_original_video` | 舊 PySide 影片流程 | React 已測試剪輯後路徑會送出；真實影片編碼待人工驗證 |
| Drive 授權、資料夾、上傳 | `SettingsView`／`App` → Drive bridge API | `MainWindow`／`GoogleDriveManager` | 授權真值與 mock API 已測試；真實 OAuth／上傳待 smoke |
| Discord Webhook | `SettingsView`／`submit_report` | `SubmissionController`／Discord service | URL 邊界與 mock API 已測試；真實 Webhook 待 smoke |
| SurveyCake 填表與成功判定 | `submit_report` → Playwright | `SubmissionController` → Playwright | Python 成功／失敗判定已測試；真實帳號送出待明確授權後 smoke |
| 提交失敗、重試、歷史 | `ReportFlowModal`／`HistoryView` | PySide history／submission widgets | React 已測試失敗保留表單、歷史清除、開啟／複製連結 |
| 設定與開關 | `SettingsView` → `save_config_key` | `SettingsController` | React OCR 開關、Drive 狀態與失敗 rollback 已測試 |
| 全域快捷鍵 | PyWebView bridge 的 native hotkey listener | PySide global hotkey manager | Python 邊界測試；Windows 實機註冊與衝突待人工驗證 |
| 無框視窗、拖曳、Snap、工作列圖示 | React/PyWebView + Win32 native window | Qt 原生視窗 | Python/native 單元測試；Windows 實機 Snap／工作列待人工驗證 |

## 自動化入口

- React UI：`cd web; npm test`
- React 型別：`cd web; npm run test:types`
- Python API 契約：`python -m unittest tests.test_webview_contract`
- 真實服務：`uv run python scripts/real_e2e_smoke.py --help`。預設拒絕執行，必須明確設定環境變數與允許旗標。
- 發行包靜態檢查／smoke：`uv run python scripts/verify_release_bundle.py --help`；建置前需先準備未納入 Git 的 `build_secrets/google_oauth_client.json`。

## 尚不能由本機 mock 證明的項目

Mock Bridge 只驗證前端狀態、參數與錯誤處理，不代表第三方服務或硬體成功。真實 OAuth、Discord、SurveyCake 送出、遊戲視窗、音訊、OCR、快捷鍵、Windows Snap，以及帶真實 OAuth 設定的 PyInstaller 啟動，仍需在具備帳號／硬體／Windows 桌面的環境中執行對應 smoke 或人工檢查。
