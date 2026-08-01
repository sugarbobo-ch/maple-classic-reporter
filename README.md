# 新楓之谷：經典版《自動外掛檢舉工具》 (MapleStory Classic Auto Reporter)

開源桌面工具，專為遊戲橘子《新楓之谷：經典版》玩家設計，快速舉報違規外掛。

## 示範影片

**新楓之谷：經典版 《自動外掛檢舉工具》 示範影片**：[在 YouTube 觀看](https://youtu.be/mF-QPrEjkdE)

## 功能

1. **Windows 原生 OCR 識別**：從程式介面按下「擷取畫面並辨識」或「錄製影片並辨識」，自動辨識遊戲畫面中的疑似外掛角色 ID。
2. **指定視窗自動錄影/截圖**：選擇錄影秒數與 15–60 FPS，較長影片可提供更多 OCR 影格，但會增加檔案大小。
3. **本機 OCR 與手動 AI 複核**：以 RapidOCR 即時辨識角色 ID 與地圖名稱；需要時才以 Gemini 複核單一影格。
4. **事證目的地二選一**：Google Drive 適合官方審查；Discord 適合 10 MiB 內的短片快速分享。
5. **送出前確認**：上傳成功後自動產生事證網址，並填入官方 [SurveyCake 回報頁面](https://forms.gamania.com/s/eLGg4)。
6. **歷史檢舉紀錄**：本地方便查閱過往檢舉目標與連結。

## 快速開始

### 環境需求
- Windows 10 / 11
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) 包管理器

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

### 打包為獨立 `.exe` 執行檔

```bash
uv run pyinstaller --noconfirm --clean --onedir --windowed --name MapleClassicReporter --icon assets/icon.ico --add-data "assets/icon.png;assets" --add-data "src/maple_reporter/ocr/data;maple_reporter/ocr/data" src/maple_reporter/main.py
```

完成後的程式位於 `dist/MapleClassicReporter/MapleClassicReporter.exe`。請保留整個 `MapleClassicReporter` 資料夾，不要只複製其中的 `.exe`，因為它需要同資料夾內的執行依賴與 OCR 資料。

## 下載 EXE 版的安裝與資料夾說明

下載版不需要安裝 Python 或 uv，但必須下載並解壓縮完整的 `MapleClassicReporter` 發行資料夾（建議以 ZIP 發布）。請勿只從 GitHub 下載單獨的 `MapleClassicReporter.exe`，因為同層的 `_internal/` 資料夾包含 Qt、OCR 與其他必要元件。

建議將整個資料夾解壓縮到你有寫入權限的位置，例如 `D:\Apps\MapleClassicReporter\`；不要放在 `Program Files`，以免 Windows 阻擋設定與錄影檔寫入。

```text
MapleClassicReporter/
├─ MapleClassicReporter.exe       # 雙擊啟動程式
├─ _internal/                     # 必要執行元件，請勿修改或刪除
└─ data/                          # 第一次啟動後自動建立的本機資料
   ├─ config/
   │  ├─ config.json              # 一般設定、範本、白名單與 Webhook
   │  ├─ client_secrets.json      # 使用者自行放入的 Google OAuth 憑證
   │  ├─ token.json               # Google 授權權杖
   │  └─ history.json             # 本機回報歷史
   └─ recordings/                 # 錄製的影片與擷取圖片
```

`data/config/config.json` 可能含有 Gemini API Key 與 Discord Webhook URL；`client_secrets.json` 與 `token.json` 則是 Google 憑證。這些檔案和 `data/recordings/` 都是私密本機資料，不要寄給他人、上傳 GitHub 或隨發行 ZIP 一起散布。

若要搬移電腦，複製整個程式資料夾即可；若不想轉移帳號授權，刪除新電腦上的 `data/config/token.json` 後重新連結 Google 帳號。

## 使用與設定步驟

### 1. 第一次啟動

1. 執行 `dist/MapleClassicReporter/MapleClassicReporter.exe`；以原始碼執行時則使用 `uv run maple-reporter`。
2. Windows 顯示 SmartScreen 時，請先確認程式來源後選擇「其他資訊」→「仍要執行」。未簽章的個人開源程式可能會出現這個提醒。
3. 在首次引導視窗確認流程：設定事證上傳目的地、選擇遊戲視窗，再以程式內按鈕擷取事證。

### 2. 設定錄影與 OCR

1. 在主畫面選擇《新楓之谷：經典版》遊戲視窗。
2. 選擇錄影秒數與 FPS。錄得更久會提供更多影格供 OCR 辨識角色 ID 與地圖名稱，但影片也會更大；建議先使用 8–15 秒與 30 FPS。
3. 需要更精細判讀時，可在預覽頁手動使用 AI 複核。它不會在每次辨識時自動呼叫，避免拖慢操作。
4. 按「擷取畫面並辨識」完成畫面拉框，或按「錄製影片並辨識」直接錄製遊戲視窗；完成後會開啟送出前確認頁。

### 3. 填寫並送出檢舉

1. 在確認頁檢查或修正角色 ID、伺服器、地圖名稱與違規描述。若隱藏地圖未在畫面顯示名稱，OCR 不會猜測錯誤地圖；請直接在「所在地圖名稱」欄位輸入正確名稱。預設違規範本可在主畫面管理、修改或新增。
2. 選擇一種事證目的地：Google Drive 適合官方長期審查；Discord 適合 10 MiB 內的短片。
3. 按「確認內容並上傳事證」。程式會顯示上傳中狀態；成功後自動取得網址、填入官方表單的事證欄位，才送出表單。
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
