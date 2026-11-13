# 共用資料契約 v0.2.0

## 目錄

- 輸入與各步驟輸出
- 證據與可追溯性
- 呈現與程式驗證
- 模型呼叫與維護

## 輸入與各步驟輸出

`schemas/` 採 JSON Schema Draft 2020-12，所有物件拒絕未定義欄位。輸入 `kind: rag_input`，含 question、as_of、sources；source 含 id、title、url、published_at、updated_at、chunks（id、locator、text）。時間未知用 null；source URL 可 null。chunk ID 在同一 source 內唯一。

分類端先依 [classification schema](../schemas/classification.schema.json) 只輸出 status、primary、secondary。以 `workflow.py resolve` 載入選取的類型描述檔。

內容整理步驟輸出 `kind: analysis`，含 question、as_of、status、classification、title、summary、sections、sources、evidence、limitations。status 為 complete、partial、insufficient；complete 表示目前材料足以回答問題，不代表取得所有歷史新聞。classification.status 為 determined、tentative、undetermined；最後一種 primary 必須 null，其餘必須是類型 ID。

目前分類清單為 12 類，已移除 service_guidance；主／次分類使用此舊值的文件會被驗證器拒絕。須重新判定分類與角色映射，不能只刪除標籤或固定換成另一類。無法歸入保留類型時，使用 undetermined、primary=null，若有 article_structure 則採 unclassified。

呈現模型輸出 [modules 計畫](../examples/mixed-policy.modules.json)，依各個模組的 input_schema 填資料。本地端用 `workflow.py build` 編譯為 `kind: presentation`，含完整且不可變的 analysis 與 blocks。這避免把中間證據另丟掉，也讓前端能由 evidence_id 查來源。前端另行接收資料時，應用程式要比對前後 analysis 相等；CLI 用 `--analysis` 執行此檢查。

`section_ids` 是區塊涵蓋的原稿節；`evidence_ids` 是區塊用到的證據。每節至少有一個 text 區塊精確保留其 body 與 evidence_ids。其他區塊可涵蓋多節或補充一節。原稿摘要由前端直接讀 analysis.summary，來源查 analysis.sources；不用另產一份無來源摘要。

## 證據與可追溯性

立場材料的 claim 可帶 position 擴充，保留 stakeholder_id/name、identity_basis、issue_id/issue、statement_date、context、stance、conditions、reasons；新版 positions_debate 分析應提供。statement_date 是實際發言日期，未知為 null，不能代填刊出日期。stance_comparison 是新增證據類型，含共同 stakeholder_id/issue_id、至少兩個 claim_ids 與 assessment（changed/consistent/conditional/not_comparable/insufficient）。text 說明分析及適用範圍，refs 保留所有被比較主張的來源。前三種判斷要求日期已知、可排序且精度區間不重疊；具體規則見分析 Skill 的 positions-over-time.md。舊 claim 可不含 position，維持 0.2.0 相容性。

分析輸出可帶 `article_structure` 擴充（新版分析 Skill 必須產出，舊 0.2.0 文件仍可省略）。格式見 [article-structure.schema.json](../schemas/article-structure.schema.json)，角色定義由[分類索引](../schemas/article-templates.json)的 file 指向個別描述檔。使用 `--require-structure` 強制新版整合輸出此欄位。

`templates` 依序對應 primary、secondary；無法分類時使用 unclassified。`nodes` 按閱讀順序排列，每個節點含 roles(type/slot)、reader_question、status、reason、section_ids、evidence_ids。角色可合併或映射多節，但每個所選模板 slot 都要且只要交代一次。主類型 core 不可標不適用，無資料時標 missing。covered/partial 需成稿與證據；missing 不得宣稱有支持證據；not_applicable 沒有映射。所有段落均須被結構涵蓋。

驗證器核對模板與分類一致、角色名稱、唯一性、段落覆蓋、證據歸屬及狀態規則；不自動判定正文是否真正回答該角色，也不強制套用固定篇幅。呈現階段保留結構原樣。

所有證據都有 id、kind、text、refs。refs 是非空的 `{source_id, chunk_id}` 陣列，必須落在本次 sources。inference 另有非空 based_on，指向已存在證據，不得循環。

