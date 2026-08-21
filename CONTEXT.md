# Maple Classic Auto Reporter - Domain Context

## Current Release

> **Window behavior work:** For mixed-DPI dragging, cursor anchors, maximize/restore, frameless resize, or Windows Snap changes, read [`docs/WINDOW_DPI_DRAG_BEHAVIOR.md`](docs/WINDOW_DPI_DRAG_BEHAVIOR.md) before editing. Its behavior contract and hardware acceptance matrix are mandatory.

- **Version**: `2.1.0`
- **Windows release**: `MapleClassicReporter-v2.1.0-windows-x64.zip`
- **Tutorial & Forum Post**: [巴哈姆特詳細教學文章](https://forum.gamer.com.tw/C.php?bsn=85994&snA=456)
- **Documentation Index**: [`docs/README.md`](docs/README.md)
- **Distribution**: ZIP contains the complete `MapleClassicReporter/` onedir bundle. The executable, Playwright Chromium, its driver, and RapidOCR ONNX models stay together in the extracted folder; users must not move the EXE out by itself.
- **Frontend Architecture**: PyWebView bridge with React 18 + TypeScript + Vite, using CSS design tokens, light and dark themes, responsive layouts, and pnpm package management.
- **Runtime fallback**: The application checks bundled Playwright Chromium first, uses a local Playwright cache as fallback, and shows a copy-friendly error dialog with the official download URL when both are unavailable.

## Glossary & Ubiquitous Language

- **Auto Reporter (自動檢舉器)**: 專為《新楓之谷：經典版》打造之外掛自動化檢舉桌面工具。
- **PyWebView UI Bridge (PyWebView 雙向通訊橋接)**: 透過 Python `webview.create_window(..., js_api=api)` 提供前端 React UI 呼叫後端截圖、錄影、OCR、OAuth、設定保存與歷史紀錄之型別安全橋接通道。
- **Suspect ID (外掛角色 ID)**: 遊戲內疑似外掛玩家的角色名稱。因字元特殊或隨機亂碼，支援透過螢幕截圖 / 畫面框選結合 OCR 自動辨識。
- **Game Server (遊戲伺服器)**: 外掛角色所在之伺服器（現有：雪吉拉、菇菇寶貝）。
- **Map Name (所在地圖)**: 外掛角色當前出現的遊戲地圖名稱。優先從遊戲視窗左上角小地圖辨識；若小地圖隱藏，會改掃描畫面中其他可見的地圖名稱，無結果時保留可編輯欄位供使用者更新。
- **Dual Region OCR Map Name Auto-Fill (雙區塊地圖與 ID 分離辨識)**: 針對左上角小地圖區塊 (X: 0~35%, Y: 0~25%) 自動辨識地圖名稱 (如 `魔法森林北郊`) 並自動預填至彈窗的「3. 所在地圖名稱」，同時從小地圖外選單排除該文字，避免地圖名稱污染外掛 ID 欄位。
- **Image Preprocessing Pipeline (圖像預處理管道)**: 針對遊戲小字體與複雜背景，進行 2.5 倍放大與黑白高對比二值化之 OpenCV 前處理，顯著提昇 OCR 辨識率。
- **Multi-Frame Video OCR (多影格抽幀 OCR)**: 錄影期間定時抽影格進行 OCR 辨識，並於預覽彈窗提供可編輯下拉選單 (Editable Suspect ID ComboBox) 供玩家選擇。
- **Asynchronous OCR Worker Thread (非阻塞背景 OCR 線程)**: 將 OCR 辨識移至背景執行緒執行，預覽彈窗秒開不卡頓，並即時動態推播辨識到的候選 ID。
- **Sanctions Matcher (官方處分狀態)**: 背景定期取得並解析官方處分公告，在歷史紀錄與預覽欄位顯示角色的官方封鎖狀態。
- **Recording FPS (錄影幀率)**: 可自訂短影片錄製順暢度之每秒幀率 (15~60 FPS)。
- **Auto-Remember Defaults (預設值自動記憶)**: 自動記憶玩家上次選取/填寫之伺服器、地圖、備註、視窗等設定值並持久化於設定檔。
- **Client Area Bounds (視窗畫布邊界)**: 透過 Win32 `GetClientRect` 精準計算除外標題列與外框後的真實遊戲視窗畫布區域。
- **UI Exclusion & Basic Filtering (UI 排除與基礎過濾)**: 自動排除純數字傷害值、語法標點符號 (`/`, `+`, `:`) 與通用系統 UI 標籤 (`HP`, `MP`, `EXP`, `Lv`, `CH`)。
- **Dynamic Whitelist System (動態 ID 白名單過濾機制)**: 主介面與預覽彈窗皆可加入白名單；設定會持久化並在未來掃描時自動過濾。
- **Evidence Media (檢舉證據)**: 用來證明疑似外掛行為的圖片（PNG/JPG）或影片。
- **Evidence Destination (優先上傳目的地)**: Google Drive 或 Discord。Google Drive 適合長期保存供官方審查；Discord 限制為 10 MiB 內的短片。
- **Evidence URL (雲端證據連結)**: 上傳成功後由目的地回傳的公開連結。它是唯讀欄位，程式會自動帶入 SurveyCake 表單，不由使用者手動輸入。
- **Google OAuth Client (Google OAuth 用戶端)**: 正式 onedir bundle 的 `_internal` 資源內嵌 `google_oauth_client.json` 作為應用程式識別設定；原始碼開發可用 `MAPLE_REPORTER_GOOGLE_OAUTH_CONFIG` 覆寫，`build_secrets/google_oauth_client.json` 僅供 release build 使用，均不可提交到 Git。
- **Google OAuth Token (Google OAuth 權杖)**: `%LOCALAPPDATA%\MapleClassicReporter\oauth_token.dpapi` 使用 Windows DPAPI 保護單一使用者授權完成後的 refresh token；舊版 `data/config/token.json` 會自動遷移後刪除，絕不打包或與其他使用者共用。
- **Discord Webhook URL**: Discord 頻道的寫入憑證，僅保存於使用者 `%LOCALAPPDATA%/MapleClassicReporter/discord_webhook_url.dpapi`，以 Windows DPAPI 保護且 UI 必須遮蔽顯示。
- **Real-Time Video Pacing (真實時間動態補幀錄影)**: 依據真實經過秒數 (`elapsed * fps`) 動態計算並寫入影片張數，解決畫面擷取延遲與 OpenCV VideoWriter 幀率標頭不符導致影片播放加速與總秒數不符的問題，確保影片播放速度精準為 1.0x 且總長度符合現實時間。
- **Interactive Cancellation Handling (倒數與錄影中途取消機制)**: 倒數與錄影皆支援按下「取消」按鈕。中途取消時立即停止錄製、釋放資源、自動清理未完成的暫存檔，且不會彈出後續 OCR 與檢舉預覽視窗。
- **Audio Capture Mode (錄音來源)**: 可選「僅遊戲聲音」、「所有系統聲音」或「不錄音」。「僅遊戲聲音」透過 Windows Process Loopback 跟隨所選錄影視窗及其子程序；「所有系統聲音」透過 WASAPI endpoint loopback 擷取指定輸出裝置。錄音會以 `av` (PyAV) 與 H.264 視訊合成 AAC MP4；擷取失敗時降級為無聲影片。
- **Auto-Delete After Upload (自動刪除已確認檢舉證據)**: 只有程式產生且位於 `%LOCALAPPDATA%/MapleClassicReporter/recordings/` 的圖片或影片，才會在官方表單送出與雲端上傳都成功後依偏好設定刪除；從檔案選擇器匯入的原始檔不會刪除。
- **Clear Recordings (清理暫存檔案)**: 清理 `%LOCALAPPDATA%/MapleClassicReporter/recordings/` 中的暫存錄影與截圖；執行前必須顯示確認視窗。
- **Clickable Evidence Link & Open Cloud Folder (點選雲端連結查看與一鍵開啟雲端資料夾)**:
  - 於上傳設定區塊提供「前往雲端資料夾」按鈕，直接於預設瀏覽器開啟 Google Drive 檢舉資料夾。
  - 於確認頁提供可開啟的雲端證據連結，完成上傳後可立即查看。
  - 歷史紀錄表格之網址欄位格式化為藍字底線超連結，點選或雙擊即可於瀏覽器開啟檢視。
- **Bundled Browser Runtime (內嵌瀏覽器執行環境)**: 發行版將 Playwright driver、Chromium 與 RapidOCR 模型放在同一個 PyInstaller onedir bundle；使用者不需要另外安裝 Chrome、Python 或 uv，且啟動時不必把整個 bundle 解壓到暫存目錄。
- **Release Secret Boundary (發行敏感資料邊界)**: `build_secrets/` 內的 OAuth client JSON 可在 release build 時嵌入 onedir bundle，但不可提交 Git；`data/`、`.env`、DPAPI refresh token、Discord Webhook URL 與檢舉證據絕不能進入 Git 或發行 ZIP。
- **Violation Template (違規範本)**: 可新增、編輯或刪除的「名稱＋違規說明」預設內容。
- **Report Form (外掛回報表單)**: 遊戲橘子官方線上 SurveyCake 結構表單 (`https://forms.gamania.com/s/eLGg4`)。
