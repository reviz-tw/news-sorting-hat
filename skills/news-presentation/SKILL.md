---
name: news-presentation
description: 依已統整且可追溯來源的新聞 analysis，按原始選型指引的 13 種視覺化與文字、引文基本區塊，輸出前端 presentation JSON。用於新聞問答呈現規劃、證據驅動的視覺化選型，以及純文字或資料不足時的降級。
---

# 新聞呈現規劃

先讀 [Slot 呈現模組](references/presentation-modules.md)、[共用模組目錄](../../schemas/presentation-modules.json)、[元件選型](references/components.md)、[共用契約](../../references/contract.md) 與 [presentation schema](../../schemas/presentation.schema.json)。先取得 news-analysis 的有效產物；不要從零散原文直接挑圖。

## 流程

1. 原樣保留輸入 analysis，不改分類、文字、數值、證據或來源。若發現矛盾或缺少證據，交回第一階段修正，不在呈現階段偷偷改稿。
2. 先讀 analysis.article_structure（若有）的角色、reader_question 與缺口，再辨識各節閱讀任務，決定「圖比文字多提供什麼」。保留文章結構原樣，以任務組織 blocks，允許多段合成表格或一段拆成文字加圖；文章角色不直接決定圖種。
3. 選型只用 [元件清單](../../schemas/components.json) 的 13 種視覺化，另保留 text、quote，共 15 種。題材或主類型只能提供方向；實際證據結構、比較口徑及資料品質才決定能畫什麼。選中圖種前，讀下方對應的原指引擷取。
   依節點 roles 查對應 slot 的 presentation_modules，按 module_id 讀取模組目錄的門檻與 availability，合併重疊候選後選擇。候選不全選，planning_only（如 photo）不可輸出為 block；保留完整文字並說明目前呈現限制。
   同時讀取 [文章模板](../../schemas/article-templates.json) 的 presentation_hints（若有）。event_context 的 sequence／turning_points 優先對應 timeline：事件先後有閱讀價值且至少有兩筆具可靠日期的 event 時，產出時間軸並保留文字。證據不足時以 text + insufficient_data 說明缺口；文字已足夠時記錄 text_sufficient 與原因，不因類型名稱硬補事件或日期。other_perspectives 收尾依候選採文字、引文或比較表，觀點與已確認事件分開呈現；影響事件重建的分歧也須保留在相關段落，不將 claim 直接填入 timeline。
   主／次類型含 data_analysis 時，依模板的 minimum_chart_count 規則，先呈現 insight 與 knowledge_comparison 的文字（可合併一節；缺對照來源則明示），再安排至少一張符合資料門檻、支持該發現的數量圖表；有多個獨立閱讀問題時可用多張，各自說明用途與證據。資料充分不能以 text_sufficient 全文略過圖表。無適用圖種時用 text + insufficient_data 說明具體缺口，可輔以表格；不能用無關圖或表格湊數。原文有數字但 analysis 未抽取 measurement 時，交回第一階段補整理。
   主／次類型含 comparative_analysis 時，依模板優先製作比較表：對象為列、共同維度為欄，各格帶來源與條件，區分未知、不適用與不可比；依需要轉置或拆表。保留範圍介紹、關鍵差異與適用條件的完整文字。只有極短且文字足夠的比較才以 text_sufficient 說明不製表；缺乏對象或維度則用 insufficient_data。
   accountability 的 evidence_chain 可搭配資訊圖表：依模板選 table、timeline、network_graph、flowchart 或數量圖表，說明調查材料及核對關係。只使用既有元件，逐項帶來源；不虛構調查步驟、不以箭頭暗示未證實因果、不由關係圖推定違法，保留反證與證明界線。
   discourse_analysis 通常以 table 展示框架、群體／時期、例句與來源的分析結果；量化資料符合門檻時另用長條、折線或堆疊圖。缺可靠統計時保留質性表與引文，明示不能量化；文字雲只補充概覽，不取代脈絡分析。
4. 為每個區塊填 section_ids、evidence_ids、decision 與 decision_reason。用 text_sufficient 表示文字足夠，visual_selected 表示採用圖表／表格／時間軸，insufficient_data 表示值得視覺化但證據不足。引文屬文字呈現。
5. 保留每一節的完整文字：至少以一個 text 區塊原樣對應該節，圖表作補充。文字是可獨立閱讀的完整回答；避免只剩圖表而遺漏限定條件。
6. 依選中圖種的資料契約引用第一階段證據。折線、長條複製 measurement 的數值；散佈圖配對同對象的兩個 measurement；比例圖引用 partition；流程與網絡引用逐筆節點／連結；地圖引用 location；詞雲引用 text_term。圖所需結構若第一階段未提供，交回補整理或降級文字，不能在第二階段新增事實。表格每格有來源，時間軸保留 event 原日期與文字；quote 保留 verbatim claim 的歸屬與原文。
7. 缺值用 null，線段斷開並在 notes 說明；不得補點、插值或將未知當零。不要把不同粒度的統計、預測與實測、目標與成果串成同一條線。不能製圖時使用文字並解釋缺少哪些資料。
8. 輸出 `kind: presentation`、`schema_version: 0.2.0`，包含原樣 analysis 與 blocks。提交程式驗證後才交 Web render；不要把模型自行宣告「已驗證」當成驗證結果。

## 按需讀取的原指引

- [01 折線圖](references/forms/01-line-chart.md)
- [02 長條圖](references/forms/02-bar-chart.md)
- [03 堆疊圖](references/forms/03-stacked-chart.md)
- [04 散佈圖](references/forms/04-scatter-plot.md)
- [05 比例氣泡圖](references/forms/05-bubble-chart.md)
- [06 單位圖示／點陣圖](references/forms/06-unit-chart.md)
- [07 地圖](references/forms/07-map.md)
- [08 比較表／矩陣](references/forms/08-table.md)
- [09 事件時間軸](references/forms/09-timeline.md)
- [10 流程圖](references/forms/10-flowchart.md)
- [11 關係網絡圖](references/forms/11-network-graph.md)
- [12 文字雲](references/forms/12-word-cloud.md)
- [13 矩形樹圖](references/forms/13-treemap.md)

指引的教學數據不是 RAG 證據，不得填入本次回答。基本形式的 schema 不涵蓋原指引每個應用變體，不輸出未定義欄位。

## 呈現界線

- 不新增事實、數值、來源或模型推論；標題、圖說也受此限制。
- 不使用圖表語法、任意 HTML、JavaScript 或未定義的元件名稱。
- 一般回答不強制製圖；data_analysis 在資料門檻成立時至少一張數量圖表。資料不足與文字足夠是不同決策，明確記錄。
- 不將來源發布日當事件日，不省略影響解讀的統計口徑與限制。
