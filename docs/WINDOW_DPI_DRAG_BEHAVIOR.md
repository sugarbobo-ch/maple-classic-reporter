# Windows 混合 DPI 視窗行為：實作紀錄與驗收契約

本文件是無邊框視窗在多螢幕混合 DPI 環境下的單一事實來源。修改 `native_window.py`、Header 拖曳、最大化／還原、視窗縮放、WinForms 或 pywebview 整合前，先讀完本文件。

## 1. 目標環境

主要重現環境：

| 位置 | 解析度與方向 | Windows 縮放 | DPI |
| --- | --- | --- | --- |
| 左 | 2K 直立 | 125% | 120 |
| 中央主螢幕 | 4K 橫向 | 175% | 168 |
| 右 | 2K 橫向 | 125% | 120 |

關鍵重現動作是按住自訂 Header，從中央螢幕拖到右螢幕，越過 DPI 切換點後繼續向右至少 200 實體像素，再原路拖回。慢速、快速拖曳都必須測試。

## 2. 行為契約

### 2.1 尺寸

- 視窗保存的是邏輯尺寸；同一邏輯尺寸在不同 DPI 上換算成不同實體像素尺寸。
- DPI 切換發生時，內容與外框一起依目標 DPI 等比例改變。
- A 螢幕 → B 螢幕 → A 螢幕後，視窗在 A 螢幕上的實體尺寸必須回到原值，不能累積捨入誤差。
- 最大化尺寸使用所在螢幕的工作區，不得覆蓋工作列。

### 2.2 游標錨點

- DPI 切換瞬間，以使用者按住 Header 的點為 anchor；縮放前後，游標相對視窗的語意位置不變。
- Header 左側品牌區附近採左側固定 anchor；右側視窗按鈕區附近採右側固定 anchor；中間區域採視窗寬度比例 anchor。
- 垂直 anchor 保留按下點相對 Header 的實體位置，並限制在還原後視窗範圍內。
- 最大化後開始「實際拖曳」時，先以該 anchor 還原，再移動。單純點擊 Header 不得還原。

### 2.3 移動

- 整次拖曳只能有一個連續移動來源。
- DPI 轉換後，游標位移與視窗位移保持 1:1；不得加速、減速、跳動或左右 ping-pong。
- 放開滑鼠後，排隊中的舊 WebView movement 不得把視窗噴回前一個螢幕或負座標。

## 3. 現行輸入鏈

```text
Header mousedown
  ├─ React 計算 left / right / proportional anchor mode
  ├─ pywebview.api.drag_window(anchor mode)
  │    └─ prepare_native_drag(): 記錄 anchor；最大化時執行 anchor restore
  └─ pywebview 的 .pywebview-drag-region mousemove
       └─ pywebviewMoveWindow：提供連續視窗位移
```

必要設定與標記：

- `webview.create_window(..., frameless=True, easy_drag=False)`。
- 可拖曳 DOM 必須包含 CSS class `pywebview-drag-region`。`data-pywebview-drag-region` 不會被 pywebview 識別。
- `PyWebViewBridge.drag_window()` 只準備 anchor；連續位移由 pywebview drag region 擁有。
- Dialog 標題列可使用 `pywebview-drag-region` 並呼叫 `drag_window()` 來重設 drag baseline；連續位移必須經由 bridge 的 delta adapter，不能再讓 Overlay 或另一個 native caption loop 同時移動。

目前待完成：`prepare_native_drag()` 仍由 `mousedown` 呼叫，因此最大化時單擊 Header 可能立即還原。修正時應加入 4–8 實體像素的拖曳門檻，並確保第一次有效 mousemove 之前完成 anchor 準備；不得移除 `pywebview-drag-region` 或讓兩個移動來源同時生效。

pywebview 的 `window.move(x, y)` 是絕對 logical desktop 座標；混合 DPI 虛擬桌面上不可直接交給 WinForms 以單一全域比例轉換。現行 bridge 以相鄰事件的 logical delta 呼叫 `move_window_by_drag_delta()`，第一筆事件只建立 baseline。

### 3.1 右側螢幕「按下就往左飄」的根因（2026-08）

這個症狀不需要開啟 Dialog，也不代表一定已經越過 50% DPI 判定點。正常視窗已在右側 125% 螢幕時，只按下主 Header，第一個有效 mousemove 就可能把整個視窗噴向右螢幕左側；從中央 175% 螢幕拖到右側後繼續約 200 實體像素時最容易觀察到。主 Header 與 Dialog Header 都會受到同一條 pywebview movement path 影響。

舊路徑的單位與語意如下：

