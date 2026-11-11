# 新聞分類帽 · News Sorting Hat

新聞分類帽是一個可由 Python 呼叫的 workflow。輸入使用者問題與 RAG 結果，由程式呼叫模型分類、依類別與 slot 組織段落，再按各段落的候選模組產生內容，輸出經驗證的前端 JSON。執行入口是 [pipeline.py](scripts/pipeline.py)，規則直接來自四層 JSON 定義。

完整流程、驗證重試與 TODO 接入點見 [Python workflow 流程圖](references/workflow.md)。

| 步驟 | 誰負責 | 輸入與輸出 |
| --- | --- | --- |
| 1. 判定文章架構分類 | 程式呼叫 generate，stage 為 classification | 問題與 RAG → 只有 status、primary、secondary 的 [classification](schemas/classification.schema.json) |
| 2. 讀取文章架構 | 程式載入描述檔後呼叫 generate，stage 為 analysis | 分類 → 選中的[類型描述檔](schemas/article-types) → [slot 定義](schemas/slots)；模型依 slot 整理原始 RAG，輸出有文章角色、正文與來源的 analysis |
| 3. 決定各 slot 如何呈現 | 程式按段落提供候選元件，呼叫 generate，stage 為 presentation | 角色、段落及證據 → 按 slot 的 use_when 與[元件契約索引](schemas/components.json)選型，交付依閱讀順序排列的 modules |
| 4. 組裝前端資料 | 程式 build | 驗證模組輸入，從原始 analysis 取值，按模組轉成 [presentation.blocks](schemas/presentation.schema.json)，整份驗證通過後輸出 |

## 檔案層級

| 層級 | 檔案 | 內容與下一層引用 |
| --- | --- | --- |
| 分類清單 | [article-templates.json](schemas/article-templates.json) | 類型 ID、名稱及各類別描述檔路徑 |
| 單一類別 | [event_brief.json](schemas/article-types/event_brief.json) | 類別敘事說明、組織方式；slots 只列 slot 類型 ID |
| 單一 slot | [event_brief.event_lead.json](schemas/slots/event_brief.event_lead.json) | 角色、閱讀問題、證據需求；writing_guidance 包含 instruction、required_elements、output_checks；presentation_modules 列候選元件 ID |
| 單一呈現元件 | [text.json](schemas/components/text.json) | 使用條件、輸入 schema、前端輸出 schema、驗證與範例 |

slot 類型 ID 採 `類別.slot`，例如 `event_brief.event_lead`，對應同名 JSON。這讓同名而用途不同的 slot 各有明確定義。slot 檔內的 id 沿用原角色 ID，供 analysis.article_structure 的 type/slot 配對引用。

## Python 呼叫

Python 3.9+，只使用標準函式庫。輸入依 [rag-input.schema.json](schemas/rag-input.schema.json)，包含 question、as_of、sources。各 source 保留 id、title、url、published_at、updated_at、chunks，chunk 需要 id、locator、text。將既有 RAG 的檢索結果映射到這些欄位，未知日期與網址使用 null。

```python
from scripts.pipeline import run_workflow
from scripts.validate import load_json

rag_input = load_json("examples/mixed-policy.input.json")

# generate(request) 接你現有的模型呼叫，回傳 dict 或 JSON 字串。
presentation = run_workflow(rag_input, generate, max_retries=1)
```

generate 收到一個 dict，每次只處理指定階段。將 instruction 作為模型指令，data 作為引用資料，response_schema 作為結構化回覆格式。模型服務若支援 JSON Schema 可直接使用 response_schema，其中本地 $ref 已完整展開；也可以讓模型依提示產生 JSON，再由 workflow 驗證。

| request 欄位 | 意義 |
| --- | --- |
| stage | classification、analysis 或 presentation |
| instruction | 該階段的任務與新聞整理規則 |
| data | 該階段需要的 RAG、已驗證產物及選中定義 |
| response_schema | 完整的 JSON 輸出 schema |
| attempt | 此階段第幾次呼叫，從 1 開始 |
| repair | 僅在修正回覆時提供 validation_error 與 previous_response |

