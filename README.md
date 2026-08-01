# 新楓之谷：經典版《自動外掛檢舉工具》 (MapleStory Classic Auto Reporter)

開源桌面工具，專為遊戲橘子《新楓之谷：經典版》玩家設計，快速舉報違規外掛。

## 功能

1. **Windows 原生 OCR 識別**：按下全域熱鍵（預設 `F9`）觸發螢幕拉框遮罩，自動精準識別遊戲畫面上怪異的外掛角色 ID。
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
uv run pyinstaller --noconfirm --onedir --windowed --add-data "src/maple_reporter:maple_reporter" src/maple_reporter/main.py
```

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

## 📜 授權條款

MIT License