```text
mousedown
  initialX = clientX, initialY = clientY
mousemove
  x = screenX - initialX       # 原點語意的絕對 logical 座標，不是本次事件 delta
  y = screenY - initialY
  -> pywebviewMoveWindow(x, y)
  -> BrowserForm.move(x, y)
  -> x_phys = x * 目前視窗 DPI 比例
  -> SetWindowPos(x_phys, y_phys)
```

`screenX - initialX` 是以視窗／桌面原點為語意的值；`BrowserForm.move()` 卻用「目前視窗所在螢幕」的單一比例把整個絕對座標重新換算。跨越 175% 與 125% 螢幕後，虛擬桌面的螢幕原點、DPI 比例與座標單位不再能用同一個乘法保持一致，因此第一筆 movement 就可能被換算到右螢幕左緣附近。這也解釋了為什麼症狀看起來像向左跳，而不是只在 50% 邊界閃爍。

現行路徑把絕對值轉成相鄰事件的增量，並只在 native 層以目前實體 RECT 套用增量：

```text
drag_window(anchor_mode)
  -> 清除 drag baseline、準備 anchor／還原幾何
第一筆 pywebview move(x, y)
  -> 只記錄 baseline，不移動視窗
下一筆 move(x, y)
  -> delta = (x - previous_x, y - previous_y)
  -> GetWindowRect() + GetDpiForWindow()
  -> physical_delta = delta * 目前 DPI 比例
  -> SetWindowPos(current_left + dx, current_top + dy)
```

實作責任固定如下：

- `src/maple_reporter/gui/pywebview_bridge.py::_move_window_from_drag_delta()` 保存 baseline，並把相鄰 logical delta 交給 native helper。
- `src/maple_reporter/gui/native_window.py::move_window_by_drag_delta()` 讀取目前實體 RECT 與 per-window DPI，只改變 `x/y`，保留尺寸與 Z-order。
- `PyWebViewBridge.drag_window()` 每次新的左鍵按下都重設 baseline；因此上一段拖曳的座標不能污染下一段拖曳。
- Header／Dialog 可以負責「準備 anchor」；連續 movement 只能由這個 delta adapter 負責。Overlay 不得再宣告整個背景為 drag region，也不得另開 `WM_NCLBUTTONDOWN/HTCAPTION` modal move loop。
- `WM_DPICHANGED` 與 `WM_WINDOWPOSCHANGING` 仍是 DPI 幾何的唯一 owner；delta adapter 只負責一般拖曳的平移，不能在同一事件再建立第二個 SetWindowPos owner。

拖曳狀態以以下順序理解與除錯，每一階段都要有可觀察的完成條件：

```text
IDLE
  -> PRESS_PREPARE   (mousedown：記錄 anchor、清除 baseline)
  -> BASELINE        (第一筆 move：只建立上一筆 logical 座標)
  -> DRAGGING        (後續 move：只套用相鄰 delta)
  -> RELEASE_GRACE   (mouseup：短暫吸收排隊事件)
  -> IDLE             (timer 到期且按鍵已放開，清除狀態)
```

若 `PRESS_PREPARE` 後視窗在 `BASELINE` 尚未完成就跳位，優先檢查是否仍有舊的 `window.move()` 絕對座標路徑或第二個 native move loop；若 `DRAGGING` 中速度改變位置比例，檢查是否把 delta 再乘上錯誤的全域座標／DPI 比例。

## 4. DPI 幾何流程

進程在任何 GUI 建立前啟用 `DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2`。核心狀態位於 `src/maple_reporter/gui/native_window.py`：

- `_WINDOW_DPI[hwnd]`：Windows 最近指派的 DPI。
- `_WINDOW_LOGICAL_SIZE[hwnd]`：穩定邏輯尺寸，計算式為 `physical / (dpi / 96)`。
- `_ACTIVE_DRAG_ANCHOR_RATIOS[hwnd]`：原始抓取點的比例語意。
- `_ACTIVE_DPI_DRAG_GEOMETRY[hwnd]`：DPI 切換後允許的 `(width, height, grab_offset_x, grab_offset_y)`。
- `_DPI_DRAG_RELEASE_DEADLINES[hwnd]`：滑鼠放開後 120 ms 保護期。

訊息責任：

1. `WM_GETDPISCALEDSIZE`
   - 以穩定邏輯尺寸預先回報目標 DPI 的實體尺寸。
   - 若尚無邏輯尺寸，才以目前尺寸乘 DPI 比例。

