# 文章抽象結構

分類後讀取 [article-templates.json](../../../schemas/article-templates.json) 中 primary 與 secondary 的 file 所指向的描述檔。JSON 是唯一的角色定義；其中的 narrative_logic 說明敘事順序，slots 依序列出 slot 類型 ID，按 ID 讀取 schemas/slots/<slot_type>.json；獨立 slot 檔定義閱讀問題、核心程度、寫作指引、證據需求及候選模組 ID。這是本專案的編輯骨架，不是 READr 官方文章格式。

## 結構的兩個層次

模板描述「這種類型通常如何回答問題」；analysis.article_structure 描述「這次實際如何組織回答」。後者不重複寫整篇正文，透過 section_ids 連接成稿，透過 evidence_ids 連接支持材料。結構是一份可公開檢查的編輯規劃，不要求模型輸出內部推理過程。

## 組合與縮放

1. 以 primary 的 narrative_logic 作骨架；只插入有助於回答問題的 secondary 角色。例如 issue_explainer 的機制解釋之後，加入 positions_debate 的各方主張與分歧。
2. 模板順序是預設，不是死板的寫作限制。依問題調整順序並在 composition_reason 說明；nodes 陣列順序就是本次閱讀順序，sections 依此組織成稿。
3. 內容重疊可合併角色：一個 node 的 roles 可同時列出主類型與次類型的多個 slot。每個 slot 只分配一次；同一節可以承接多個角色，一個角色也可對應多節。
4. 所選模板的每個 slot 都需有交代。主類型 core 角色必須處理，無證據時標 missing；conditional 角色與次類型不適用的角色可標 not_applicable 並寫明原因。若一個次類型沒有任何有用角色，交回第一關調整分類，再重新載入描述檔。
5. 短答可以只生成一節。例如只問何時重新開館，事件核心一節即可；其他不必要背景標 not_applicable，不為了模板新增長文。
6. 無法分類時 templates 使用 ["unclassified"]，套用 fallback 的 answer、limits 兩角色。完全沒有證據時可以用 missing 節點連到說明無法回答的段落。

## 實例欄位與狀態

article_structure 包含 structure_version（1.0.0）、templates（依序 primary、secondary）、composition_reason 與 nodes。

每個 node 包含 id、roles（type/slot）、reader_question、status、reason、section_ids、evidence_ids。reader_question 是本次具體問題，不只照抄通用模板。reason 用一句話交代該段角色、合併或缺漏原因。

- covered：角色已由成稿與證據處理，兩組 ID 都非空。
- partial：部分內容有支持，但仍有明確缺口；reason 說明缺什麼，兩組 ID 都非空。
- missing：角色需要回答但沒有可支持的證據；evidence_ids 為空，可連到說明缺口的 section。
- not_applicable：本次問題不需該角色，兩組 ID 都空；原因不能寫成缺資料，缺資料應用 missing。

節點證據必須存在於其映射段落的 evidence_ids 中。每個 section 至少被一個非 not_applicable 節點涵蓋。不要把全篇所有證據機械地貼到每個角色；每個角色只引用真正支持它的材料。自動驗證只核對結構與引用，角色是否被正文充分回答仍需語意檢核。

## 與呈現階段銜接

先形成角色規劃，再寫 sections，最後核對映射及完整性。news-presentation 依 reader_question、sections 與證據選元件，保留 article_structure 原樣。workflow.py resolve 合併模組目錄後，每個 slot 的 presentation_modules 以 module_id／use_when 列出可能的文字、圖表、表格、引文或照片形式，依 [元件索引](../../../schemas/components.json)所指的檔案 查證據需求與支援狀態；模板層級的 presentation_hints 則提供優先選型、最低張數與例外。候選可組合，不要求每個 slot 一張圖，實際選擇由呈現階段寫入 blocks。photo 目前僅 planning_only，不能輸出為 block；詳見 [Slot 呈現模組](../../news-presentation/references/presentation-modules.md)。

為相容既有 0.2.0 資料，schema 將 article_structure 視為可選擴充；新版分析 Skill 每次都必須輸出。新版整合請執行 `python3 scripts/validate.py OUTPUT --require-structure`。這會拒絕只有分類而沒有結構的舊輸出。