正常流程呼叫模型三次。analysis 階段一次組織全篇段落與共用證據，可把重疊角色合併同一節。presentation 階段收到每個 section 的候選模組清單，以及實際可用元件的輸入契約。跨節模組須屬於至少一個被引用段落的候選；數據與來源須來自被引用段落。程式從分析結果取出正文、量測值與事件，完成前端 blocks。

每階段輸出驗證通過後才往下執行。max_retries=1 表示允許該階段修正一次。模型呼叫或傳輸失敗會立即拋出 WorkflowError，其 stage 標示失敗位置；驗證持續失敗時也拋出同一錯誤。各次執行保存自己的區域狀態，generate 所收到的 request 為深複製。

## 命令列執行

也可用 CommandModel 對接自己的模型程式。workflow 每階段啟動一次指定命令，將上述 request JSON 寫入 stdin，從 stdout 讀取單一 JSON 回覆。模型程式的紀錄寫到 stderr。timeout 限制單次呼叫時間。

```bash
python3 scripts/pipeline.py rag.json --model-command "python3 my_model_adapter.py" --timeout 120 --max-retries 1 > presentation.json
```

從 Python 使用命令 adapter 時傳入 argv 陣列：

```python
from scripts.pipeline import CommandModel, run_workflow
from scripts.validate import load_json

generate = CommandModel(["python3", "my_model_adapter.py"], timeout=120)
presentation = run_workflow(load_json("rag.json"), generate)
```

[replay_model.py](examples/replay_model.py) 回放合成案例的模型回覆，可直接驗證整個流程：

```bash
python3 scripts/pipeline.py examples/mixed-policy.input.json --model-command "python3 examples/replay_model.py"
python3 -m unittest discover -s tests
```

此案例分類為 policy_evaluation + data_analysis，程式依序載入類別、slot 及元件。成果段落以 bar_chart 引用 goal 與 result，程式由證據取出目標 100 個名額和實際開放 80 個，輸出 [mixed-policy.presentation.json](examples/mixed-policy.presentation.json) 的內容。模型回放測試用於檢查程式交接；實際模型品質需以自己的 generate 與新聞材料評測。

個別階段的讀取與驗證工具仍可直接使用：

```bash
python3 scripts/workflow.py resolve examples/mixed-policy.classification.json
python3 scripts/workflow.py slot policy_evaluation.outcomes
python3 scripts/workflow.py module bar_chart
python3 scripts/validate.py examples/mixed-policy.analysis.json --input examples/mixed-policy.input.json --classification examples/mixed-policy.classification.json
```

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

- 執行環境需要 scripts/ 與 schemas/。由應用程式接入 RAG、generate 模型介面及 Web renderer。模型選擇與 API 憑證由 generate 管理。
- 原有 analysis 與前端 presentation 維持 0.2.0。新版 build 要求角色映射，舊資料仍可用 validate.py 驗證。原本直接讀 article-templates.json 的程式須改為依各筆 file 載入描述檔，或呼叫 resolve。類別描述檔的 `slots` 是有序的類型 ID 陣列，每個 ID 對應獨立 slot 檔。slot 檔以 `presentation_modules` 列出候選元件 ID，`presentation_conditions` 補充專屬適用條件。共用條件與輸入輸出格式放在各自的元件檔。[呈現規則](schemas/presentation-modules.json)補充類型整體的選型提示。
- 程式驗證來源引用、分類一致性、角色覆蓋與模組資料。來源是否真的支持推論、slot 寫作品質、分類品質仍須用新聞材料評估。驗證失敗會以非零狀態結束，錯誤輸出到 stderr。前端只使用已通過整份驗證的結果。渲染文字時使用純文字，來源連結限 http/https。詳見[共用資料契約](references/contract.md)。