2. `WM_DPICHANGED`
   - 更新 `_WINDOW_DPI`。
   - 依邏輯尺寸產生目標實體尺寸。
   - 使用游標與既有 anchor 計算穩定 bounds。
   - 將修正後 RECT 傳給原 WinForms WndProc，由 WinForms 完成唯一一次 DPI SetWindowPos 與 WebView2 子視窗重排。
   - 拖曳中將結果寫入 `_ACTIVE_DPI_DRAG_GEOMETRY`。

3. `WM_WINDOWPOSCHANGING`
   - DPI 切換後的唯一幾何守門員。
   - 以目前游標位置減 grab offset，覆寫 WebView 排隊送來的舊 `x/y/cx/cy`。
   - 這個階段同時固定尺寸與位置，避免下一個 mousemove 把視窗拉回舊 DPI 幾何。

4. `WM_LBUTTONUP`、`WM_NCLBUTTONUP`、`WM_CAPTURECHANGED` 與 timer
   - 放開時不立即刪除幾何狀態，而是保留 120 ms，吸收排隊中的最後一筆舊 movement。
   - Timer 確認按鍵已放開且期限到達後，清除 drag state 並停止 timer。

5. `WM_ENTERSIZEMOVE` / `WM_EXITSIZEMOVE`
   - 原生 resize loop 開始時清除 drag geometry，避免 resize 被誤當拖曳。
   - loop 結束後清理狀態並同步 resize overlay。

## 5. 最大化、最小化與還原

- React Header 透過 bridge 呼叫 minimize／toggle maximize／close。
- pywebview 的 `window.events.maximized` 和 `window.events.restored` 轉成 `WINDOW_MAXIMIZED`／`WINDOW_RESTORED`，只用來同步按鈕圖示與前端狀態。
- `WM_GETMINMAXINFO` 使用目標螢幕 `rcWork` 設定最大化位置與尺寸，確保工作列保留。
- 還原尺寸優先取 `_WINDOW_LOGICAL_SIZE`，依目前 DPI 換算；不能把最大化 rect 或一次漂移後的實體 rect 當成新的正常尺寸。
- `calculate_restored_grab_offset()` 的分段規則：
  - `left`：保留左側 offset。
  - `right`：保留游標到右邊緣的距離。
  - `proportional`：以最大化視窗內的水平比例換算到還原寬度。
- 最小化再還原不能改變 normal rect、邏輯尺寸或拖曳狀態。

## 6. Resize 與 Snap 邊界

- Frameless WebView2 子視窗會先吃掉邊緣指標，因此 resize 使用同進程透明 child overlay 接收 hit-test，再以 `WM_NCLBUTTONDOWN` 啟動原生 sizing loop。
- Header 的一般移動目前由 pywebview movement 實作，不是 Windows caption modal loop。因此「拖到頂端觸發完整 Windows Snap／Snap Layout」目前不是已交付能力。
- 若要加入 Snap，應建立獨立實驗分支，證明 caption loop 能與 async JS bridge、DPI anchor 和 WebView capture 共存後才替換移動來源。

## 7. 已證實的失敗方案

以下是回歸防線，不是可重新嘗試的預設設計：

- 在 `WM_DPICHANGED` 先讓 WinForms SetWindowPos，Python 隨後再 SetWindowPos：同一幀雙重幾何 owner，會閃爍或跳位。
- DPI 切換後只修正一次 rect：下一筆 WebView mousemove 仍會套用舊抓取 offset，造成反向拉扯。
- 強制把視窗推到目標螢幕 55% 的 hysteresis：遮蔽判定點但破壞游標 1:1，且不能處理越界後 200 px 才出現的震盪。
- 前端 `zoom` 或 CSS scale 補償 DPI：產生第二套比例系統，造成內容與外框不一致。
- 從 async `drag_window()` 以 `PostMessage(WM_NCLBUTTONDOWN, HTCAPTION)` 啟動 caption loop：實測會先還原但無法持續拖曳。
- 以 `data-pywebview-drag-region` 宣告拖曳區：pywebview 只查詢 `.pywebview-drag-region` selector。
- mouseup 立即清除 geometry：最後一筆排隊 movement 可能在清除後把視窗噴回舊位置。

## 8. 修改流程

1. 先建立能重現目標症狀的最小測試；純 Win32 幾何使用 `tests/test_native_window.py`，bridge 呼叫鏈使用 `tests/test_pywebview_bridge.py`。
2. 明確指定唯一 geometry owner 與唯一 movement source。
3. 修改後先跑自動測試與前端 build。
4. 重新啟動真正的 pywebview 應用程式；Vite build 成功不能替代 WinForms/WebView2 人工測試。
5. 依下一節完整走完硬體矩陣。每個條件都通過才可宣告完成。

## 9. 必須通過的條件

