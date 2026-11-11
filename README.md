# 新聞分類帽 · News Sorting Hat

新聞分類帽將使用者問題和檢索到的新聞片段整理成可追溯的回答。分類先獨立完成，本地端再依分類取得文章描述檔，模型按其中的 slot 整理材料與選擇呈現模組，最後由程式組出前端 JSON。

| 步驟 | 誰負責 | 輸入與輸出 |
| --- | --- | --- |
| 1. 判定文章架構分類 | 分類模型，使用 [news-classification](skills/news-classification/SKILL.md) | 問題與 RAG → 只有 status、primary、secondary 的 [classification](schemas/classification.schema.json) |
| 2. 讀取文章架構 | 本地程式按 ID 查[索引](schemas/article-templates.json)，本地模型使用 [news-analysis](skills/news-analysis/SKILL.md) | 分類 → 選中的[類型描述檔](schemas/article-types) → [slot 定義](schemas/slots)；模型依 slot 整理原始 RAG，輸出有文章角色、正文與來源的 analysis |
| 3. 決定各 slot 如何呈現 | 本地模型使用 [news-presentation](skills/news-presentation/SKILL.md) | 角色、段落及證據 → 按 slot 的 use_when 與[元件契約索引](schemas/components.json)選型，交付依閱讀順序排列的 modules |
| 4. 組裝前端資料 | 本地程式 workflow.py build | 驗證模組輸入，從原始 analysis 取值，按模組轉成 [presentation.blocks](schemas/presentation.schema.json)，整份驗證通過後輸出 |

## 檔案層級

| 層級 | 檔案 | 內容與下一層引用 |
| --- | --- | --- |
| 分類清單 | [article-templates.json](schemas/article-templates.json) | 類型 ID、名稱及各類別描述檔路徑 |
| 單一類別 | [event_brief.json](schemas/article-types/event_brief.json) | 類別敘事說明、組織方式；slots 只列 slot 類型 ID |
| 單一 slot | [event_brief.event_lead.json](schemas/slots/event_brief.event_lead.json) | 角色、閱讀問題、寫作指引、證據需求；presentation_modules 列候選元件 ID |
| 單一呈現元件 | [text.json](schemas/components/text.json) | 使用條件、輸入 schema、前端輸出 schema、驗證與範例 |

slot 類型 ID 採 `類別.slot`，例如 `event_brief.event_lead`，對應同名 JSON。這讓同名而用途不同的 slot 各有明確定義。slot 檔內的 id 沿用原角色 ID，供 analysis.article_structure 的 type/slot 配對引用。

## 用一筆資料走完整個流程

Python 3.9+，只使用標準函式庫。下列檔案是合成的模型回覆與 RAG，可直接重播。第一關收到「這個政策執行得如何？請搭配數據說明目標與成果」，回傳：

```json
{"status":"determined","primary":"policy_evaluation","secondary":["data_analysis"]}
```

```bash
python3 scripts/validate.py examples/mixed-policy.input.json
python3 scripts/validate.py examples/mixed-policy.classification.json
python3 scripts/workflow.py resolve examples/mixed-policy.classification.json
python3 scripts/validate.py examples/mixed-policy.analysis.json --input examples/mixed-policy.input.json --classification examples/mixed-policy.classification.json
python3 scripts/workflow.py slot policy_evaluation.outcomes
python3 scripts/workflow.py module bar_chart
python3 scripts/workflow.py build --classification examples/mixed-policy.classification.json --input examples/mixed-policy.input.json --analysis examples/mixed-policy.analysis.json --plan examples/mixed-policy.modules.json
python3 -m unittest discover -s tests
```

`resolve` 依主次順序載入兩份類別描述檔，按 slots 陣列中的類型 ID 讀取 `schemas/slots/<slot_type>.json`，再讀取各 slot 列出的元件。slot 定義包含閱讀問題、撰寫方式、證據需求與候選模組 ID。分類為 undetermined 時只載入 unclassified。每個分類可獨立讀取，例如 [policy_evaluation.json](schemas/article-types/policy_evaluation.json)。在 analysis 中保留第一關分類，這時才填理由、標籤和證據 ID。若確實需要改分類，回到第一關，重新解析描述檔。

本例的 outcomes slot 比較同年度的目標與成果。模型在[模組輸入](examples/mixed-policy.modules.json)指定 `bar_chart` 與 `data.measurement_ids = ["goal","result"]`。程式從證據讀出「年度目標」100 個和「年底實際開放」80 個，產生 points、單位與零基線；前端可按 evidence_id 回查原文。可比對[完整前端輸出](examples/mixed-policy.presentation.json)。