| kind | 額外欄位 | 意義 |
| --- | --- | --- |
| fact | 無 | 來源陳述的事實，不等於獨立查證已完成 |
| claim | speaker、verbatim | 帶歸屬的主張；verbatim 才能當引文 |
| inference | based_on | 模型根據證據整理的推論；text 要明示推論範圍 |
| event | date | 事件日期，精度可年、月或日 |
| measurement | metric、value、unit、region、statistic、period、category | value 為數字或 null；category 可 null；statistic 保留統計口徑 |
| partition | label、total_id、member_ids、mutually_exclusive、exhaustive | 來源支持的互斥完整分配；總量及每個分項均引用 measurement，兩個旗標必須 true |
| entity | label、entity_type、period | 已去重對象，不由同名或共同出現推定身分相同 |
| relationship | from_id、to_id、relationship、directed、period、weight_evidence_id | 逐筆 entity 關係；線寬另引 measurement，未知權重用 null |
| location | label、region_code、boundary_id、latitude、longitude | 有來源的座標或行政區／邊界版本配對；不生成地理多邊形 |
| process_step | label、role、scope、conditions、exceptions | 程序節點；role 為 start／step／decision／end，scope 限定適用範圍 |
| process_link | from_id、to_id、label、conditions、exceptions、rule_basis、version | 程序箭頭；rule_basis 區分 regulation／practice／case，不能把個案變成普遍規則 |
| text_term | term、corpus、period、language、sample_size、sampling、method、group、present、value、unit | 語料與計數／分類方法；僅有出現與否時 value/unit=null，未知樣本數可 null，但不能用權重字級 |

文字內容與數值不能靠 ID 驗證為真；驗證器只確認來源結構與精確的引文包含關係，語意支持程度仍須評估。來源可信度、樣本代表性、因果、日期版本與數值抽取正確性由內容整理步驟判斷。

limitations 含 code（missing_data、incomparable、conflicting、historical、uncertain）、text、evidence_ids。不能取得足夠證據時允許空 evidence_ids，但要寫明缺口。sections 在完全無證據且 status=insufficient 時才可空引用，其餘必須有證據。

與原始輸入一起驗證時，question、as_of、sources 必須完全相等，防止模型改寫或擴充 RAG。不要只驗輸出就以為已與原始檢索核對。

## 呈現與程式驗證

各 slot 的 `writing_guidance` 為物件：`instruction` 說明寫法，`required_elements` 列出該段必須交代的內容，`output_checks` 列出輸出前逐項自查的要求。`resolve` 將完整物件保留在 `profiles[].slots[].writing_guidance`，供 analysis 與 presentation 階段使用。原本將此欄位當作字串的整合端須改讀 `instruction`，並一併傳入兩個清單。

`narrative_logic` 只簡述文章先寫什麼、再寫什麼。slot 的 `role` 命名段落用途，`reader_question` 指出要查明的對象與問題，`evidence_requirements` 列明所需資料，寫作指示則直接說明要引述、比較或解釋什麼。生成的 `sections[].heading` 應依實際內容點出對象、問題或發現，不直接照抄 role；正文須指出具體差異，例如哪個時間、行動或結果的說法不同，避免只寫「存在分歧」。

編輯說明、標題與正文使用台灣常用的繁體中文，句子簡短自然，直接說清楚誰做了什麼。不要為了縮短句子，把完整說明壓成不自然的縮寫。避免直譯和堆疊名詞：例如「帶歸屬的主張」寫成「註明是誰的說法」，「比較口徑」依實際意思寫成「計算方式與比較基準」，「共同維度」寫成「相同的比較項目」。需要的專業名詞可以保留，但要說明意思；逐字引文、正式名稱、JSON 欄位及 ID 不改寫。

必要元素須有材料支持並寫入對應正文；資料缺漏時明示缺口及影響，使用符合證據覆蓋的角色狀態與 reason，不得為滿足清單補造內容。不適用角色沿用原有規則。檢查清單是模型的語意自查指引，不會新增前端欄位，也不代表程式已驗證每個元素的語意完整性；程式仍驗證既有 schema、引用與角色映射。

文章類型檔的 slots 是 slot 類型 ID 陣列，依序讀取 schemas/slots/<slot_type>.json。各 slot 檔的 presentation_modules 是候選元件 ID 陣列，presentation_conditions 保存此 slot 的專屬適用條件。resolve 依順序查[元件索引](../schemas/components.json)與[呈現規則](../schemas/presentation-modules.json)，將元件預設或 slot 專屬的 use_when 展開到 profiles[].slots[].presentation_modules。15 個 supported 模組對應現有 block type；photo 為 planning_only，沒有合法 block_type。呈現階段只能輸出 supported 模組，不把候選數量視為必要區塊數量。

各 blocks 共用 id、type、title、section_ids、evidence_ids、decision、decision_reason、notes。資料欄位由 type 決定：text.body、table.columns/rows、chart.points、timeline.events、quote.evidence_id。schema 以 oneOf 白名單限制元件。

data_analysis 的編輯要求為 insight 先行，資料符合元件門檻時呈現至少一張、可多張數量圖表，詳見呈現規則的 article_rules.data_analysis.presentation_hints。表格可補充精確數字，但不替代此要求；無適用圖種時以 text 的 insufficient_data 與 decision_reason 明示缺口。這些是 Skill 的語意規則，既有 schema／驗證器不自動判斷洞察品質及圖表需求是否完整。