### 9.1 自動驗證

```powershell
rtk uv run pytest tests/test_native_window.py tests/test_pywebview_bridge.py -q
cd web
rtk npm run build
rtk rg -n -F "app-header-drag-region pywebview-drag-region" src/components/Header.tsx
```

測試至少必須鎖定：

- DPI 切換時只存在一個 SetWindowPos owner。
- `move_window_by_drag_delta()` 將 logical delta 轉成目前視窗 DPI 的 physical delta，而不是轉換絕對 desktop origin。
- bridge 的第一筆 pywebview move 只建立 baseline；第二筆才依前後值移動，且每次 `drag_window()` 都會清除上一段 baseline。
- 168 → 120 → 168 DPI 往返後回到原始實體尺寸。
- left／right／proportional 三種 restore anchor。
- mouseup 後的 stale `WM_WINDOWPOSCHANGING` 在 120 ms 內被吸收，期限後狀態清除。
- 最大化 `WM_WINDOWPOSCHANGING` 不受舊 drag geometry 影響。
- Header 的最終 bundle 包含 `pywebview-drag-region` class。

### 9.2 人工硬體驗收

以下每項都要在中央 4K 175% ↔ 右側 2K 125% 雙向執行，並抽測中央 ↔ 左側直立螢幕：

#### 9.2.1 右側螢幕 movement adapter 回歸

- 視窗已在右側 125% 螢幕時，按下 Header 但不移動：RECT 不變；第一個 1–2 實體像素的移動不得讓視窗跳到右螢幕左側。
- 右側螢幕向任一方向拖曳至少 200 實體像素：視窗位移只等於游標位移（允許四捨五入誤差），不得出現一次性大幅左飄或邊界吸附。
- 主 Header 與 Dialog Header 各重複上述按下、慢速拖曳、快速拖曳、放開流程；兩者都只能有一個 movement source。

#### 9.2.2 其他跨螢幕／DPI 條件

- 正常視窗慢速跨界，越界後繼續至少 200 px：零左右閃爍。
- 正常視窗快速跨界：零跳躍、零游標脫節。
- DPI 切換瞬間：視窗依游標 anchor 等比例縮放／放大，anchor 誤差不超過 4 實體像素。
- DPI 切換後繼續拖曳：滑鼠與視窗位移保持 1:1。
- 左右往返兩次：回到同一螢幕時寬高與起始值各相差不超過 1 實體像素。
- 在品牌區、中間區、視窗控制區左側分別拖曳：還原 anchor 符合分段規則。
- 最大化後單擊 Header 並放開：維持最大化。
- 最大化後按住並移動超過拖曳門檻：只還原一次，視窗仍在游標下並可連續拖曳。
- 最小化再還原：回到原螢幕、原 normal rect，後續仍可拖曳與 resize。
- 最大化／還原連續執行兩次：按鈕狀態、工作區位置與正常尺寸一致。
- 放開滑鼠：視窗停在放開位置，不得延遲跳到左螢幕、右螢幕或負座標。
- 八個邊與角 resize：游標形狀與 resize 方向正確，跨 DPI 後仍可使用。

### 9.3 Snap 驗收（實作該功能時才啟用）

- 拖到螢幕頂端能觸發 Windows 原生排列／最大化行為。
- 拖到左右邊緣能觸發 Windows 原生半螢幕排列。
- Snap 後拖離能依 Header anchor 還原。
- 開啟 Snap 不得使本文件 9.1、9.2 的既有條件退化。

## 10. 目前狀態

- Per-Monitor V2、邏輯尺寸、DPI anchor、`WM_WINDOWPOSCHANGING` 守門與 120 ms release grace 已實作並有單元測試。
- 右側螢幕左飄的根因已定位為 pywebview 絕對 logical `window.move()` 與 WinForms 目前 DPI 比例的座標單位衝突；bridge 現在以 delta adapter 逐事件平移，並由 native helper 以目前實體 RECT 套用。
- 最新自動驗證：`190 passed, 8 subtests passed`；`web` production build 已通過。仍需重新啟動實際應用程式，在右側螢幕依 9.2.1 條件人工確認，因單元測試無法取代真實 WebView2 mousemove 與 Windows 多螢幕座標。
- Header 已恢復正確的 `pywebview-drag-region` class，前端 production build 已通過。
- 右側螢幕的實際 WebView2 拖曳仍需依 9.2.1 重啟應用程式後驗證；自動測試不宣稱已完成這項人工驗收。
- 「最大化時單擊 Header 不應還原」尚未完成，屬於下一個修改的第一優先。
- Windows Snap 尚未交付。
