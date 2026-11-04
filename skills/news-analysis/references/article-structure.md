# 文章抽象結構

分類後讀取 [article-templates.json](../../../schemas/article-templates.json) 中 primary 與 secondary 對應的模板。JSON 是唯一的角色定義；其中的 narrative_logic 說明敘事順序，slots 定義每個內容角色的閱讀問題、核心程度、證據需求與 presentation_modules 候選。這是本專案的編輯骨架，不是 READr 官方文章格式。

## 結構的兩個層次

模板描述「這種類型通常如何回答問題」；analysis.article_structure 描述「這次實際如何組織回答」。後者不重複寫整篇正文，透過 section_ids 連接成稿，透過 evidence_ids 連接支持材料。結構是一份可公開檢查的編輯規劃，不要求模型輸出內部推理過程。

| 類型 | 預設文章順序 |
| --- | --- |
| event_brief | 事件核心 → 已知結果 → 必要背景 → 未明事項 → 其他說法與回應（有需要時） |
| human_story | 人物背景與處境 → 經歷與選擇 → 處境限制 → 經驗的邊界 → 側訪與他人觀察（有材料且相關時） |
| event_context | 現在的位置 → 關鍵經過 → 轉折與連結 → 脈絡缺口 → 其他方觀點（有需要時） |
| issue_explainer | 核心解答 → 作用機制 → 理解背景 → 法規依據與法律觀點（相關時）→ 不同意見與觀點 → 範圍與例外 |
| positions_debate | 議題背景與共同問題（含觀察期間）→ 各方逐時主張 → 同一對象的立場變化 → 分歧與共通點 → 未解爭議 |
| data_analysis | 核心洞察（insight）→ 既有認識與新發現的對照 → 圖表與數據證據、比較基準 → 差異與例外 → 解讀限制 |
| comparative_analysis | 比較範圍 → 共同維度與比較表 → 關鍵差異 → 適用與不可比 |
| accountability | 必要背景 → 調查摘要 → 問題起點與質疑 → 調查內容與證據鏈 → 權責與回應 → 尚待追查 |
| discourse_analysis | 語料範圍與方法 → 敘事框架 → 分析結果與資料 → 群體／時期差異與視覺化 → 代表性限制 |
| impact_scenarios | 影響範圍 → 影響途徑 → 條件情境 → 不確定性 |
| policy_evaluation | 目標與基準 → 投入與執行 → 成果與落差 → 歸因與限制 |
| claim_verification | 事件緣由與查證背景 → 待查說法 → 證據對照 → 限定結論 → 判定邊界 |

## 組合與縮放

1. 以 primary 的 narrative_logic 作骨架；只插入有助於回答問題的 secondary 角色。例如 issue_explainer 的機制解釋之後，加入 positions_debate 的各方主張與分歧。
2. 模板順序是預設，不是死板的寫作限制。依問題調整順序並在 composition_reason 說明；nodes 陣列順序就是本次閱讀順序，sections 依此組織成稿。
3. 內容重疊可合併角色：一個 node 的 roles 可同時列出主類型與次類型的多個 slot。每個 slot 只分配一次；同一節可以承接多個角色，一個角色也可對應多節。
4. 所選模板的每個 slot 都需有交代。主類型 core 角色必須處理，無證據時標 missing；conditional 角色與次類型不適用的角色可標 not_applicable 並寫明原因。若一個次類型沒有任何有用角色，移除該次類型，不保留裝飾性標籤。
5. 短答可以只生成一節。例如只問何時重新開館，事件核心一節即可；其他不必要背景標 not_applicable，不為了模板新增長文。
6. 無法分類時 templates 使用 ["unclassified"]，套用 fallback 的 answer、limits 兩角色。完全沒有證據時可以用 missing 節點連到說明無法回答的段落。

