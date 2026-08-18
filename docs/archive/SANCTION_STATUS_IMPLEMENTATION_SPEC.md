# 制裁狀態自動檢查：實作交接規格

## 任務結果

在現有 PyWebView／React 桌面應用程式加入制裁公告同步功能。應用程式從新楓之谷：經典版官方「重要」公告取得制裁名單，將歷史檢舉中的完整角色 ID 與官方遮罩名稱比對，並持久化結果。

完成後應具備以下行為：

- 啟動時依設定在背景增量同步，不阻塞 UI。
- 歷史頁可手動批次檢查，並顯示逐篇進度。
- 已完成的舊日期不再請求公告內文；今天與昨天允許官方修改，因此會重新取得。
- 公告內容、同步中繼資料與歷史紀錄分開持久化。
- 一篇公告只下載一次後即可在本機比對全部角色，不得為每個角色各發送請求。

官方入口：[重要公告](https://maplestoryclassic.beanfun.com/Main?kind=758)。

## 已確認的產品決策

以下是需求決策，不要在實作時自行改變：

1. 遮罩命中直接顯示「已制裁」，並保留公告日期與連結。官方遮罩無法證明唯一身分；多個本機 ID 符合同一遮罩時，全部視為已制裁。這是已接受的誤判風險。
2. 完整同步後未命中者顯示「未被制裁」。
3. 每個 `*` 恰好代表一個 Unicode 字元。中文字、英文字母、數字各算一個字元；先做 Unicode NFC 正規化，英文大小寫保持敏感，總長度必須一致。
4. 只解析標題包含「遊戲異常行為制裁公告」的文章。
5. 任一非空白官方制裁結果都算「已制裁」，並保存官方原始文字。
6. 只用公告日期等於或晚於該筆檢舉日期的公告比對該紀錄。
7. 同一 ID 命中多篇時，歷史頁顯示最新公告；若日期相同，以數值較大的 `Bid` 作穩定次序。
8. 首次建立快取時回溯台灣時間最近 30 個日曆日（今天加前 29 天）。之後補齊上次完整同步以來的所有日期，即使應用程式超過 30 天未開啟。
9. 台灣時間的今天與昨天屬於可編輯日期：同步時重新取得這兩日所有制裁公告內文，包括已存在的 `Bid`，以接收官方編輯或補充。
10. 兩天前及更早日期在成功完成後封存；封存日期只讀本機快取，不再請求公告內文。尚未成功完成的舊日期仍須重試，成功後才封存。
11. 所有 HTTP 請求序列執行。相鄰請求之間隨機等待 3–8 秒；單次失敗最多再重試 2 次，亦即最多 3 次嘗試。失敗項目不得標記為已完成。
12. 啟動自動更新預設開啟；有歷史紀錄，且距上次完整成功同步至少 6 小時才執行。失敗同步不推進 6 小時計時。
13. 沒有歷史紀錄時，啟動同步直接略過且不發送網路請求。
14. 手動批次檢查忽略自動更新開關與 6 小時限制，但遵守日期快取、可編輯日期、隨機延遲和重試規則。
15. 新增歷史紀錄後立即使用現有本機快取比對，不發送網路請求。
16. 部分同步失敗時，可套用已成功取得的陽性命中；未命中紀錄保持原狀。只有完整同步才能產生新的「未被制裁」結果或推進最近完整同步時間。
17. 背景同步只有在新增命中或發生錯誤時顯示一則摘要 toast；零命中且成功時保持安靜。手動同步完成時一律顯示一則摘要。
18. 清空歷史紀錄保留公告快取。
19. 快取重建只提供開發者 API，不加入正式 UI。
20. 核心後端可由任一 UI 呼叫，但這次只修改預設 WebView／React UI；不替 `--pyside` 增加介面。

## 現況與修改接縫

先閱讀下列現有實作，不要另建平行的設定或歷史系統：

- `src/maple_reporter/utils/config.py`
  - `DEFAULT_CONFIG`、`load_config`、`save_config`
  - `HISTORY_FILE`、`load_history`、`add_history_entry`、`clear_history`
  - 現有 JSON 原子寫入 helper
- `src/maple_reporter/gui/pywebview_bridge.py`
  - `get_initial_data`、`save_config_key`、`shutdown`
  - 正式與開發模式寫入歷史紀錄的位置
  - `_emit_event` 與現有背景 worker 模式
- `src/maple_reporter/gui/webview_app.py`
  - Bridge 建立、window lifecycle 與關閉流程
- `web/src/App.tsx`
  - 初始資料、PyWebView events、history state、HistoryView props
- `web/src/components/HistoryView.tsx`
  - 已有 `ban_status`、`ban_date` 欄與 Badge render helper
- `web/src/components/SettingsView.tsx`
  - 一般設定與既有 Switch pattern
- `web/src/hooks/useAppConfig.ts`
  - 前端預設值與 optimistic save/rollback
- `web/src/types/index.ts`
  - `AppConfig`、`HistoryRecord`、PyWebView API 與 event types

注意：`App.tsx` 和 `useAppConfig` 目前都可能在 ready 階段呼叫 `get_initial_data`。`get_initial_data` 必須保持唯讀，不得在其中啟動同步，否則會重複建立 worker。

## 官方資料來源

使用 `requests` 呼叫官方 JSON API；這個功能不需要 Playwright 或 Chromium。

### 公告列表

```text
POST https://maplestoryclassic.beanfun.com/api/Bulletin/FindBulletin
Content-Type: application/json

{
  "pageSize": 10,
  "kind": 758,
  "page": <page>,
  "method": 6,
  "toAll": 0
}
```

### 公告內容

```text
POST https://maplestoryclassic.beanfun.com/api/Bulletin/BulletinDetail?pbid=<Bid>
```

公告內容可在回應的 `data.myDataSet.table.content` 取得。實作時先用擷取的 fixture 確認列表回應欄位名稱，不要把尚未驗證的猜測寫進 production parser。

以 `response.content.decode("utf-8-sig")` 後再 `json.loads`，避免 `requests` 對列表標題套用錯誤編碼。若無法可靠解析標題、日期、`Bid` 或分頁資訊，該次列表覆蓋視為失敗；不得因為解析不到中文就把日期標記成沒有制裁公告。

所有 URL 必須由固定官方 HTTPS origin 和數值 `Bid` 組成，不接受前端傳入任意抓取 URL。

## 建議模組切分

在 `src/maple_reporter/sanctions/` 建立一個深模組，對 Bridge 暴露少量入口：

```text
src/maple_reporter/sanctions/
  __init__.py
  models.py        # typed records, cache schema, sync summary
  official_api.py  # requests Session、分頁、重試、節流
  parser.py        # 公告 table -> masked name/result
  matcher.py       # NFC、嚴格遮罩比對、日期篩選
  repository.py    # sanction_cache.json 與 history 原子更新
  coordinator.py   # single-flight worker、取消、事件、完整/部分提交
```

Bridge 只負責驗證呼叫、啟動 coordinator、投射 DTO 與發送事件；HTTP、HTML、快取規則和角色比對不可散落在 UI bridge 中。

## 持久化模型

### 設定

在 Python、TypeScript 與前端 defaults 同步加入：

```json
{
  "auto_check_sanction_status": true
}
```

利用既有 defaults merge 即可相容舊設定，不需要一次性 config migration。

### 公告快取

新增：

```text
%LOCALAPPDATA%\MapleClassicReporter\config\sanction_cache.json
```

建議 schema：

```json
{
  "schema_version": 1,
  "last_attempt_at": "2026-08-17T12:00:00+08:00",
  "last_complete_sync_at": "2026-08-17T12:04:31+08:00",
  "bootstrap_start_date": "2026-07-19",
  "dates": {
    "2026-08-17": {
      "state": "mutable",
      "last_success_at": "2026-08-17T12:04:31+08:00",
      "bulletin_ids": [82430]
    },
    "2026-08-15": {
      "state": "finalized",
      "last_success_at": "2026-08-16T09:00:00+08:00",
      "bulletin_ids": [82421]
    }
  },
  "bulletins": {
    "82421": {
      "bid": 82421,
      "publication_date": "2026-08-15",
      "title": "新楓之谷：經典版《0815(六)遊戲異常行為制裁公告》",
      "url": "https://maplestoryclassic.beanfun.com/bulletin?Bid=82421",
      "fetched_at": "2026-08-16T09:00:00+08:00",
      "entries": [
        {"masked_name": "雲**間", "result": "永久鎖定"}
      ]
    }
  }
}
```

要求：

- 使用既有原子 JSON 寫入策略或抽出共用 atomic JSON repository。
- 只保存解析後的最小資料，不保存數 MB 的完整 HTML。
- 日期只有在列表完整涵蓋該日，且該日每篇目標公告都成功取得並解析後，才可寫成成功狀態。
- 一個日期即使沒有制裁公告，只要列表覆蓋完整，也可標記成功。
- 今天、昨天的成功日期保持 `mutable`；年齡至少兩日且成功的日期轉為 `finalized`。
- `finalized` 日期不重新請求內文。缺失或失敗的舊日期不是 finalized，仍須補抓。
- 可編輯日期重新解析同一 `Bid` 時，以最新完整 entries 原子取代舊 entries，使官方刪除或補充都能反映。
- 損壞或未知 schema 的快取不得被當成完整覆蓋；保留可診斷 log，回到需要同步的安全狀態。

### 歷史紀錄欄位

保留現有欄位並補齊：

```ts
interface HistoryRecord {
  record_id: string;
  ban_status: 'pending' | 'banned' | 'unbanned';
  ban_date?: string;
  ban_announcement_url?: string;
  ban_bulletin_id?: number;
  ban_result?: string;
  ban_masked_name?: string;
  ban_checked_at?: string;
}
```

- 新紀錄產生 UUID `record_id`。
- 更新舊紀錄時，替缺少 `record_id` 的紀錄補值並原子寫回。
- `banned` 保存所有來源欄位。
- `unbanned` 清除舊的命中來源欄位並更新 `ban_checked_at`。
- `pending` 用於從未具有足夠完整覆蓋的紀錄。
- 現有 `investigating` 或其他歷史值可在前端向後相容顯示，但新後端不再產生它們。

`history.json` 現有的 read-modify-write 會與背景同步競爭。為歷史 repository 加入同一把 process-wide lock，讓新增、清空、批次制裁更新全部在鎖內重新讀取並原子寫入，避免 lost update。維持目前最多 100 筆的限制。

## 日期覆蓋演算法

所有日期計算使用 `ZoneInfo("Asia/Taipei")`，不可依賴電腦目前設定的本地時區。

### 決定所需日期

1. 第一次建立快取：所需範圍為今天至前 29 天，包含首尾。
2. 已有快取：所需範圍包含今天、昨天，以及 `last_complete_sync_at` 之後所有尚未成功完成的日期。
3. 先前失敗或缺失的日期保持在所需集合，直到成功。
4. 若啟動觸發時歷史為空，回傳 `no_history`，不呼叫官方 API。
5. 若自動觸發距 `last_complete_sync_at` 未滿 6 小時，回傳 `fresh`，不呼叫官方 API。
6. 手動觸發略過第 5 項。

### 掃描列表

1. 從列表第 1 頁開始，依序請求。
2. 收集所需日期內所有公告的 `Bid`、標題與日期。
3. 持續翻頁，直到已越過最早所需日期；要多取得足以證明頁面邊界已跨日的資料，避免同一天跨頁時漏項。
4. 每個日期只挑選標題包含「遊戲異常行為制裁公告」的項目。
5. 對 finalized 日期，列表資料只能用來判斷掃描停止點，不取得其公告內文。
6. 列表任何必要頁失敗或格式不可信時，整體覆蓋不完整。

列表頁是發現新日期與 `Bid` 所必需，可以重查；「不再抓」指 finalized 日期的公告內文不再請求。

### 取得公告

- 今天、昨天：每次符合執行條件的同步都重新取得所有目標公告，包括已知 `Bid`。
- 更早且尚未成功完成的日期：取得尚未成功保存的目標公告；全日成功後立即 finalized。
- 更早且 finalized 的日期：零內文請求。
- 一個日期要在其所有目標公告成功後才完成。任何一篇失敗，該日期保持 incomplete。

HTTP client 必須注入 `Session`、clock、random source 和 cancellable wait function。第一個請求可立即執行；後續每個實際網路嘗試前以 `cancel_event.wait(random.uniform(3, 8))` 等待。不要用不可取消的長時間 `sleep`。收到取消時不再送下一個請求，也不把未完成日期提交為成功。

對 timeout、連線失敗、HTTP 5xx 和 429 執行最多兩次重試。429 若提供合理的 `Retry-After`，等待時間取它與隨機延遲的較大值並設安全上限。其他 4xx 視為不可重試。設定明確 connect/read timeout；不得無限等待。

## 公告表格解析

使用標準函式庫 `html.parser.HTMLParser` 或同等的隔離 parser；本功能不需要新增瀏覽器依賴。解析器輸入為公告 HTML 字串，輸出 `list[SanctionEntry]`。

表格會重複出現三組欄位：

```text
角色名稱 | 制裁結果 | 角色名稱 | 制裁結果 | 角色名稱 | 制裁結果
```

解析規則：

- 逐列配對第 1/2、3/4、5/6 欄，而不是假設只有兩欄。
- 忽略表頭、空白 cell、非成對 cell 與純排版內容。
- HTML entity、巢狀 tag、全形／一般空白都要正確取出文字。
- 對角色名和結果做 trim；不要改寫官方結果文字。
- 至少一筆有效 pair 才算成功解析制裁公告。標題吻合但表格完全無法解析時，視為失敗而非空名單。
- 同一公告內完全相同的 `(masked_name, result)` 可去重並維持首次出現順序。

## 遮罩比對

建立純函式，避免在 coordinator 中拼湊 regex。

1. 對完整 ID 與遮罩名稱做 Unicode NFC 正規化及首尾 trim。
2. 將遮罩中的每個 `*` 轉成恰好一個 Unicode code point 的 wildcard。
3. 其他字元全部 `re.escape`，以 `re.fullmatch` 比對。
4. 保持大小寫敏感。
5. 一個中文字、ASCII 字母或數字都各計一個；不得讓一串 `*` 變成任意長度的 `.*`。

範例：

```text
遮罩 雲**間  命中 雲端之間
遮罩 雲**間  不命中 雲間
遮罩 雲**間  不命中 雲端測試間
遮罩 A**z    命中 Ab1z
遮罩 A**z    不命中 ab1z
```

對每筆歷史紀錄：

- 解析 `timestamp` 或 `time` 為台灣日期。
- 只保留 `publication_date >= report_date` 的候選公告。
- 缺少或無法解析檢舉日期時，保持 `pending`，並在同步摘要計入無法判斷數；不要猜日期。
- 任一 entry 符合就算 banned；遮罩同時命中多筆歷史時全部 banned。
- 多個候選按 `(publication_date, bid)` 取最新者作為 UI 來源。
- 保存該 entry 的原始 `result` 供 tooltip 顯示。

## 完整與部分提交

同步必須區分陽性證據與陰性覆蓋：

- 每成功解析一篇公告，可在本機計算確定的 banned 命中。
- 即使稍後有其他公告失敗，這些 banned 命中仍可在同一個鎖定批次寫入歷史。
- 未命中只有在所需日期的列表和公告全部成功、快取原子提交完成後，才能寫成 unbanned。
- 部分失敗時，原本的 banned、unbanned 或 pending 狀態均保留；只更新此次確定的 banned。
- 完整成功時，依最新完整快取重算全部歷史。官方在可編輯公告移除名單時，先前由該公告造成的 banned 可以變回 unbanned。
- `last_complete_sync_at` 只在完整成功後更新。

新增歷史紀錄時進行本機比對：若快取具有足以涵蓋該紀錄日期到最近完整同步時間的完整覆蓋，可寫 banned 或 unbanned；若覆蓋不足，只套用確定的 banned，否則保持 pending。

## Coordinator 與生命週期

Coordinator 使用 single-flight：同一時間最多一個同步 worker。

建議公開方法：

```python
start(trigger: Literal["startup", "manual"]) -> StartSyncResult
get_status() -> SyncStatus
cancel(timeout: float = ...) -> None
rebuild_cache_for_development() -> bool
```

- `startup` 檢查設定、歷史、6 小時 freshness。
- `manual` 忽略設定和 freshness；若已有 worker，回傳 `already_running` 並讓 UI 接續觀察現有進度。
- worker 可為 daemon thread，但 `shutdown` 必須 set cancellation event 並 bounded join。
- 關閉後不得再向已銷毀 WebView emit event。
- `rebuild_cache_for_development` 只在 `dev_mode` 為 true 時允許，並只清除／重建 `sanction_cache.json`；不得碰觸歷史或其他設定。

啟動同步由 `App.tsx` 完成 initial data hydration 後明確呼叫一次。Bridge 仍應有一次性啟動 guard，防止 WebView ready lifecycle 重複觸發。不要由 `get_initial_data` 產生副作用。

## Bridge 與事件契約

在 `web/src/types/index.ts` 和 Bridge 同步加入：

```ts
type SanctionSyncPhase = 'listing' | 'fetching' | 'matching';

interface SanctionSyncStatus {
  running: boolean;
  trigger?: 'startup' | 'manual';
  phase?: SanctionSyncPhase;
  current?: number;
  total?: number;
  message?: string;
  last_complete_sync_at?: string;
}

interface SanctionSyncSummary {
  completed: boolean;
  bulletin_count: number;
  checked_record_count: number;
  newly_banned_count: number;
  changed_to_unbanned_count: number;
  unchanged_count: number;
  indeterminate_count: number;
  failed_request_count: number;
  last_complete_sync_at?: string;
}
```

新增 API：

```ts
start_sanction_sync(trigger: 'startup' | 'manual'): Promise<{
  started: boolean;
  reason?: 'already_running' | 'disabled' | 'fresh' | 'no_history';
  status: SanctionSyncStatus;
}>;
get_sanction_sync_status(): Promise<SanctionSyncStatus>;
get_history(): Promise<HistoryRecord[]>;
rebuild_sanction_cache_for_development(): Promise<boolean>;
```

新增 events：

```text
SANCTION_SYNC_STARTED
SANCTION_SYNC_PROGRESS
SANCTION_SYNC_COMPLETED
SANCTION_SYNC_FAILED
```

事件 payload 要符合上述型別：

- STARTED：目前狀態。
- PROGRESS：phase、current、total、可顯示的繁中 message。
- COMPLETED：summary 與最新 history snapshot。
- FAILED：單一使用者安全錯誤訊息、部分 summary 與最新 history snapshot。

不要把 exception repr、完整官方 HTML 或本機路徑送到前端。

`get_initial_data` 額外回傳目前 sync status 與 `last_complete_sync_at`，讓使用者切換到歷史頁時仍能看到既有 worker 的狀態。

## React UI

### 一般設定

在一般設定加入 Switch：

```text
啟動時自動更新制裁公告
```

預設開啟，使用既有 `onUpdateConfig` 和 optimistic rollback。輔助說明應指出同步在背景進行，且會以隨機間隔存取官方公告。

### 歷史頁

頁首工具列加入帶 icon 的主按鈕：

```text
檢查制裁狀態
```

同步中：

- 改為 spinner icon。
- label 顯示 `檢查中…`。
- 旁邊顯示 `正在檢查第 X/Y 篇公告`；列表階段尚未知總數時顯示具體 phase message。
- 按鈕 disabled，避免重複啟動。
- UI 其他區域維持可操作，不顯示 modal 或全頁遮罩。

按鈕旁顯示：

```text
上次完整檢查：YYYY-MM-DD HH:mm
```

以台灣時間呈現；沒有成功同步時顯示「尚未完成檢查」。

歷史列：

- `pending`：待檢查。
- `banned`：危險色 Badge「已制裁」。Badge hover 與 keyboard focus 時，以既有 Tooltip 元件顯示 `ban_result` 官方原始文字。
- `unbanned`：中性或成功色 Badge「未被制裁」。
- banned 日期欄顯示 `ban_date`。
- banned 狀態旁放公告外連 icon，具有可辨識的 `aria-label`，點擊透過現有安全 external URL bridge 開啟 `ban_announcement_url`。
- Tooltip 不能只靠原生 hover；鍵盤 focus 也要能讀取，並為 Badge／觸發元素提供可存取名稱。

### 摘要通知

整次同步最多發出一則摘要 toast，不逐篇通知。

- 手動完整成功：始終顯示公告數、檢查紀錄數、新增制裁數與解除命中數。
- 背景完整成功：只有 `newly_banned_count > 0` 時顯示同一種摘要；零新增時安靜更新 UI。
- 部分／完全失敗：顯示一則摘要，說明已取得的命中數、失敗數，以及未命中狀態未更新；保留舊結果。

## 實作順序與完成條件

### 1. 建立純資料模型、parser 與 matcher

先用離線 fixture 完成公告列表／內容 parser、NFC 遮罩 matcher 與日期篩選。

完成條件：三組重複欄位、中文／英文遮罩、碰撞、大小寫、日期門檻和最新公告選擇均有 deterministic unit tests。

### 2. 建立 cache/history repository

加入 schema、原子讀寫、process-wide history lock、legacy `record_id` 補值及日期狀態轉換。

完成條件：同步寫入與新增／清空歷史不會 lost update；清空歷史保留公告快取；損壞快取不會產生假的完整覆蓋。

### 3. 建立官方 API client 與 coordinator

實作分頁、日期停止點、mutable/finalized 規則、3–8 秒 cancellable wait、最多兩次重試、single-flight 和完整／部分提交。

完成條件：所有網路與時間行為可注入並在無真實等待、無外網的測試中驗證；finalized 日期的 detail request 數為零。

### 4. 接上 Bridge 與生命週期

加入 API、events、initial sync status、startup guard 和 shutdown cancellation。

完成條件：`get_initial_data` 無同步副作用；重複 startup/manual 呼叫只存在一個 worker；關閉後沒有 event emit。

### 5. 完成 React 設定與歷史 UI

加入 Switch、批次按鈕、進度、最近同步時間、Badge tooltip、公告外連與單一摘要。

完成條件：loading、成功、部分失敗、完全失敗、切頁後回復進度、鍵盤 tooltip 和安全開啟連結都有 component tests。

### 6. 整合驗證

執行 Python、前端 unit tests、型別檢查與 production build。更新 README 或 release notes 中的使用者設定與網路行為說明。

完成條件：全部既有測試與新增測試通過，release bundle 不需系統瀏覽器即可執行制裁同步。

## 必測案例

### Parser/API

- 列表分頁同一天跨兩頁，不漏任何該日公告。
- 同日含維護公告與制裁公告，只下載制裁公告。
- 內容表格一列有三組角色／結果。
- 巢狀 tag、HTML entity、空 cell、重複 entry。
- 中文列表以 UTF-8 bytes 解碼，不受 response encoding 猜測影響。
- 標題吻合但表格解析為零筆時，日期保持 incomplete。
- timeout、429、5xx、不可重試 4xx、第三次嘗試後失敗。
- 每個相鄰 request attempt 的 wait 都落在 3–8 秒，且取消可立即終止 wait。

### 日期快取

- 首次同步恰好涵蓋 30 個台灣日曆日。
- 今天與昨天每次同步都重抓 detail，已知 `Bid` 也會重抓。
- 兩天前成功日期 finalized 且不重抓。
- 兩天前失敗／從未取得的日期仍會補抓，成功後 finalized。
- 應用程式離線 45 天後補齊全部缺口。
- 日期無制裁公告時仍可成功完成。
- 官方修改 mutable 公告：新增 entry、移除 entry、變更 result 均覆蓋快取。

### Matcher/history

- `雲**間` 命中四個 Unicode code point，不命中二字或五字以上名稱。
- NFC 組合前後等價；英文大小寫不同不命中。
- 同一遮罩命中多個歷史 ID，全部 banned。
- 公告早於檢舉日期時不命中。
- 多篇命中取最新日期，再以最大 Bid tie-break。
- 任一非空白 result 都算 banned，原文完整保存。
- 無效歷史日期保持 pending。
- 完整同步可產生 unbanned；部分失敗不能產生新的 unbanned。
- mutable 公告移除 entry 後，完整同步可將該來源造成的 banned 更新為 unbanned。
- 新增歷史只使用快取，不觸發 HTTP。

### 觸發與 UI

- auto setting 預設 true，儲存失敗時 Switch rollback。
- 無歷史時 startup 零 HTTP。
- 完整成功未滿 6 小時時 startup 零 HTTP；manual 仍執行。
- 失敗同步不更新 `last_complete_sync_at`。
- single-flight 阻止雙 worker。
- 進度為 `X/Y`，按鈕 disabled 且顯示 spinner。
- banned tooltip 顯示原始制裁文字，mouse hover 與 keyboard focus 均可使用。
- 公告 icon 只開啟固定官方 HTTPS URL。
- 背景零新增無 toast；背景有新增只有一則摘要；手動每次只有一則摘要；失敗只有一則摘要。

## 驗收標準

功能只有在以下條件全部成立時才算完成：

1. APP 啟動保持可操作，同步不在 UI thread 或 `get_initial_data` 中阻塞。
2. 第一次同步只回溯 30 日；後續不遺漏離線缺口。
3. 今天、昨天可反映官方編輯；成功封存的更早日期不再請求公告內文。
4. 所有實際連續請求具有 3–8 秒隨機、可取消的間隔，且沒有並行爬取。
5. 已爬資料由日期狀態與 `Bid` 共同去重；失敗資料不會被誤認為完成。
6. 一篇公告只解析一次即可批次比對所有歷史 ID，不存在逐 ID 官網請求。
7. 遮罩、日期、碰撞與原始制裁文字完全符合已確認決策。
8. 部分失敗不產生不可靠的「未被制裁」，並保留既有結果。
9. UI 顯示按鈕、icon、逐篇進度、最近完整同步時間、公告來源及可存取 tooltip。
10. 公告快取在清空歷史後仍存在；開發者重建 API 不影響歷史。
11. Python tests、React tests、TypeScript 檢查及 production build 全部通過。