原 HTML 的 13 種圖表與欄位映射見 [components.json](../schemas/components.json)、[元件選型](../skills/news-presentation/references/components.md)。加上 text、quote，共 15 種 block type。12 種新聞回答分類與這組圖表分類互相獨立。

| 新增 type | 專屬欄位 | 來源與檢查 |
| --- | --- | --- |
| stacked_chart | mode、partition_ids | 每組引用 partition 及其總數、分項；核對加總、單位與比較口徑；percentage 由 renderer 按已有分母換算 |
| scatter_plot | x_axis、y_axis、points | 每軸 metric/unit/statistic；每點 label/x_evidence_id/y_evidence_id，category 配對對象、期間與母體一致 |
| bubble_chart | scale、measurement_ids | scale 固定 area；同口徑非負數值，renderer 由面積計算半徑，不以半徑同比縮放 |
| unit_chart | partition_id、unit_value、representation | 正整數單位、整數分配；aggregate_count 或 percentage；餘數明示，不自行四捨五入 |
| map | mode、features | points 或 choropleth；每筆 location_id/measurement_id；值的 region 對應位置 label，區界版本由 renderer 登錄 |
| flowchart | node_ids、edge_ids | process_step/process_link；一入口、至少一出口、所有節點可達且有出口路徑；分支有條件、版本與程序性質一致 |
| network_graph | node_ids、edge_ids | entity/relationship；連結端點存在且同期間，權重必須逐筆支持；同一共同合計不能複用為多條邊權重 |
| word_cloud | mode、term_ids | frequency/topic 為可比較的正數權重，presence 為等大字；保留樣本、語言、方法、群體與語料範圍 |
| treemap | nodes、partition_ids | 每 node 含 id/parent_id/measurement_id；單根、無循環、所有內部節點各有分配，逐層核對子項等於父項 |

新增元件直接引用證據，避免再複製一套可能漂移的數字。partition 本身也需來源，不以加總通過推定分類真的互斥完整。自動檢查能核對算術與連結，不能自動驗證法規分支是否完整、語料方法是否適當或區界是否與報導期間相容；這些仍需內容整理步驟與應用程式核對。

可視化必須引用證據子集，區塊的證據也必須來自其 section_ids 的證據聯集。時間軸至少兩個事件；圖表至少三個／兩個非缺值；表格儲存格需有證據；引文需能在 cited chunk 原文找到相同字串。

CLI 使用標準函式庫，實作本 repo 所用的 schema 關鍵字：`$ref`（限 schemas/ 內相對路徑與 JSON Pointer）、`type`、`const`、`enum`、`properties`、`required`、`additionalProperties`、`items`、`minItems`、`uniqueItems`、`minLength`、`pattern`、`oneOf`。支援布林 schema，例如 planning_only 元件以 false 拒絕輸入輸出。拒絕未知關鍵字，避免規格擴充後靜默漏驗。它不是通用 JSON Schema 引擎；正式環境可換完整 Draft 2020-12 引擎，仍保留語意驗證。

額外檢查所有 ID、日期是否合法、圖表數值是否等於證據、序列的指標／單位／地區／統計方式、時間排序與連續期間、表格欄寬、區塊涵蓋、引用閉合與 inference 無循環。錯誤即拒絕渲染。只接受有限 JSON 數字，不接受 NaN／Infinity。

schema 語法與引用驗證不能代替編輯品質測試；下一步需用真實 RAG 做分類、遺漏、衝突保留、數字與來源抽查。合成 fixture 的通過只證明契約與檢查流程可運作。

## 模型呼叫與維護

`scripts.pipeline.run_workflow(rag_input, generate)` 依序呼叫分類、內容整理、呈現三階段。每階段由文字模板產生已填入資料及完整 schema 的 request.prompt，另保留 instruction、data、response_schema 等結構化欄位。程式驗證第一關分類、第二關來源與角色映射、第三關模組資料與段落候選，最後回傳 presentation。

分類索引的 reading_task、coverage、boundaries 提供機器可讀的分類依據。描述檔與各元件 JSON 提供內容規則與資料契約，由 Python 讀取並插入 skills/ 下的 prompt template，模型不需開啟檔案或連結。`build_slot_request()` 可另行準備符合 slot-draft.schema.json 的單段草稿請求；它不會自動合併成 analysis。詳見 [模板與草稿契約](prompt-templates.md)。

驗證錯誤可在同一階段有限次修正，預設一次；模型或傳輸失敗立即停止並帶出 WorkflowError.stage。重新執行會重新呼叫三個階段。實例與接入介面見 [README](../README.md)。

沿用既有 0.2.0 前端契約。變更時同步更新描述檔、schema、模型指令、驗證器與範例。前端以整份驗證通過的 presentation 為渲染單位。
