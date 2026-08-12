# 新楓之谷：經典版《自動外掛檢舉工具》 v1.1.0 (MapleStory Classic Auto Reporter)

開源桌面工具，專為遊戲橘子《新楓之谷：經典版》玩家設計，快速舉報違規外掛。

## 示範影片與詳細教學

- **巴哈姆特詳細教學**：[【攻略】【工具分享】新楓之谷：經典版《自動外掛檢舉工具》附教學](https://forum.gamer.com.tw/C.php?bsn=85994&snA=456)
- **YouTube 示範影片**：[在 YouTube 觀看功能示範影片](https://youtu.be/mF-QPrEjkdE)

## 功能

1. **RapidOCR 本機識別**：從程式介面按下「擷取畫面並辨識」或「錄製影片並辨識」，自動辨識遊戲畫面中的疑似外掛角色 ID；RapidOCR 無法使用時會退回 Windows OCR。
2. **指定視窗自動錄影/截圖**：選擇錄影秒數與 15–60 FPS。採用真實時間動態補幀技術，確保生成的影片總秒數與現實秒數精準 1:1 對應（1.0x 正常播放速度）。
3. **系統聲音同步錄音 (Audio)**：可勾選同步錄製系統音效/遊戲聲音，採用 WASAPI Loopback 背景擷取並以 PyAV 原生合成為標準 AAC + H.264 MP4 檔案。
4. **回放緩衝**：可持續保留最近 10–60 秒的遊戲畫面與系統聲音，發現違規時按「儲存最近片段」即可保存事證，不必事後回想發生時間。
5. **倒數與錄影隨時取消**：倒數、一般錄影與回放儲存流程皆可取消，並自動清理未完成的暫存檔。
6. **本機 OCR 與手動 AI 複核**：以 RapidOCR 辨識角色 ID 與地圖名稱；需要時才以 Gemini 複核單一影格，不會自動上傳整段影片。
7. **地圖目錄與候選過濾**：針對小地圖、角色名稱、公會／勳章文字做分區辨識、地圖名稱校正、候選排序與白名單過濾，減少誤判。
8. **事證目的地二選一**：Google Drive 適合官方審查；Discord 適合 10 MiB 內的短片快速分享。
9. **安全的 Google OAuth 與設定保存**：OAuth refresh token、Gemini API Key 與 Discord Webhook 使用 Windows DPAPI 保護，不把使用者機密寫入明文設定檔。
10. **上傳成功確認與安全清理**：只有在雲端上傳及官方表單收到明確成功回應後，才會依設定刪除本機事證，避免誤刪未送出的證據。
11. **一鍵開啟雲端資料夾與歷史紀錄**：提供 Google Drive 資料夾、事證網址與過往檢舉歷史的快速開啟功能。
12. **可攜式快速啟動發行版**：Windows 版以 onedir bundle 發行，Chromium、driver 與 RapidOCR 資源隨資料夾提供，不需要安裝 Python、uv 或 Chrome，也不會每次啟動解壓大型 one-file EXE。

## v1.1.0 更新內容

相較於上一版 `v1.1.0`，本版重點如下：

- 新增回放緩衝，可保存最近一段畫面與系統聲音。
- OCR 拆分為地圖辨識、候選排序、影像前處理與背景 worker，提升辨識穩定性並降低 UI 卡頓。
- 新增 Google OAuth DPAPI 保護、Discord/Gemini 機密保護、URL 驗證與更嚴格的上傳成功確認。
- 影片錄製、音訊合併、取消流程與本機事證清理更加穩定，並補上對應測試。
- Windows 發行版改用 onedir：主程式與 Chromium 資源放在同一個資料夾，啟動時不再解壓約 1 GB 的暫存內容。
- Release CI/CD 加入鎖定依賴、單元測試、建置、完整資料夾 ZIP 與版本化 release notes 驗證。

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

### 打包為可攜式 Windows 發行資料夾（含 Playwright Chromium）

```bash
# 會清除 build/ 與舊的 dist/MapleClassicReporter，輸出 onedir 發行資料夾。
# Playwright driver、Chrome for Testing、RapidOCR ONNX 模型會放在資料夾內。
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

完成後的程式位於 `dist/MapleClassicReporter/MapleClassicReporter.exe`。完整的 `MapleClassicReporter` 資料夾必須一起保留；不要把 EXE 單獨移出。使用者不需要另外安裝 Python、uv 或 Chrome。

建立 GitHub Release ZIP（請依目前版本更新檔名）：

```powershell
Compress-Archive `
  -LiteralPath .\dist\MapleClassicReporter `
  -DestinationPath .\dist\MapleClassicReporter-v1.1.0-windows-x64.zip `
  -CompressionLevel Optimal -Force
```

ZIP 會包含完整的 `MapleClassicReporter/` 資料夾。解壓縮後請從資料夾內執行 EXE；不要只解出或只下載 EXE。

若只要清掉 PyInstaller 中間檔與本機測試資料、保留發行資料夾，可執行 `powershell -ExecutionPolicy Bypass -File scripts/clean_release.ps1`。

### Release 檔案格式

- 發行檔：`MapleClassicReporter-v<version>-windows-x64.zip`
- ZIP 內容：`MapleClassicReporter/` 資料夾，包含 EXE、`_internal/`、Playwright Chromium 與 RapidOCR 資源。
- SHA-256：以對應 GitHub Release 的實際 ZIP 為準。

## 下載 EXE 版的安裝與資料夾說明

下載版不需要安裝 Python、uv 或 Chrome。下載 `MapleClassicReporter-v<version>-windows-x64.zip` 後，請將整個 `MapleClassicReporter/` 資料夾解壓縮，再執行其中的 `MapleClassicReporter.exe`。程式會直接使用資料夾內的 Playwright Chromium，不會在每次啟動時把整個瀏覽器解壓到暫存目錄；若瀏覽器檔案損壞或遺失，程式會顯示完整可複製的錯誤欄位與官方下載說明網址。

建議將整個資料夾解壓縮到你有寫入權限的位置，例如 `D:\Apps\MapleClassicReporter\`；不要放在 `Program Files`，以免 Windows 阻擋設定與錄影檔寫入。

```text
MapleClassicReporter\
├─ MapleClassicReporter.exe       # 從這裡啟動
└─ _internal\                     # 不要刪除或移出
   └─ ms-playwright\              # Chromium 與其 DLL／資源
```

錄影、一般設定與回報歷史都會寫入使用者專屬目錄 `%LOCALAPPDATA%\MapleClassicReporter\`；舊版 `data/config/` 的一般設定會在啟動時自動遷移。Gemini API Key 與 Discord Webhook 不再寫入 JSON，而是分別以 Windows DPAPI 保護於：

```text
%LOCALAPPDATA%\MapleClassicReporter\gemini_api_key.dpapi
%LOCALAPPDATA%\MapleClassicReporter\discord_webhook_url.dpapi
%LOCALAPPDATA%\MapleClassicReporter\recordings\
```

正式發行資料夾內嵌的是應用程式共用的 OAuth Desktop client 設定；它只是用來識別 Maple Classic Reporter，不包含任何使用者授權。每位使用者首次登入後取得的 refresh token 會以 Windows DPAPI 保護，寫入自己的使用者資料夾：

```text
%LOCALAPPDATA%\MapleClassicReporter\oauth_token.dpapi
```

舊版的 `data/config/token.json` 會在成功登入後自動遷移到上述受保護檔案，並刪除明文檔案。

`%LOCALAPPDATA%\MapleClassicReporter\` 都是私密本機資料，不要寄給他人、上傳 GitHub 或隨發行 ZIP 一起散布。DPAPI 檔案即使被複製，也只能由同一 Windows 使用者解密。

`.gitignore` 已排除舊版 `data/config/`、OAuth 憑證與 `data/recordings/`；目前的使用者資料位於 `%LOCALAPPDATA%`。提交或推送前仍應檢查 `git status`，確認沒有把本機 `data/`、`.env`、憑證、Webhook URL 或 API Key 加入版本庫。

若要搬移電腦，請重新執行程式並重新連結 Google 帳號；程式資料夾不包含使用者設定或授權。若要保留設定，需在同一 Windows 使用者下搬移 `%LOCALAPPDATA%\MapleClassicReporter\`，若不想轉移帳號授權則只不要搬移 `oauth_token.dpapi`。

Windows DPAPI 可防止其他 Windows 使用者或單純外洩檔案直接讀出 refresh token，但無法防禦已在同一 Windows 使用者權限下執行的惡意程式。OAuth client JSON 內嵌於發行包也屬 Installed App 的公開識別設定，不應把它當成可保密的 server secret。

## 使用與設定步驟

### 1. 第一次啟動

1. 執行 `dist/MapleClassicReporter/MapleClassicReporter.exe`；以原始碼執行時則使用 `uv run maple-reporter`。
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

## Google Drive 連結與 OAuth

### 下載版使用者

一般使用者不需要建立 Google Cloud project、加入測試使用者或下載 `client_secrets.json`。下載並啟動正式 EXE 後：

1. 選擇 **Google Drive** 作為事證目的地。
2. 按 **「連結 Google 帳號」**。
3. 在系統瀏覽器登入自己的 Google 帳號，並同意 `drive.file` 權限。

程式使用專案維護者正式發布的 OAuth Desktop client；每位使用者的授權仍只會連到自己的 Google Drive。首次授權成功後，refresh token 會以 Windows DPAPI 保護在 `%LOCALAPPDATA%\MapleClassicReporter\oauth_token.dpapi`；之後不需再次登入，除非使用者撤銷授權或刪除該檔案。

### 開發者建置

正式 release build 需要一份由專案維護者管理、但不提交 Git 的 OAuth Desktop client JSON：

```text
build_secrets/google_oauth_client.json
```

`scripts/build_windows.ps1` 與 `MapleClassicReporter.spec` 會在建置前檢查這個檔案，缺少時直接失敗；建置成功後它會放在 PyInstaller onedir bundle 的 `_internal` 資源目錄，不會以獨立 JSON 出現在發行資料夾根目錄。OAuth client 設定不會複製到使用者設定目錄，而使用者的 DPAPI token 也不在 PyInstaller 資源中。

原始碼開發可用環境變數 `MAPLE_REPORTER_GOOGLE_OAUTH_CONFIG` 指向測試用 OAuth JSON；舊的 `data/config/client_secrets.json` 僅保留作為進階開發者 fallback。若 fork 本專案，請建立並使用自己的 OAuth project，不要重用維護者的 client 或 token。

目前正式 OAuth 設定使用 External / Production，且只要求 `https://www.googleapis.com/auth/drive.file`；不使用 service account 或完整的 `drive` scope。Webhook、Gemini key 與 DPAPI token 都位於使用者的 `%LOCALAPPDATA%`，不應提交到 Git。

## Discord 上傳

Discord 是可選的短片上傳目的地。預設單檔上限為 10 MiB；超過時請改用 Google Drive。

1. 在 Discord 伺服器建立一個專用文字頻道。
2. 開啟「伺服器設定」→「整合」→「Webhooks」，建立 Webhook，選擇該頻道並複製 **Webhook URL**。
3. 在程式的「上傳目的地」選 Discord，將 Webhook URL 貼入設定欄位並儲存。
4. 上傳成功時，Discord 回傳的 attachment asset URL 會自動顯示於預覽頁，並自動填入 SurveyCake 的事證連結欄位。

Webhook URL 是可直接向頻道發文的敏感憑證；請勿分享、截圖或提交到 Git。Discord attachment URL 可能含有到期簽章，不建議作為唯一的長期官方審查事證。

## 授權條款

MIT License