人物敘事沿用 person_context 核心角色，明確作為「人物背景與處境」開場：先交代與故事相關的身分、當時生活／工作情境及其與事件的關係，再進入 experience（經歷與選擇）。不是每篇都要完整履歷或固定人口欄位；短文可將兩角色合併一節，仍先背景後經歷。作為次類型時，在相應人物段落先介紹即可。只知道部分背景就標 partial，必要背景完全缺乏則標 missing，不補造生平或由身分推定動機。呈現以文字為主，照片目前僅為規劃候選，不能取代背景說明。

人物故事收尾新增 side_interviews（側訪與他人觀察）條件角色，以相關家人、同事、同行等觀察補充、印證或對照本人自述；保留與當事人的關係、觀察／發言時間的已知範圍、來源，區分親身觀察、轉述與評價。可用 text、quote，必要時以 table 並列觀察，不要求正反平衡或等量篇幅。只整理取得的側訪，沒有訪談不等於拒訪。無必要時標 not_applicable，必要但未取得時標 partial/missing；關鍵矛盾須在相應經歷段落一併交代。既有 human_story 結構需補此角色，可與經歷或經驗邊界合併節點，不強制新增長段落。

事件事實敘述的 other_accounts（其他說法與回應）是條件式收尾，可用 text、quote 或必要時的 table。它補充與事件直接相關的主張、回應、更正及其來源／時間；unknowns 則交代未確認範圍，兩者重疊可合併節點。一般日期短答可標 not_applicable；涉及直接指控、關鍵事實爭議或明確要求多方回應，而必要材料未取得時，應標 partial/missing。未檢索到回應不等於拒絕回應，不補造另一方。若爭議或更正會改變事件核心，開頭與結果也要保留歸屬或修正，不能到收尾才揭露。既有 event_brief 結構需補此角色，即使不適用也要交代理由。

事件脈絡與重建新增 other_perspectives（其他方觀點）作為條件式收尾，以 text、quote 或 table 呈現其他參與者、受影響者等對經過、轉折與影響的理解。保留發言者身分、事件關係、已知發言時間與依據，區分親歷、事後評價與因果主張，不強配正反。必要觀點未取得時標 partial/missing，無需展開時可標 not_applicable；不能將缺回應寫成拒絕回應。影響時間線或轉折的分歧須同步標於相應段落，claim 不直接充作 timeline 的 event。可與 open_questions 合併缺口說明，立場比較重要時搭配 positions_debate。既有 event_context 結構需補此角色。

議題解釋每次都要評估 perspectives（不同意見與觀點）是否影響理解。政策選擇、價值分歧、解釋爭議或不同受影響者處境，應納入具歸屬的主張、理由與證據。只取得部分相關觀點時標 partial，必要觀點完全缺乏時標 missing；不能把缺資料標成不適用。純概念或操作機制且觀點差異與問題無關時，才可說明 not_applicable。觀點不強分正反，不把有證據與無證據的說法呈現為同等確定。

議題解釋新增 legal_context（法規依據與法律觀點）條件角色，說明規範如何影響議題與機制，整理有來源的法律解釋分歧。保留已知法域、法規名稱／條次、版本／生效時間及適用條件；不憑記憶補寫法條或案號。區分規範文本、報導轉述、機關解釋、法院見解與專家評論，不自行認定相同效力或替個案下法律判斷。只有轉述時明示未核對原文；依來源區分草案、已通過與已生效，歷史資訊不證明現行法律。相關且部分支持標 partial，必要卻缺依據標 missing，無關才標 not_applicable。可與 mechanism、perspectives 或 boundaries 合併角色；呈現採文字、比較表、符合契約的引文或程序圖。既有 issue_explainer 結構需補此角色。

若爭點比較是重要次要任務，選 issue_explainer + positions_debate；可將 perspectives 與 positions、fault_lines 合併到同一節點，保留各角色映射。若使用者主要問各方分歧，則改以 positions_debate 為主類型。

