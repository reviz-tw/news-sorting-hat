---
name: news-analysis
description: 依已確定的文章分類與本地描述檔整理新聞 RAG，產出逐 slot 的文章角色、完整回答與可追溯證據，交給呈現規劃。
---

# 依分類整理新聞

取得第一關的[分類結果](../../schemas/classification.schema.json)、原始 [RAG](../../schemas/rag-input.schema.json) 與本地程式 `workflow.py resolve` 輸出的 profiles 和候選 modules。輸出依 [analysis schema](../../schemas/analysis.schema.json) 與[角色映射格式](../../schemas/article-structure.schema.json)。

1. 直接讀檔時，先由類別的 slots ID 陣列載入 schemas/slots/<slot_type>.json；resolve 已完成此展開。按 profiles 順序讀 narrative_logic、composition_guidance、presentation_hints 與 slots。第一份提供文章順序，後面的類型可補入角色或與前者合併。無法判定分類時用 unclassified。將 status、primary、secondary 原樣帶入 classification；另補 reason、evidence_ids 及 topic、method、angle、temporal 標籤。
2. 依每個 slot 的 reader_question、writing_guidance 與 evidence_requirements 取材。參考該 slot 列出的模組候選及資料需求，整理實際存在的證據。將 RAG 段落當作引用材料。question、as_of、sources 原樣帶入，所有證據保留 source_id/chunk_id；日期區分事件、發言、刊出與統計期間。
3. 區分 fact、具歸屬的 claim、附 based_on 的 inference。保留可核對的 event、measurement，以及材料支持的分項、關係、程序、地點和文本證據，欄位見[共用契約](../../references/contract.md)。數值保留單位、口徑、母體、地區、期間及缺值。材料衝突時保留歸屬及限制。涉及 positions_debate 時讀[立場時間與比較規則](references/positions-over-time.md)。
4. 編寫可獨立閱讀的 title、summary 與 sections。依[角色映射規則](references/article-structure.md)將每個所選 slot 對應到 node，附 section_ids 與 evidence_ids。證據充足用 covered，部分支持用 partial，必要材料缺漏用 missing，條件不適用用 not_applicable，逐項寫明原因。短答可在同一節完成多個角色。
5. 交代缺值、比較邊界、衝突與歷史適用時間。材料不足仍可回傳 status 為 insufficient 的 analysis 和具體 limitations。若證據改變分類判斷，交回分類步驟重新產生選擇及描述檔。
6. 輸出含 article_structure 的 0.2.0 analysis，送交 `validate.py ANALYSIS --input RAG --classification CLASSIFICATION` 核對原始材料和第一關結果。
