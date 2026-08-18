# React／PyWebView 與舊 PySide 操作比對

本文件描述兩個入口實際共用與各自保留的操作邊界。React／PyWebView 是預設入口；舊 PySide 仍可用 `--pyside` 啟動。這不是把兩套 UI 做成相同畫面，而是用相同設定、媒體、送出資料與安全規則驗證使用者操作結果。

## 可執行的逐項比對

執行：

```powershell
uv run python -m unittest tests.test_ui_parity -v
```

| 操作 | React／PyWebView | 舊 PySide | 比對結果 |
| --- | --- | --- | --- |
| OCR ID／地圖開關與白名單 | `SettingsView` → `save_config_key`；`PyWebViewBridge` OCR | `SettingsController` → `OcrWorkerThread` | 已自動比對相同 OCR 結果與過濾規則 |
| 一般錄影參數 | `start_recording` | `EvidenceCaptureController.record_video` | 已比對視窗、秒數、FPS、音訊參數 |
| 回放開始／停止 | `start_replay`／`stop_replay` | `ReplayController.start`／`stop` | 已比對 recorder 呼叫參數與生命週期 |
| 背景靜默送出 | `form_submit_headless` | PySide 設定開關與 `SubmitThread` | 已接上同一設定；已自動比對 |
| 開發者 Dry-Run | `dev_mode` | PySide 設定開關與 `SubmitThread` | 兩邊都不呼叫真正 SurveyCake；已自動比對 |
| 檢舉表單 payload | `submit_report` | `SubmitThread` | 已比對 ID、伺服器、地圖、備註、事證 URL、headless |
| 歷史紀錄開啟連結 | `HistoryView` → `open_external_url` | 歷史表格點擊／雙擊 | 都只允許安全 HTTPS |
| 歷史紀錄複製連結 | React clipboard bridge | PySide「複製選取連結」 | 已補上並自動比對安全 URL 邊界 |
| 歷史紀錄清空 | `clear_history` | PySide「清空紀錄」 | 都在確認後清除持久化歷史 |
| 快捷連結新增／編輯／刪除／排序／開啟 | `SettingsView`／首頁快捷連結 | PySide 快捷連結表格與 `QuickLinksController` | 已補上；URL 正規化與安全開啟規則一致 |
| 設定儲存失敗 | React 重新讀取後端設定 | PySide `SettingsController` 重新載入後端設定 | 已補上 rollback 與錯誤提示 |

React UI 案例位於 `web/tests/`；跨入口 Python 案例位於 `tests/test_ui_parity.py`。測試使用 `tests/fixtures/config.json`，不讀取使用者設定，也不使用真正錄影資料夾。

## 尚未宣稱完全一致的項目

- React 的影片剪輯／還原目前只在 PyWebView `ReportFlowModal` 提供；舊 PySide 預覽窗仍只有播放／預覽，尚未補同一套時間軸剪輯 UI。
- React 會顯示 `SUBMISSION_STATUS` 的上傳／填表進度；舊 PySide 目前顯示最終結果，沒有同樣的逐步事件畫面。
- 真實 Google OAuth／Drive、Discord Webhook、Gamania／SurveyCake、遊戲視窗、音訊、OCR、全域快捷鍵與 Windows Snap／工作列，仍須在 Windows 實機以真實帳號或硬體驗證。
- PySide 與 React 使用不同的視窗框架，因此無框拖曳、縮放、最大化與 Snap 的實作不同；比對的是可觀察結果，不是內部 API 相同。

## 相關驗證命令

```powershell
uv run python -m unittest tests.test_ui_parity -v
uv run python -m unittest discover -s tests -b -q
cd web
npm test
npm run test:types
npm run build
```