positions_debate 沿用 issue 核心角色，明確作為「議題背景與共同問題」開場：交代必要前情、制度或提案內容、爭議起點，以及各方在討論什麼與觀察期間，再進入各方主張。不直接列支持／反對，也不把某方的爭議框架當成共同事實。短答可合併背景與主張，作為次類型也可共用已有背景段落；仍保留角色映射。缺少必要背景時標 partial/missing，不從立場反推起因。

positions_debate 的 position_evolution 要比較同一 stakeholder 對同一爭點的逐時主張。時間與身分是資料的一部分，不能只在段落標題寫年份。依 positions-over-time.md 區分 changed、consistent、conditional、not_comparable、insufficient。單一時點也要交代無法判定變化，不把這個缺口標成不適用。

data_analysis 的 finding 是核心洞察（insight），保留原 ID。主類型的摘要與第一節先回答「資料揭露什麼，對問題有何意義」，再展開口徑及數字。例：「2020–2024 年 PM2.5 年平均連年下降，從 20 降至 15 µg/m³；這段資料支持持續下降，不能單憑此判定政策成效。」不要只以逐年數字清單開場，也不為了吸引讀者誇大成異常或因果。次類型在相應段落先交代 insight 即可。無可靠發現時以缺口與可判斷範圍開場，標 partial/missing。

data_analysis 的 knowledge_comparison 是洞察之後的核心角色，對照有來源的既有研究、報導、調查或公開說法與本次發現，說明是印證、補充、修正、挑戰或不可比較。與 basis 的統計口徑說明分開：此段回答「我們對議題的理解增加或改變了什麼」。保留既有認識的提出者、時間與適用範圍，不泛稱社會共識；政策目標也不等於公眾預期。模型作的對照判斷用 inference，based_on 同時引用舊說與新資料。先核對母體、定義、期間與方法，不能把口徑改變當成推翻舊說。缺基準材料標 missing，部分支持標 partial；短文可與 finding 合併，主類型仍須處理此核心角色。既有 data_analysis 結構需補 knowledge_comparison。

accountability 以 background 與 investigation_summary 兩個核心角色開場，先讓讀者理解原本制度／承諾／事件，再知道調查揭露什麼及確認到哪裡，之後展開證據鏈與權責回應。兩角色可合併一個節點或一節短文，避免冗長背景；摘要中的發現須有後文證據支持，不預斷責任。頂層 summary 亦概述背景與發現，但不能取代正文角色。新版 accountability 結構須補上這兩個角色；沒有資料時明示缺口。

accountability_question 是「問題起點與質疑」：先說哪份文件、數據、現象或說法提供線索，接著對照承諾／標準／另一方說法，最後提出可查證的問題。例如材料同時記錄「契約承諾每月檢查」與「三個月紀錄空白」，可以追問是否未執行或紀錄缺漏；紀錄空白本身尚不能斷定未檢查。來源未交代記者最初如何發現問題時，只描述現有材料的疑點，不編造檢舉或採訪過程。後續 evidence_chain 才展開支持、反證與替代解釋。

evidence_chain 是「調查內容與證據鏈」，回答查了什麼、如何核對、支持哪個發現及能證明到哪裡。只敘述原文提供的查證工作；模型整合材料不是另外完成訪查。依需要以表格對照文件／說法、時間軸串事件、關係圖說明有證據的權責或資金往來、流程圖呈現有來源的查證步驟，數量落差可用統計圖。資訊圖表由既有元件組成，不另創 infographic type；每項連回來源，並保留反證、替代解釋與限制。

discourse_analysis 的 analysis_results 是核心角色，整理框架、例句與資料的對照，不只列語料。模型歸納須標 inference 並連回證據；量化須有來源或上游提供可核對方法的計數、樣本與分母。結果表可呈現質性對照，數量圖僅在門檻成立時使用；多重框架不可當互斥分配，文字雲也不是民意比例。既有結構須補此角色，可與 frames 或 group_differences 合併。

