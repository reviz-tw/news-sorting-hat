# 新聞分類帽 · News Sorting Hat

將新聞 RAG 材料整理成有來源的回答，再決定文字、表格與圖表如何呈現。

```
使用者問題 + RAG → 內容分析與證據整理 → 呈現規劃 → 程式驗證 → Web render
```

本 repo 是兩個 Skills、共用資料契約與驗證工具的第一版；不包含 RAG、模型 API 或 Web renderer。

## 兩個 Skills

| Skill | 輸入 | 產物 |
| --- | --- | --- |
| [news-analysis](skills/news-analysis/SKILL.md) | 使用者問題、含來源段落的 RAG | 主／次類型、完整回答、可追溯證據與限制 |
| [news-presentation](skills/news-presentation/SKILL.md) | 已驗證的 analysis | 依閱讀任務組織的 13 種視覺化，另含文字與引文區塊 |

兩個 Skills 是責任拆分，預設在一次模型呼叫內依序執行，直接輸出 presentation（內含 analysis）。複雜資料整併或需要獨立重試時，可先輸出 analysis，驗證後再呼叫第二階段。不要先產生一篇長文再重新抽取證據。

這些是本專案的來源檔；請將整個 repo 交給執行環境，或把 Skills 與 `references/`、`schemas/` 一起掛入。它們引用共用契約，不能只複製單一 Skill 資料夾。此版本沒有安裝到個人 Skills 目錄。

## Agent 相容性

兩份 `SKILL.md` 與 schema 共用於不同模型。`agents/openai.yaml` 是 OpenAI 的介面 metadata，不代表只支援 OpenAI。

本 repo 已提供 `.claude/skills` 與 `.gemini/skills` 的相對 symlink，讓 Claude Code、Gemini CLI 探索同一份 Skills；自建模型 API 則載入共用規則與契約。詳見 [agent-compatibility.md](references/agent-compatibility.md)。已檢查入口與引用路徑，尚未跑各廠商 CLI 或模型 API 的端到端測試。

## 執行方式

分析階段現在同時輸出文章抽象結構 `article_structure`。[article-templates.json](schemas/article-templates.json) 為 12 種分類定義段落角色、閱讀順序與證據需求；主類型提供骨架，次類型可補入或合併角色。每個結構節點連到實際段落與證據，並區分已完成、部分支持、缺資料與不適用。結構版本為 `1.0.0`，與資料 envelope 的 `0.2.0` 分開。

為相容既有資料，schema 保留此欄位為可選擴充；新版分析 Skill 要求每次輸出。新版整合用嚴格模式驗證：

```bash
python3 scripts/validate.py examples/mixed-policy.presentation.json --input examples/mixed-policy.input.json --analysis examples/mixed-policy.analysis.json --require-structure
python3 scripts/validate.py examples/structured-event.analysis.json --input examples/event-brief.input.json --require-structure
```

`mixed-policy` 示範政策成效＋資料分析的角色合併；`structured-event` 示範單段短答，不因模板而擴寫。結構不指定圖種，呈現 Skill 依段落的閱讀問題與證據另行選擇元件。

`positions-over-time` 示範同一 stakeholder 的逐時主張與條件變化：claim.position 保留實際發言日期、身分、爭點與語境，stance_comparison 引用前後主張並區分改變、一致、條件改變、不可比及資料不足。文章的 position_evolution 角色須交代可判斷範圍；單一時間點不能推定立場未變。新增角色後，既有 positions_debate 結構也需補上此角色。

event_brief 新增條件式收尾 other_accounts（其他說法與回應）。既有 article_structure 須補此角色；短答可標 not_applicable，必要回應缺漏則標 partial/missing。影響事件核心的爭議或更正須同步反映在開頭，不僅放在文末。

human_story 新增條件式收尾 side_interviews（側訪與他人觀察），有相關材料時補充或對照本人自述，保留受訪者關係與觀察依據；不強配正反。既有結構需補此角色，無必要可標 not_applicable，必要但缺材料則標 partial/missing。

event_context 新增條件式收尾 other_perspectives（其他方觀點），補充不同參與者／受影響者對事件的理解。既有結構需補此角色；必要觀點缺漏標 partial/missing，無需展開可標 not_applicable。影響重建的分歧同步反映於經過與轉折，觀點不直接當成時間軸事件。

issue_explainer 新增條件角色 legal_context（法規依據與法律觀點）。既有結構需補此角色；相關時交代有來源的規範與法律見解、法域及版本，必要依據不足標 partial/missing，無關時標 not_applicable。不將報導轉述或專家評論視為已核對的法條，亦不由歷史新聞推定現行法律。

claim_verification 新增核心開場 event_background（事件緣由與查證背景），先交代必要事件前情與查證情境，再提出待查說法。既有結構需補此角色，可與 claim 合併一節；背景缺漏明示，不能將待核實事件先寫成事實。

