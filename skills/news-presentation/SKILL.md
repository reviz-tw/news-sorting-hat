---
name: news-presentation
description: 依已統整且可追溯來源的新聞 analysis，按原始選型指引的 13 種視覺化與文字、引文基本區塊，產生供程式編譯為前端 presentation 的模組輸入計畫。用於新聞問答呈現規劃、證據驅動的視覺化選型，以及純文字或資料不足時的降級。
---

# 新聞呈現規劃

取得已通過分類與來源比對的 analysis、`workflow.py resolve` 合併後的 profiles 與[元件索引](../../schemas/components.json)。輸出模組計畫，交由本地程式編譯成前端資料。

1. 依 article_structure.nodes 的 roles 對到 profiles 中的 slots，以 reader_question、use_when、evidence_requirements 與實際材料選型。依類型層級的 presentation_hints 決定主要呈現方式與資料不足時的處理；合併角色可共用同一張圖。完整選型原則見 [slot 呈現模組](references/presentation-modules.md)。
2. 每一節安排一個完整 text，可加上有證據的圖表或逐字引文。data_analysis 在可繪圖時依提示提供數量圖表；comparative_analysis 優先以表格並列共同維度。呈現順序保留洞察、前情及限制。
3. 依元件索引的 files[MODULE_ID] 開啟獨立 JSON，讀取 $defs 中的輸入與前端 schema 及 example 的成對範例。也可執行 `python3 scripts/workflow.py module MODULE_ID` 讀取該模組的 input_schema、frontend_schema、驗證條件與渲染說明。依 input_schema 填寫 module_id、id、title、section_ids、evidence_ids、decision、decision_reason、notes 和 data。以 visual_selected 標記圖表，以 text_sufficient 或 insufficient_data 區分文字足夠或證據不足。照片目前僅供規劃。
4. 證據取自所引段落，數值、期間、條件與引文可回查 analysis。折線／長條使用 measurement_ids，時間軸使用 event_ids；text 的 data 填空物件。其餘模組的 data 專屬欄位與前端對應，見[逐模組對照](../../README.md#模組輸入與前端格式)。資料不足時用文字交代具體限制；若 RAG 已有材料而 analysis 遺漏，交回內容整理步驟。
5. 只輸出依閱讀順序排列的 `{"modules":[…]}`，交給 `workflow.py build`。程式會驗證模組專屬輸入、以原始 analysis 組裝 blocks 並驗證整份 [presentation](../../schemas/presentation.schema.json)。[合成計畫範例](../../examples/mixed-policy.modules.json)可供核對。

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