claim_verification 新增 event_background（事件緣由與查證背景）核心角色，在摘要與正文開頭先交代必要前情、說法出現的情境與需要釐清的原因，再以 claim 界定待查命題。短文可合併同一節，但仍先背景後說法，避免重複；作為次類型時可共用已有背景。缺背景時標 partial/missing，不編造最初傳播者、擴散程度、動機或查核過程。若事件是否發生正是待查內容，背景須維持說法歸屬，不能先當成已確認事實。文字為主，有可靠 event 時可輔以時間軸；既有 claim_verification 結構需補此角色。

## 實例欄位與狀態

article_structure 包含 structure_version（1.0.0）、templates（依序 primary、secondary）、composition_reason 與 nodes。

每個 node 包含 id、roles（type/slot）、reader_question、status、reason、section_ids、evidence_ids。reader_question 是本次具體問題，不只照抄通用模板。reason 用一句話交代該段角色、合併或缺漏原因。

- covered：角色已由成稿與證據處理，兩組 ID 都非空。
- partial：部分內容有支持，但仍有明確缺口；reason 說明缺什麼，兩組 ID 都非空。
- missing：角色需要回答但沒有可支持的證據；evidence_ids 為空，可連到說明缺口的 section。
- not_applicable：本次問題不需該角色，兩組 ID 都空；原因不能寫成缺資料，缺資料應用 missing。

節點證據必須存在於其映射段落的 evidence_ids 中。每個 section 至少被一個非 not_applicable 節點涵蓋。不要把全篇所有證據機械地貼到每個角色；每個角色只引用真正支持它的材料。自動驗證只核對結構與引用，角色是否被正文充分回答仍需語意檢核。

## 與呈現階段銜接

先形成角色規劃，再寫 sections，最後核對映射及完整性。news-presentation 依 reader_question、sections 與證據選元件，保留 article_structure 原樣。每個 slot 的 presentation_modules 以 module_id／use_when 列出可能的文字、圖表、表格、引文或照片形式，依 [共用模組目錄](../../../schemas/presentation-modules.json) 查證據需求與支援狀態；模板層級的 presentation_hints 則提供優先選型、最低張數與例外。候選可組合，不要求每個 slot 一張圖，實際選擇由呈現階段寫入 blocks。photo 目前僅 planning_only，不能輸出為 block；詳見 [Slot 呈現模組](../../news-presentation/references/presentation-modules.md)。

event_context 的 sequence（關鍵經過）與 turning_points（轉折與連結）優先對應 timeline。分析階段先整理逐筆 event 與來源，呈現階段在至少兩個相關事件有可靠日期時產出時間軸。current_state 與 open_questions 保留文字，亦可補充時間軸的上下文。日期不足或有爭議時保留說明，不補造節點；只問單一日期則可採 event_brief 的短答。

data_analysis 的 finding／patterns 依 presentation_hints 要求一至多張支持洞察的數量圖表，先文字洞察、後圖表證據。圖的數量依不同閱讀問題決定，不等於節點數；不新增獨立的「圖表段落」角色。至少一張的要求以資料符合元件門檻為前提；不符合時明示 insufficient_data，可用表格補充而不當成完成圖表要求。這是 Skill 的編輯要求，驗證器檢查既有結構與圖表資料契約，不會自動判斷洞察品質或是否已涵蓋所有值得繪圖的發現。

comparative_analysis 的 dimensions／differences 通常以 table 並列至少兩個對象與共同維度；比較範圍、差異解讀與適用條件仍以文字說明。表格可轉置或拆分，保留逐格來源，未知、不適用、不可比須分開。部分欄位缺漏可保留表格並註明，沒有可比較的對象或共同維度才降級並交代缺口；極短比較可說明文字已足夠。

為相容既有 0.2.0 資料，schema 將 article_structure 視為可選擴充；新版分析 Skill 每次都必須輸出。新版整合請執行 `python3 scripts/validate.py OUTPUT --require-structure`。這會拒絕只有分類而沒有結構的舊輸出。