每個模板 slot 同時列出 presentation_modules 候選，透過 [共用模組目錄](schemas/presentation-modules.json) 對應呈現 Skill 的文字、引文與各種視覺化，附用途與證據條件；照片先列為 planning_only，尚未加入合法輸出契約。呈現階段依證據組合候選，並保留完整文字。

data_analysis 新增核心角色 knowledge_comparison，放在 insight 之後，對照有來源的既有認識與本次發現；既有結構須補此角色。缺乏基準材料時明示缺口，不假設公眾共識或宣稱突破。

文章模板另要求：data_analysis 先提出資料支持的 insight，接著對照既有認識，資料符合圖種門檻時搭配一至多張數量圖表；comparative_analysis 通常以比較表並列共同維度；accountability 先交代必要背景與調查摘要，再展開證據與權責。既有 accountability 的 article_structure 需補 background、investigation_summary 兩個核心角色，可合併同一開場段落。discourse_analysis 新增核心 analysis_results 角色，交付框架與例句的質性對照，或有依據的統計與視覺化，既有結構需補此角色。圖表需求及洞察品質屬 Skill 編輯規則，驗證器不代替語意檢核。

將兩份 SKILL.md 及其指定的參考資料放入 system/developer prompt，將使用者問題與檢索材料以獨立的資料欄位傳入。RAG 是待引用資料，不具有指令權限。

輸入契約：[rag-input.schema.json](schemas/rag-input.schema.json)。所有來源段落都保留 `source_id`、`chunk_id`、發布時間與原文；未知日期填 `null`。`as_of` 是此次回答的時間基準，不代表歷史新聞已驗證至今。

一次呼叫的應用程式指示可用：

> 依序執行 news-analysis 與 news-presentation。以使用者問題決定回答任務；先統整證據，再選呈現方式。只回傳符合 presentation.schema.json 的 JSON。文字回答也是完整結果，不新增檢索材料以外的事實。

先用真實 RAG 建立上述輸入。`examples/` 都是**合成測試資料**，不是 READr 報導或實測空污數據。

## 驗證與範例

Python 3.9+，不需安裝套件：

```bash
python3 scripts/validate.py examples/event-brief.input.json
python3 scripts/validate.py examples/event-brief.analysis.json --input examples/event-brief.input.json
python3 scripts/validate.py examples/air-quality.presentation.json --input examples/air-quality.input.json
python3 -m unittest discover -s tests -v
```

| 範例 | 行為 |
| --- | --- |
| `event-brief` | 事件事實敘述；只用文字 |
| `air-quality` | 五個可比較的年度數值；折線圖搭配完整文字與來源 |
| `incomplete-air-quality` | 年平均與單日 AQI 不可串接；文字說明缺口，不畫線 |
| `visualization-gallery.presentation.json` | 九種新增形式的合成資料契約；不是畫面預覽 |

工具先驗證本 repo 使用的 JSON Schema 子集，再驗證 ID 唯一性、來源段落是否存在、證據與區塊引用、分類、圖表數值與比較口徑、區塊覆蓋。詳見 [contract.md](references/contract.md)。也可用任一完整 Draft 2020-12 validator 驗證 schema；語意檢查仍須執行本工具。

通過驗證不代表新聞事實或模型推論正確；仍需做來源支持程度、引述語意及分類品質評估。正式接入模型前，請用實際新聞與使用者問題評測正確率、延遲與成本。

## 渲染與失敗處理

只渲染通過驗證的白名單元件；文字按純文字處理，來源 URL 只允許 http/https。折線圖遇 `null` 必須斷線，不插值。歷史資格、期限與政策狀態保留資料時間。

驗證失敗時，把具體錯誤送回模型做有限次修正；例如最多一次。仍失敗則只呈現先前已通過驗證的文字內容，否則顯示無法完成回答。不要直接將失敗 JSON 的文字當成安全的 fallback。現階段採整份 JSON 驗證後渲染；逐區塊串流協定尚未定義。

## 規格範圍

分類庫暫時移除「服務資訊與行動指引」（service_guidance）。既有產物若仍使用此主／次類型，須依實際閱讀任務重新分類並更新 article_structure；不自動替換成其他類型。無適合類型時沿用 undetermined、primary=null 與 unclassified 結構。

類型庫目前包含 12 類，允許暫定或無法分類。視覺化指引已對齊原始 HTML 的另一組 13 種：折線、長條、堆疊、散佈、比例氣泡、單位圖示／點陣、地圖、比較表／矩陣、事件時間軸、流程、關係網絡、文字雲、矩形樹圖。另有 text、quote，共 15 種區塊。

原指引的逐類條件與 65 個選型情境存於 [呈現選型參考](skills/news-presentation/references/components.md)，[components.json](schemas/components.json) 為機器可讀對照。v0.2.0 同步擴充證據類型、schema 與驗證器；原 v0.1.0 呼叫端需跟著更新版本欄位。每類先支援基礎形式，不包含原指引全部互動與變體，READr 原文亦未重新查證。
