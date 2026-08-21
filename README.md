# 新楓之谷：經典版《自動外掛檢舉工具》 v2.1.1 (MapleStory Classic Auto Reporter)

開源 Windows 桌面工具，專為遊戲橘子《新楓之谷：經典版》玩家設計，協助快速建立檢舉證據並回報疑似外掛。介面採用 **PyWebView + React 18 + TypeScript + Vite**，支援淺色與深色主題、響應式版面及即時狀態提示。

## 示範影片與文件

- **巴哈姆特詳細教學**：[【攻略】【工具分享】新楓之谷：經典版《自動外掛檢舉工具》附教學](https://forum.gamer.com.tw/C.php?bsn=85994&snA=456)
- **YouTube 示範影片**：[在 YouTube 觀看功能示範影片](https://youtu.be/mF-QPrEjkdE)
- **專案文件目錄**：[docs/README.md](docs/README.md)

## 功能

1. **現代化桌面介面（PyWebView + React 18）**：提供淺色與深色主題、響應式版面、清楚的操作狀態與錄影進度提示。
2. **本機文字辨識（OCR）**：使用「截圖」或「錄影」取得遊戲畫面後，由 RapidOCR 在本機辨識疑似外掛角色 ID，並提供候選名單供你選擇；RapidOCR 無法使用時會改用 Windows OCR。
3. **角色 ID 與地圖名稱分區辨識**：分別辨識左上角小地圖與其他畫面區域，自動填入所在地圖名稱並排除不應列為角色 ID 的文字。確認頁也會帶入歷史紀錄中的地圖與常用資料，減少重複輸入。
4. **背景靜默送出檢舉**：確認送出後，在背景上傳檢舉證據並以 Playwright 填寫官方表單，不遮擋遊戲或搶走焦點；關閉背景模式時，則會開啟瀏覽器顯示填表過程。
5. **官方處分狀態**：定期取得並快取官方處分公告，比對歷史紀錄中的角色是否已被封鎖，並顯示處分結果與公告來源。
6. **指定視窗截圖與錄影**：鎖定所選 Windows 視窗進行截圖或錄影。一般錄影支援 1～60 秒與 15～60 FPS，並依實際經過時間補幀，使影片長度與播放速度維持正常。
7. **可選擇錄音來源**：可選擇「僅遊戲聲音」、「所有系統聲音」或「不錄音」。「僅遊戲聲音」會跟隨目前選擇的錄影視窗及其子程序，不會錄入其他應用程式或系統通知；完成後以 PyAV 合成 AAC + H.264 MP4 檔案。
8. **循環錄影**：像行車記錄器一樣在背景持續保留最近 10～30 秒的遊戲畫面與所選聲音；按下「儲存循環錄影」即可輸出目前保留的片段，並分析最後 5 秒畫面以提高事件尾端的 OCR 辨識機會。儲存完成後，背景循環錄影不會中斷。
9. **全域錄影快捷鍵**：即使遊戲視窗在前景，也能使用 Windows 全域快捷鍵控制循環錄影或一般錄影。`Ctrl` 與 `Shift` 固定，只需選擇最後一個鍵位；預設 `Ctrl+Shift+F9` 啟動或儲存循環錄影，`Ctrl+Shift+F10` 開始一般錄影。一般錄影中再次按 F10 會取消；循環錄影片段正在儲存或處理時再次按 F9 會忽略，不會重複排程。
10. **倒數與錄影隨時取消**：倒數與一般錄影皆可取消，並自動清理未完成的暫存檔。錄影期間，主畫面狀態列會顯示倒數、已錄製秒數及進度，不會另開遮擋遊戲的提示視窗；循環錄影也可從狀態列停止。
11. **優先上傳目的地**：可選 Google Drive 或 Discord。Google Drive 適合保存供官方審查的檢舉證據；Discord 適合上傳 10 MiB 內的短片。
12. **受保護的帳號與頻道資料**：Google OAuth refresh token 與 Discord 頻道連結使用 Windows DPAPI 保護，不會寫入一般明文設定檔。
13. **自動刪除已確認檢舉證據**：只有檢舉證據上傳及官方表單送出都成功後，才會依偏好設定刪除程式產生的本機暫存檔，避免誤刪尚未送出的檔案。
14. **雲端證據與歷史紀錄**：可直接開啟 Google Drive 資料夾、雲端證據連結與官方處分公告，並在歷史紀錄查看過往回報結果。
15. **可攜式 onedir 發行版**：Windows 版以 onedir bundle 發行，Chromium、driver 與 RapidOCR 資源隨資料夾提供，不需要安裝 Python、uv、pnpm 或 Chrome，也不會每次啟動解壓大型 one-file EXE。
16. **安全的應用程式自動更新**：啟動後在背景檢查 GitHub Releases，可選穩定版或預覽版頻道，優先下載較小的差分包並在必要時改用完整包。下載前會檢查磁碟空間，套用前驗證 SHA-256 與 Ed25519 簽章；更新內容可在「關於」頁面展開閱讀，重啟套用時會顯示即時進度，且不會覆蓋使用者資料。

## 快速開始

### 開發環境需求

- Windows 10 / 11 (x64)
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) Python 套件管理器
- [pnpm](https://pnpm.io/) Node.js 套件管理器（請勿使用 npm）

下載版使用者不需要安裝 Python、uv、pnpm、Playwright 或 Chrome；以下安裝步驟只適用於從原始碼執行或自行打包。

### 安裝與開發步驟

```powershell
# 1. 進入專案資料夾
cd d:\Projects\maple-classic-reporter

# 2. 前端依賴安裝與編譯 (請務必使用 pnpm)
cd web
pnpm install
pnpm run build
cd ..

# 3. 後端依賴同步與 Playwright 驅動安裝
uv sync
uv run playwright install chromium

# 4. 啟動桌面應用程式
uv run maple-reporter
```

### 打包為可攜式 Windows 發行資料夾（含 Playwright Chromium）

```bash
# 會自動使用 pnpm 建置前端資源，並清除舊 dist/ 輸出 onedir 發行資料夾
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

完成後的程式位於 `dist/MapleClassicReporter/MapleClassicReporter.exe`。完整的 `MapleClassicReporter` 資料夾必須一起保留；不要把 EXE 單獨移出。使用者不需要另外安裝 Python、uv 或 Chrome。

建立 GitHub Release ZIP（請依目前版本更新檔名）：

```powershell
Compress-Archive `
  -LiteralPath .\dist\MapleClassicReporter `
  -DestinationPath .\dist\MapleClassicReporter-v2.1.1-windows-x64.zip `
  -CompressionLevel Optimal -Force
```

ZIP 會包含完整的 `MapleClassicReporter/` 資料夾。解壓縮後請從資料夾內執行 EXE；不要只解出或只下載 EXE。

若只要清掉 PyInstaller 中間檔與本機測試資料、保留發行資料夾，可執行 `powershell -ExecutionPolicy Bypass -File scripts/clean_release.ps1`。

### 發行檔案格式

- 發行檔：`MapleClassicReporter-v<version>-windows-x64.zip`
- ZIP 內容：`MapleClassicReporter/` 資料夾，包含 EXE、`_internal/`、Playwright Chromium 與 RapidOCR 資源。
- SHA-256：以對應 GitHub Release 的實際 ZIP 為準。

## 安裝 Windows 可攜版

下載版不需要安裝 Python、uv 或 Chrome。下載 `MapleClassicReporter-v<version>-windows-x64.zip` 後，請將整個 `MapleClassicReporter/` 資料夾解壓縮，再執行其中的 `MapleClassicReporter.exe`。程式會直接使用資料夾內的 Playwright Chromium，不會在每次啟動時把整個瀏覽器解壓到暫存目錄；若瀏覽器檔案損壞或遺失，程式會顯示完整可複製的錯誤欄位與官方下載說明網址。

建議將整個資料夾解壓縮到你有寫入權限的位置，例如 `D:\Apps\MapleClassicReporter\`；不要放在 `Program Files`，以免 Windows 阻擋設定與錄影檔寫入。

```text
MapleClassicReporter\
├─ MapleClassicReporter.exe       # 從這裡啟動
└─ _internal\                     # 不要刪除或移出
   └─ ms-playwright\              # Chromium 與其 DLL／資源
```

錄影、偏好設定與歷史紀錄都會寫入使用者專屬目錄 `%LOCALAPPDATA%\MapleClassicReporter\`；舊版 `data/config/` 的一般設定會在啟動時自動遷移。Discord 頻道連結以 Windows DPAPI 保護，不會寫入 JSON：

```text
%LOCALAPPDATA%\MapleClassicReporter\discord_webhook_url.dpapi
%LOCALAPPDATA%\MapleClassicReporter\recordings\
```

正式發行資料夾內嵌的是應用程式共用的 OAuth Desktop client 設定；它只用來識別 Maple Classic Reporter，不包含任何使用者授權。每位使用者首次登入後取得的 refresh token 會以 Windows DPAPI 保護，寫入自己的使用者資料夾：

```text
%LOCALAPPDATA%\MapleClassicReporter\oauth_token.dpapi
```

舊版的 `data/config/token.json` 會在成功登入後自動遷移到上述受保護檔案，並刪除明文檔案。

`%LOCALAPPDATA%\MapleClassicReporter\` 都是私密本機資料，不要寄給他人、上傳 GitHub 或隨發行 ZIP 一起散布。DPAPI 檔案即使被複製，也只能由同一 Windows 使用者解密。

`.gitignore` 已排除舊版 `data/config/`、OAuth 憑證與 `data/recordings/`；目前的使用者資料位於 `%LOCALAPPDATA%`。提交或推送前仍應檢查 `git status`，確認沒有把本機 `data/`、`.env`、憑證、Webhook URL 或 API Key 加入版本庫。

若要搬移電腦，請在新電腦重新啟動程式並登入 Google 帳號；程式資料夾不包含使用者偏好設定或授權。若只是在同一 Windows 使用者環境搬移程式，可另外備份 `%LOCALAPPDATA%\MapleClassicReporter\`；不需要保留 Google 授權時，請勿搬移 `oauth_token.dpapi`。

Windows DPAPI 可防止其他 Windows 使用者或單純外洩檔案直接讀出 refresh token，但無法防禦已在同一 Windows 使用者權限下執行的惡意程式。OAuth client JSON 內嵌於發行包也屬 Installed App 的公開識別設定，不應把它當成可保密的 server secret。

## 使用與偏好設定

### 1. 第一次啟動

1. 執行 `dist/MapleClassicReporter/MapleClassicReporter.exe`；以原始碼執行時則使用 `uv run maple-reporter`。
2. Windows 顯示 SmartScreen 時，請先確認程式來源後選擇「其他資訊」→「仍要執行」。未簽章的個人開源程式可能會出現這個提醒。
3. 在首次引導視窗確認流程：設定優先上傳目的地、選擇遊戲視窗，再使用主畫面的「截圖」、「錄影」或「循環錄影」建立檢舉證據。

### 2. 設定錄影與文字辨識

1. 在主畫面選擇《新楓之谷：經典版》遊戲視窗。
2. 選擇錄影秒數與 FPS。錄得更久會提供更多影格供 OCR 辨識角色 ID 與地圖名稱，但影片也會更大；建議先使用 8–15 秒與 30 FPS。
3. 在 **「錄音來源」** 選擇「僅遊戲聲音」、「所有系統聲音」或「不錄音」。選擇「僅遊戲聲音」時，音訊會跟隨上方選擇的錄影視窗及其子程序；選擇「所有系統聲音」時，需再指定系統聲音輸出裝置。
4. 在 **「全域快捷鍵」** 開啟快捷鍵，只選擇最後一個鍵位即可，`Ctrl` 與 `Shift` 固定。預設 `Ctrl+Shift+F9` 啟動或儲存循環錄影，`Ctrl+Shift+F10` 開始一般錄影；第一次按 F9 會啟動循環錄影，累積幾秒後再次按 F9 才會儲存目前片段。F10 會在主畫面狀態列顯示倒數、錄影秒數、進度條與取消按鈕。若快捷鍵已被其他程式使用，請更換鍵位後重新儲存。
5. 可在「一般與表單預設」開啟 **「自動刪除已確認檢舉證據」**，或在「錄影與音訊」使用 **「清理暫存檔案」** 釋放本機空間。
6. 一般錄影期間，主畫面狀態列會顯示倒數、已錄製秒數、進度條與「取消錄影」。按下主畫面的「截圖」或「錄影」後，程式會自動辨識畫面並開啟「檢舉證據回報表單」。

### 3. 填寫並送出檢舉

1. 在「檢舉證據回報表單」檢查或修正角色 ID、伺服器、所在地圖名稱與違規描述。若隱藏地圖未顯示名稱，請直接輸入正確地圖；可在「一般與表單預設」管理違規描述範本。
2. 在「上傳與帳號」選擇 **「優先上傳目的地」**：Google Drive 適合長期保存供官方審查；Discord 適合 10 MiB 內的短片。使用 Google Drive 時可按 **「前往雲端資料夾」** 查看檔案。
3. 按 **「送出檢舉證據」**。程式會先上傳檔案，取得雲端證據連結，再填入官方表單並送出；成功後會自動加入歷史紀錄。
4. 上傳失敗時不會送出官方表單。請檢查帳號或 Discord 頻道連結，也可以切換優先上傳目的地後重試。

### 4. 應用程式更新

1. 程式啟動後會自動檢查更新；可在「關於與更新」開關自動下載，並選擇「穩定版」或「預覽版」頻道。
2. 發現新版本時，「關於與更新」會顯示套件類型、下載大小、所需與可用磁碟空間；展開「更新內容」可閱讀經安全過濾的 GitHub Release Markdown，或前往 GitHub 查看完整說明。
3. 自動下載關閉時可按「立即下載」；下載期間會顯示百分比並可取消。完成後按「重啟應用」即可套用，若仍在錄影、處理影片或送出回報，程式會等待工作結束再重啟。
4. 套用視窗會持續顯示解壓、替換、驗證及重新啟動進度。更新失敗時會保留或還原原安裝內容；使用者設定、授權、歷史與錄影仍保存在 `%LOCALAPPDATA%\MapleClassicReporter\`。

更新機制、發行資產與簽章設定的完整技術說明請見 [docs/UPDATES.md](docs/UPDATES.md)。

## Google Drive 連結與 OAuth

### 下載版使用者

一般使用者不需要建立 Google Cloud project、加入測試使用者或下載 `client_secrets.json`。下載並啟動正式 EXE 後：

1. 選擇 **Google Drive** 作為優先上傳目的地。
2. 按 **「登入 Google 帳號」**。
3. 在系統瀏覽器登入自己的 Google 帳號，並同意 `drive.file` 權限。

程式使用專案維護者正式發布的 OAuth Desktop client；每位使用者的授權仍只會連到自己的 Google Drive。首次授權成功後，refresh token 會以 Windows DPAPI 保護在 `%LOCALAPPDATA%\MapleClassicReporter\oauth_token.dpapi`；之後不需再次登入，除非使用者撤銷授權或刪除該檔案。

### 開發者建置

正式 release build 需要一份由專案維護者管理、但不提交 Git 的 OAuth Desktop client JSON：

```text
build_secrets/google_oauth_client.json
```

`scripts/build_windows.ps1` 與 `MapleClassicReporter.spec` 會在建置前檢查這個檔案，缺少時直接失敗；建置成功後它會放在 PyInstaller onedir bundle 的 `_internal` 資源目錄，不會以獨立 JSON 出現在發行資料夾根目錄。OAuth client 設定不會複製到使用者設定目錄，而使用者的 DPAPI token 也不在 PyInstaller 資源中。

原始碼開發可用環境變數 `MAPLE_REPORTER_GOOGLE_OAUTH_CONFIG` 指向測試用 OAuth JSON；舊的 `data/config/client_secrets.json` 僅保留作為進階開發者 fallback。若 fork 本專案，請建立並使用自己的 OAuth project，不要重用維護者的 client 或 token。

目前正式 OAuth 設定使用 External / Production，且只要求 `https://www.googleapis.com/auth/drive.file`；不使用 service account 或完整的 `drive` scope。Webhook 與 DPAPI token 都位於使用者的 `%LOCALAPPDATA%`，不應提交到 Git。

## Discord 上傳

Discord 是可選的短片上傳目的地。預設單檔上限為 10 MiB；超過時請改用 Google Drive。

1. 在 Discord 伺服器建立一個專用文字頻道。
2. 開啟「伺服器設定」→「整合」→「Webhooks」，建立 Webhook，選擇該頻道並複製 **Webhook URL**。
3. 在「上傳與帳號」將 **「優先上傳目的地」** 設為 Discord，把 Webhook URL 貼入 **「Discord 頻道連結」**，再按「測試連線」。
4. 上傳成功時，Discord 回傳的 attachment asset URL 會自動顯示於預覽頁，並自動填入 SurveyCake 的檢舉證據連結欄位。

Webhook URL 是可直接向頻道發文的敏感憑證；請勿分享、截圖或提交到 Git。Discord attachment URL 可能含有到期簽章，不建議作為唯一的長期官方審查證據。

## 授權條款

MIT License
