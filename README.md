# 新楓之谷：經典版《自動外掛檢舉工具》 v1.0.0 (MapleStory Classic Auto Reporter)

開源桌面工具，專為遊戲橘子《新楓之谷：經典版》玩家設計，快速舉報違規外掛。

## 示範影片與詳細教學

- **巴哈姆特詳細教學**：[【攻略】【工具分享】新楓之谷：經典版《自動外掛檢舉工具》附教學](https://forum.gamer.com.tw/C.php?bsn=85994&snA=456)
- **YouTube 示範影片**：[在 YouTube 觀看功能示範影片](https://youtu.be/mF-QPrEjkdE)

## 功能

1. **RapidOCR 本機識別**：從程式介面按下「擷取畫面並辨識」或「錄製影片並辨識」，自動辨識遊戲畫面中的疑似外掛角色 ID；RapidOCR 無法使用時會退回 Windows OCR。
2. **指定視窗自動錄影/截圖**：選擇錄影秒數與 15–60 FPS。採用真實時間動態補幀技術，確保生成的影片總秒數與現實秒數精準 1:1 對應（1.0x 正常播放速度）。
3. **系統聲音同步錄音 (Audio)**：可勾選同步錄製系統音效/遊戲聲音，採用 WASAPI Loopback 背景擷取並以 PyAV 原生合成為標準 AAC + H.264 MP4 檔案。
4. **倒數與錄影隨時取消**：倒數與錄影對話框皆支援隨時按「取消」中斷流程，並自動刪除未完成的暫存檔。
5. **本機 OCR 與手動 AI 複核**：以 RapidOCR 即時辨識角色 ID 與地圖名稱；需要時才以 Gemini 複核單一影格，不會自動上傳整段影片。
6. **事證目的地二選一**：Google Drive 適合官方審查；Discord 適合 10 MiB 內的短片快速分享。
7. **事證自動刪除與本機清理**：可勾選「上傳成功後自動刪除本機事證檔案」，或使用「一鍵清理所有錄製檔案」按鈕快速清空暫存。
8. **一鍵開啟雲端資料夾與點擊查看網址**：提供「前往雲端資料夾」按鈕；預覽視窗提供「點擊前往查看」按鈕；歷史紀錄表格之網址雙擊即可於瀏覽器直接開啟檢視。
9. **送出前確認與歷史紀錄**：上傳成功後自動產生事證網址並填入官方 [SurveyCake 回報頁面](https://forms.gamania.com/s/eLGg4)，同時於本機記錄過往檢舉歷史。

## 快速開始

### 環境需求
- Windows 10 / 11
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) 包管理器

下載版使用者不需要安裝 Python、uv、Playwright 或 Chrome；以下安裝步驟只適用於從原始碼執行或自行打包。

### 安裝步驟

```bash
# 1. 複製或進入專案資料夾
cd d:\Projects\maple-classic-reporter

# 2. 安裝依賴與 Playwright 驅動
uv sync
uv run playwright install chromium

# 3. 啟動應用程式
uv run maple-reporter
```

### 打包為獨立 `.exe` 執行檔（含 Playwright Chromium）

```bash
# 會清除 build/ 與 dist/ 後，將 Playwright driver、Chrome for Testing、RapidOCR ONNX 模型一起打進單一 exe
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

完成後的程式位於 `dist/MapleClassicReporter.exe`。Playwright Chromium、driver 與 RapidOCR 模型都已內嵌，不需要使用者另外安裝 Python、uv 或 Chrome。

建立 GitHub Release ZIP（請依目前版本更新檔名）：

```powershell
Compress-Archive `
  -LiteralPath .\dist\MapleClassicReporter.exe `
  -DestinationPath .\dist\MapleClassicReporter-v1.0.0-windows-x64.zip `
  -CompressionLevel Optimal -Force
```

`v1.0.0` Release ZIP 只包含 `MapleClassicReporter.exe`，解壓後直接執行即可。

若只要清掉 PyInstaller 中間檔與本機測試資料、保留 exe，可執行 `powershell -ExecutionPolicy Bypass -File scripts/clean_release.ps1`。

### v1.0.0 Release 檔案

- 發行檔：`MapleClassicReporter-v1.0.0-windows-x64.zip`
- ZIP 內容：`MapleClassicReporter.exe`
- SHA-256：`4CB0B43ECF7B2C79F0B96F3C6BB49B2E3067B5F1410BBEB2736E19CF5F55EE24`

## 下載 EXE 版的安裝與資料夾說明

下載版不需要安裝 Python、uv 或 Chrome。建議下載 `MapleClassicReporter-v1.0.0-windows-x64.zip` 後解壓縮，再執行其中的 `MapleClassicReporter.exe`；也可以直接下載 EXE。首次啟動會使用 exe 內的 Playwright Chromium；若瀏覽器檔案損壞或遺失，程式會顯示完整可複製的錯誤欄位與官方下載說明網址。

建議將整個資料夾解壓縮到你有寫入權限的位置，例如 `D:\Apps\MapleClassicReporter\`；不要放在 `Program Files`，以免 Windows 阻擋設定與錄影檔寫入。

```text
MapleClassicReporter.exe          # 唯一需要下載的檔案
data/                              # 第一次啟動後自動建立的本機資料
   ├─ config/
   │  ├─ config.json              # 一般設定、範本、白名單與 Webhook
   │  ├─ client_secrets.json      # 使用者自行放入的 Google OAuth 憑證
   │  ├─ token.json               # Google 授權權杖
   │  └─ history.json             # 本機回報歷史
   └─ recordings/                 # 錄製的影片與擷取圖片
```

`data/config/config.json` 可能含有 Gemini API Key 與 Discord Webhook URL；`client_secrets.json` 與 `token.json` 則是 Google 憑證。這些檔案和 `data/recordings/` 都是私密本機資料，不要寄給他人、上傳 GitHub 或隨發行 ZIP 一起散布。

`.gitignore` 已排除 `data/config/` 的設定、OAuth 憑證與權杖，以及 `data/recordings/`。提交或推送前仍應檢查 `git status`，確認沒有把本機 `data/`、`.env`、憑證、Webhook URL 或 API Key 加入版本庫。

若要搬移電腦，複製整個程式資料夾即可；若不想轉移帳號授權，刪除新電腦上的 `data/config/token.json` 後重新連結 Google 帳號。

## 使用與設定步驟

### 1. 第一次啟動

1. 執行 `dist/MapleClassicReporter.exe`；以原始碼執行時則使用 `uv run maple-reporter`。
2. Windows 顯示 SmartScreen 時，請先確認程式來源後選擇「其他資訊」→「仍要執行」。未簽章的個人開源程式可能會出現這個提醒。
3. 在首次引導視窗確認流程：設定事證上傳目的地、選擇遊戲視窗，再以程式內按鈕擷取事證。

### 2. 設定錄影與 OCR

1. 在主畫面選擇《新楓之谷：經典版》遊戲視窗。
2. 選擇錄影秒數與 FPS。錄得更久會提供更多影格供 OCR 辨識角色 ID 與地圖名稱，但影片也會更大；建議先使用 8–15 秒與 30 FPS。
3. 可勾選 **「同步錄製系統聲音 (Audio)」**，錄製遊戲聲音音效。
4. 可勾選 **「上傳成功後自動刪除本機事證檔案」** 節省磁碟空間；或隨時使用 **「一鍵清理所有錄製檔案」** 刪除所有本機暫存。
5. 按「擷取畫面並辨識」完成畫面拉框，或按「錄製影片並辨識」直接錄製遊戲視窗（倒數與錄影過程隨時可按「取消」）；完成後會開啟送出前確認頁。

### 3. 填寫並送出檢舉

1. 在確認頁檢查或修正角色 ID、伺服器、地圖名稱與違規描述。若隱藏地圖未在畫面顯示名稱，OCR 不會猜測錯誤地圖；請直接在「所在地圖名稱」欄位輸入正確名稱。預設違規範本可在主畫面管理、修改或新增。
2. 選擇一種事證目的地：Google Drive 適合官方長期審查（主介面可按 **「前往雲端資料夾」** 查看）；Discord 適合 10 MiB 內的短片。
3. 按「確認內容並上傳事證」。程式會顯示上傳中狀態；成功後自動取得網址（亦可按 **「點擊前往查看」** 或於歷史紀錄雙擊網址開啟檢視），並自動填入官方表單的事證欄位完成送出。
4. 若上傳失敗，表單不會送出。修正設定或改用另一個目的地後再試即可。

## Google Drive API 設定

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)，建立或選擇專案。
2. 使用英文介面時，開啟 **APIs & Services > Enabled APIs & services**，搜尋並啟用 **Google Drive API**。
3. 開啟 **Google Auth Platform**：設定應用程式名稱與支援電子郵件；在 **Audience** 選擇 **External / Testing**。
4. 在 **Audience > Test users** 加入你自己的 Google 帳號電子郵件；未發布的 External 應用程式只有測試使用者可授權。
5. 在 **Data Access** 加入本程式使用的 scope：`https://www.googleapis.com/auth/drive.file`。
6. 建立桌面 OAuth 用戶端時，依序點選 **APIs & Services > Credentials > Create credentials > OAuth client ID**，應用程式類型選 **Desktop app**，下載 JSON。
7. 將下載檔命名為 `client_secrets.json`，放到 `data/config/client_secrets.json`。
8. 啟動程式後選擇 Google Drive，按「連結 Google 帳號」完成瀏覽器授權。

首次授權成功後，refresh token 會儲存在 `data/config/token.json`；之後不需再次登入，除非你撤銷 Google 授權、刪除 token，或 OAuth 測試授權到期。測試模式的 External 應用程式有最多 100 位測試使用者，且授權通常會在 7 天後到期。

`data/config/` 內含 OAuth token、Webhook 與本機設定，不應提交到 Git。

## Discord 上傳

Discord 是可選的短片上傳目的地。預設單檔上限為 10 MiB；超過時請改用 Google Drive。

1. 在 Discord 伺服器建立一個專用文字頻道。
2. 開啟「伺服器設定」→「整合」→「Webhooks」，建立 Webhook，選擇該頻道並複製 **Webhook URL**。
3. 在程式的「上傳目的地」選 Discord，將 Webhook URL 貼入設定欄位並儲存。
4. 上傳成功時，Discord 回傳的 attachment asset URL 會自動顯示於預覽頁，並自動填入 SurveyCake 的事證連結欄位。

Webhook URL 是可直接向頻道發文的敏感憑證；請勿分享、截圖或提交到 Git。Discord attachment URL 可能含有到期簽章，不建議作為唯一的長期官方審查事證。

## 授權條款

MIT License
