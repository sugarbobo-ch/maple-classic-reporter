# Maple Classic Auto Reporter - Domain Context

## Current Release

- **Version**: `0.1.2`
- **Windows release**: `MapleClassicReporter-v1.0.0-windows-x64.zip`
- **Distribution**: ZIP contains only `MapleClassicReporter.exe`; Playwright Chromium, its driver, and RapidOCR ONNX models are bundled inside the executable.
- **Runtime fallback**: The application checks bundled Playwright Chromium first, uses a local Playwright cache as fallback, and shows a copy-friendly error dialog with the official download URL when both are unavailable.

## Glossary & Ubiquitous Language

- **Auto Reporter (自動檢舉器)**: 專為《新楓之谷：經典版》打造之外掛自動化檢舉桌面工具。
- **Suspect ID (外掛角色 ID)**: 遊戲內疑似外掛玩家的角色名稱。因字元特殊或隨機亂碼，支援透過螢幕截圖 / 畫面框選結合 OCR 自動辨識。
- **Game Server (遊戲伺服器)**: 外掛角色所在之伺服器（現有：雪吉拉、菇菇寶貝）。
- **Map Name (所在地圖)**: 外掛角色當前出現的遊戲地圖名稱。優先從遊戲視窗左上角小地圖辨識；若小地圖隱藏，會改掃描畫面中其他可見的地圖名稱，無結果時保留可編輯欄位供使用者更新。
- **Dual Region OCR Map Name Auto-Fill (雙區塊地圖與 ID 分離辨識)**: 針對左上角小地圖區塊 (X: 0~35%, Y: 0~25%) 自動辨識地圖名稱 (如 `魔法森林北郊`) 並自動預填至彈窗的「3. 所在地圖名稱」，同時從小地圖外選單排除該文字，避免地圖名稱污染外掛 ID 欄位。
- **Image Preprocessing Pipeline (圖像預處理管道)**: 針對遊戲小字體與複雜背景，進行 2.5 倍放大與黑白高對比二值化之 OpenCV 前處理，顯著提昇 OCR 辨識率。
- **Multi-Frame Video OCR (多影格抽幀 OCR)**: 錄影期間定時抽影格進行 OCR 辨識，並於預覽彈窗提供可編輯下拉選單 (Editable Suspect ID ComboBox) 供玩家選擇。
- **Asynchronous OCR Worker Thread (非阻塞背景 OCR 線程)**: 將 OCR 辨識移至背景 `QThread` 執行，預覽彈窗秒開不卡頓，並即時動態推播辨識到的候選 ID。
- **Recording FPS (錄影幀率)**: 可自訂短影片錄製順暢度之每秒幀率 (15~60 FPS)。
- **Auto-Remember Defaults (預設值自動記憶)**: 自動記憶玩家上次選取/填寫之伺服器、地圖、備註、視窗等設定值並持久化於設定檔。
- **Client Area Bounds (視窗畫布邊界)**: 透過 Win32 `GetClientRect` 精準計算除外標題列與外框後的真實遊戲視窗畫布區域。
- **UI Exclusion & Basic Filtering (UI 排除與基礎過濾)**: 自動排除純數字傷害值、語法標點符號 (`/`, `+`, `:`) 與通用系統 UI 標籤 (`HP`, `MP`, `EXP`, `Lv`, `CH`)。
- **Dynamic Whitelist System (動態 ID 白名單過濾機制)**: 主介面與預覽彈窗皆可加入白名單；設定會持久化並在未來掃描時自動過濾。
- **Evidence Media (檢舉事證媒體)**: 外掛違規行為之圖片（PNG/JPG）或影片連結。
- **Evidence Destination (事證目的地)**: 使用者在 Google Drive 與 Discord Webhook 間二選一。Google Drive 適合長期官方審查；Discord 限制為 10 MiB 內的短片。
- **Evidence URL (事證連結)**: 上傳成功後由目的地回傳的公開連結。它是唯讀欄位，程式會自動帶入 SurveyCake 表單，不由使用者手動輸入。
- **Google OAuth Credentials (Google OAuth 憑證)**: `data/config/client_secrets.json` 是桌面 OAuth 用戶端設定；`data/config/token.json` 保存授權完成後的 refresh token。兩者均不可提交到 Git。
- **Discord Webhook URL**: Discord 頻道的寫入憑證，僅保存於本機設定且 UI 必須遮蔽顯示。
- **Real-Time Video Pacing (真實時間動態補幀錄影)**: 依據真實經過秒數 (`elapsed * fps`) 動態計算並寫入影片張數，解決畫面擷取延遲與 OpenCV VideoWriter 幀率標頭不符導致影片播放加速與總秒數不符的問題，確保影片播放速度精準為 1.0x 且總長度符合現實時間。
- **Interactive Cancellation Handling (倒數與錄影中途取消機制)**: 倒數與錄影對話框皆支援按下「取消」按鈕。中途取消時立即停止錄製、釋放 `VideoWriter`、自動清理未完成的 `.mp4` 暫存檔，且不會彈出後續 OCR 與檢舉預覽視窗。
- **WASAPI System Audio Capture (WASAPI Loopback 系統聲音同步錄音)**: 透過 `soundcard` 模組於背景非同步擷取系統音效/遊戲聲音，並使用 `av` (PyAV) 將 H.264 視訊與 AAC 音訊整合成相容性佳之標準 MP4 檔；音效擷取失敗時自動降級為無聲影片。
- **Auto-Delete After Upload (上傳成功自動刪除本機事證檔)**: 提供「上傳成功後自動刪除本機事證檔案」設定選項，表單提交與雲端上傳完成後，自動刪除本機 `data/recordings/` 內的對應圖片/影片檔。
- **Clear All Recordings (一鍵清理所有錄製檔案)**: 提供一鍵清理按鈕，彈出確認視窗後一次性清空本機 `data/recordings/` 錄影與截圖暫存資料夾。
- **Clickable Evidence Link & Open Cloud Folder (點選雲端連結查看與一鍵開啟雲端資料夾)**:
  - 於上傳設定區塊提供「前往雲端資料夾」按鈕，直接於預設瀏覽器開啟 Google Drive 檢舉資料夾。
  - 於預覽彈窗提供「點擊前往查看」按鈕，完成上傳後可立即點擊開啟雲端事證連結。
  - 歷史紀錄表格之網址欄位格式化為藍字底線超連結，點選或雙擊即可於瀏覽器開啟檢視。
- **Bundled Browser Runtime (內嵌瀏覽器執行環境)**: 發行版將 Playwright driver、Chromium 與 RapidOCR 模型封裝於單一 EXE；使用者不需要另外安裝 Chrome、Python 或 uv。
- **Release Secret Boundary (發行敏感資料邊界)**: `data/`、`.env`、OAuth 憑證、refresh token、Gemini API Key、Discord Webhook URL 與錄影事證只屬於使用者本機資料，不得加入 Git 或發行 ZIP。
- **Violation Template (違規範本)**: 可新增、編輯或刪除的「名稱＋違規說明」預設內容。
- **Report Form (外掛回報表單)**: 遊戲橘子官方線上 SurveyCake 結構表單 (`https://forms.gamania.com/s/eLGg4`)。
