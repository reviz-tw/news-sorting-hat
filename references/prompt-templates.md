# 模型 prompt template

`skills/` 下的 SKILL.md 現在是由 Python 載入的純文字模板，不使用 Skill 的自動觸發或檔案跳轉機制。模型只接收填好欄位的完整 prompt，不需要 repo 或外部檔案存取能力。原本 Markdown 參考文件中的必要分類、寫作、證據與選型規則已整理到模板內；類別、slot 與元件的具體內容仍以 JSON 定義為準，由程式插入。

## 模板與資料

| 用途 | 模板檔案 | 程式插入的主要資料 |
| --- | --- | --- |
| 分類 | skills/news-classification/SKILL.md | rewritten_question、categories、rag_input、response_schema |
| 全篇整理與撰寫 | skills/news-analysis/SKILL.md | rewritten_question、classification、profiles、modules、rag_input、response_schema |
| 單一 slot 撰寫 | skills/news-analysis/slot.md | rewritten_question、article_type、slot、is_primary、modules、rag_input、response_schema |
| 呈現模組 | skills/news-presentation/SKILL.md | rewritten_question、analysis、profiles、section_modules、components、response_schema |

每份模板也有 attempt 與 repair。`<!-- INPUT -->` 之前是固定指示，之後是需要填值的內容。這個分隔符只供 Python 使用，不送到模型。

`categories` 會插入 12 類的閱讀任務、涵蓋內容及分類界線；`profiles` 會展開選中類別的全部 slot。`components` 包含選中元件的輸入與前端 schema、選型規則、驗證及範例。程式移除只供本地導航的 file/reference 欄位，保留 RAG 原始網址供來源辨識，並展開 schema 的 `$ref`。不要求模型循網址或路徑取得資料。

## 單一 slot 的文字模板

```text
這是一份回答「{{rewritten_question}}」的{{article_type.name}}專題報導。文章依以下順序撰寫：{{article_type.narrative_logic}}
我們現在要撰寫「{{slot.role}}」。請依問題與檢索到的新聞片段，回答：{{slot.reader_question}}
```

模板後面另插入完整 article_type、slot、候選模組需求、RAG 及 response_schema。`slot.writing_guidance` 的寫法、必要元素與檢查清單會完整帶入。

`slot` 是段落定義，`response_schema` 才是模型輸出的 JSON Schema。兩者分開，避免模型把段落設定當成要回傳的成稿格式。

## 在目前 workflow 使用

```python
from scripts.pipeline import run_workflow
from scripts.validate import load_json

rag = load_json("examples/mixed-policy.input.json")

# generate(request) 由應用程式提供。
# adapter 把 request["prompt"] 送給模型，取得 JSON 字串或 dict 後回傳。
result = run_workflow(
    rag,
    generate,
    rewritten_question="政策的實際成果距離原定目標還有多少？",
)
```

正常流程仍為 classification → analysis → presentation 三次呼叫，每次都先從對應模板產生完整 `request.prompt`。sglang adapter 可直接使用此文字，不需另外拼接 data 或 schema，避免重複放入同一份資料。若部署端支援結構化輸出，可另外使用 request.response_schema 配置其輸出約束。

`rewritten_question` 由呼叫端提供，未指定時沿用 RAG 的 question。它只用來表達本次提問，不是新聞證據；workflow 不會自行呼叫模型改寫問題，也不會改動原始 RAG 或 analysis.question。

保留 instruction、data、response_schema、attempt、repair 欄位供既有 adapter 使用；新接入端優先使用 prompt。驗證失敗時，下一次 prompt 會填入更新的 attempt、validation_error 與 previous_response。模型呼叫異常仍直接停止。

## 準備一個 slot 的請求

```python
from scripts.prompts import build_slot_request
from scripts.validate import load_json

request = build_slot_request(
    rag_input=load_json("examples/mixed-policy.input.json"),
    selection=load_json("examples/mixed-policy.classification.json"),
    slot_type="policy_evaluation.outcomes",
    rewritten_question="政策的實際成果距離原定目標還有多少？",
)
print(request["prompt"])
```

`build_slot_request()` 只允許選中類別內的 slot；可傳入該段專用的 RAG 結果，但須符合原有 RAG 格式。函式會完成本地資料載入、模板填值與 schema 展開，不會呼叫 RAG 或模型。

輸出契約為 [slot-draft.schema.json](../schemas/slot-draft.schema.json)：

| 欄位 | 意義 |
| --- | --- |
| kind | 固定 slot_draft |
| slot_type | 固定為本次請求的 slot 類型 |
| status、reason | covered、partial、missing 或 not_applicable，以及原因 |
| section | 使用既有 analysis section 格式；不適用時為 null |
| evidence | 依既有證據契約抽取的證據，保留來源引用 |
| limitations | 依既有格式列出缺漏、衝突或比較限制 |

這是單段草稿，不能直接交給前端。逐 slot 模型呼叫、草稿的語意驗證、合併共用證據、建立 article_structure 及再次驗證完整 analysis，仍是 slot-writing TODO。現有三階段 workflow 的第二階段仍一次產生完整 analysis。

## 填值規則與驗證範圍

`render_template()` 只接受 `{{name}}` 或 `{{object.field}}`，不支援函式、運算式或讀檔指令。物件與陣列以不含縮排空白的 JSON 插入，減少 prompt 長度；字串直接插入。缺欄位或模板語法錯誤會在呼叫模型前報錯。欄位值只插入一次，新聞原文中的 `{{...}}` 會當作原文保留，不會再執行填值。

測試使用合成資料與回放模型，確認模板、資料交接、重試及既有輸出契約。尚未對實際 sglang 服務測試；模型的分類與寫作品質仍需用真實新聞評估。
