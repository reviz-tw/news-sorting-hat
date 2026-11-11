# Slot 的呈現模組候選

按文章類別檔的 `slots` ID 陣列讀取 `schemas/slots/<slot_type>.json`，從各 slot 檔的 `presentation_modules` 取得候選元件 ID 與順序。各 ID 預設沿用元件檔的 `use_when`，slot 檔的 `presentation_conditions[模組 ID]` 可指定專屬條件。類型整體的選型規則放在[呈現規則](../../../schemas/presentation-modules.json)的 `article_rules[類型].presentation_hints`。執行 `workflow.py resolve` 後，每個 slot 的 `presentation_modules` 都包含完整的 ID 與適用條件。

依[元件索引](../../../schemas/components.json)的 `files[module_id]` 查元件檔。每份檔案列出使用條件、資料需求與驗證，並以 `$defs.input_schema`、`$defs.frontend_schema` 定義完整輸入與輸出。已支援元件附成對實例 `example.input`、`example.output`；例如[長條圖](../../../schemas/components/bar_chart.json)從 measurement_ids 取得可渲染的 points。

## 從文章角色到區塊

1. 讀取 `analysis.article_structure.nodes[].roles`，找到對應模板 slot 的候選模組、閱讀問題與節點證據。
2. 合併同一節點多個角色的候選，移除不符合閱讀任務或證據門檻者。同一張圖可以服務多個角色，不按角色重複出圖。
3. 套用類型層級的 `presentation_hints`：例如 data_analysis 資料充分時至少一張數量圖表，comparative_analysis 優先比較表。最低張數對整個類型的閱讀任務計算，不對每個 slot 重算。
4. 每個 section 仍以 text 原樣保留完整文字。其他模組可搭配文字，不取代完整回答；候選的排列不直接決定版面順序。
5. 只將 `availability: supported` 的模組輸出為其 `block_type`，依既有契約填 `section_ids`、`evidence_ids`、`decision`、`decision_reason` 與 `notes`。不把候選清單塞入未定義的 analysis 或 block 欄位。
6. 候選提供編輯方向，並非封閉白名單。其他 supported 模組若更適合，可在 decision_reason 說明選擇及證據，不跳過資料契約。

例如 accountability.evidence_chain 可選 text 搭配 table、timeline、network_graph、flowchart、line_chart 或 bar_chart；可追溯照片也是規劃候選。選型取決於本次有何調查證據，不能由「證據鏈」名稱直接生成關係箭頭。

## 照片與尚未支援的模組

`photo` 目前為 `planning_only`，`block_type: null`。它表示編輯上可能適用，並不擴充現有 15 種合法輸出區塊。目前 RAG／analysis 沒有照片資產契約，前端也尚無本專案實作的照片 renderer；不可發出 photo block、假圖片網址或任意 HTML，也不能以文字區塊夾帶圖片格式繞過契約。

若未來提供照片，須建立資產 ID、來源與使用條件、可確認的拍攝時間／地點、圖說、替代文字及驗證狀態，再同步擴充輸入、analysis、presentation、驗證器與 renderer。影像只支持可直接確認的內容；示意或生成影像不能冒充現場或調查證據，新聞報導的刊出日期也不是拍攝日期。

若照片對回答有用但契約不支援，保留完整文字與其他可用模組，於相關 text 的 decision_reason／notes 說明限制。區分「來源沒提供照片」、「已有照片但尚不能輸出」與「不需要照片」，不要一概宣稱缺少事實證據。