## 模組輸入與前端格式

每個元件各有一份 JSON，可由下表直接開啟。檔案中的 `$defs.input_schema` 定義模型提交的一筆模組輸入，`$defs.frontend_schema` 定義前端收到的一筆 block。兩者均列出完整物件與巢狀欄位；`example.input`、`example.output` 示範同一筆資料如何轉換。引用的段落與證據依 [analysis schema](schemas/analysis.schema.json) 取得。前端總 schema 直接引用各元件的 frontend_schema。

`python3 scripts/workflow.py module <module_id>` 輸出該模組的用途、證據條件、驗證、渲染規則，以及完整的 `input_schema` 和 `frontend_schema`（含型別、必填、陣列成員與列舉值）。模組所列 evidence_kinds 是繪製資料會用到的證據種類；text 與 table 可引用任一種，network_graph 只有畫邊權重時才需要 measurement。所有輸入放在同一個 `{"modules":[…]}` 計畫，陣列順序即閱讀順序。每筆輸入共用 id、module_id、title、section_ids、evidence_ids、decision、decision_reason、notes，專屬欄位放在 data。前端每個 block 使用 type，專屬欄位在 block 頂層。

| module_id | 模組專屬輸入 data | 前端 block 專屬欄位 |
| --- | --- | --- |
| [text](schemas/components/text.json) | 空物件，以 section_ids 指定一節 | body 取自原段落 |
| [quote](schemas/components/quote.json) | evidence_id | evidence_id 指向具名逐字 claim |
| [table](schemas/components/table.json) | columns、rows，每格含文字及 evidence_ids | columns、rows |
| [line_chart](schemas/components/line_chart.json) | 依期間排序的 measurement_ids | metric、unit、region、statistic、points |
| [bar_chart](schemas/components/bar_chart.json) | 依比較順序排列的 measurement_ids | 同上，另含 zero_baseline |
| [timeline](schemas/components/timeline.json) | 依日期排序的 event_ids | events，每筆含 date、text、evidence_id |
| [stacked_chart](schemas/components/stacked_chart.json) | mode、partition_ids | mode、partition_ids |
| [scatter_plot](schemas/components/scatter_plot.json) | x_axis、y_axis、points，各點引用兩軸的 measurement | x_axis、y_axis、points |
| [bubble_chart](schemas/components/bubble_chart.json) | scale、measurement_ids | scale、measurement_ids |
| [unit_chart](schemas/components/unit_chart.json) | partition_id、unit_value、representation | partition_id、unit_value、representation |
| [map](schemas/components/map.json) | mode、features，各筆配對位置與數值 | mode、features |
| [flowchart](schemas/components/flowchart.json) | node_ids、edge_ids，引用程序步驟與連結 | node_ids、edge_ids |
| [network_graph](schemas/components/network_graph.json) | node_ids、edge_ids，引用實體與關係 | node_ids、edge_ids |
| [word_cloud](schemas/components/word_cloud.json) | mode、term_ids | mode、term_ids |
| [treemap](schemas/components/treemap.json) | nodes、partition_ids | nodes、partition_ids |
| [photo](schemas/components/photo.json) | planning_only，尚無資產輸入契約 | 無，build 拒絕此模組 |

## 整合與相容性

- 此 repo 提供三個模型步驟的說明、描述檔、契約與本地 CLI。實際的 RAG、模型推論服務及 Web renderer 由應用程式接入。打包整個 repo 以保留相對引用。參見 [Agent 載入說明](references/agent-compatibility.md)。
- 原有 analysis 與前端 presentation 維持 0.2.0。新版 build 要求角色映射，舊資料仍可用 validate.py 驗證。原本直接讀 article-templates.json 的程式須改為依各筆 file 載入描述檔，或呼叫 resolve。類別描述檔的 `slots` 是有序的類型 ID 陣列，每個 ID 對應獨立 slot 檔。slot 檔以 `presentation_modules` 列出候選元件 ID，`presentation_conditions` 補充專屬適用條件。共用條件與輸入輸出格式放在各自的元件檔。[呈現規則](schemas/presentation-modules.json)補充類型整體的選型提示。
- 程式驗證來源引用、分類一致性、角色覆蓋與模組資料。來源是否真的支持推論、slot 寫作品質、分類品質仍須用新聞材料評估。驗證失敗會以非零狀態結束，錯誤輸出到 stderr。前端只使用已通過整份驗證的結果。渲染文字時使用純文字，來源連結限 http/https。詳見[共用資料契約](references/contract.md)。
