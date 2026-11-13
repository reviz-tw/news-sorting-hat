# 模型與執行介面

Python 執行入口為 `scripts.pipeline.run_workflow(rag_input, generate)`。程式讀取 schemas 下的分類、類別、slot 與元件，再由 `scripts.prompts` 填入文字模板，將完整 prompt 與 response_schema 交給 generate。

generate 是應用程式提供的同步函式，接受一個 request dict，回傳 JSON dict 或字串。可依 request.stage 選擇不同模型。命令列可透過 CommandModel 以 stdin/stdout JSON 協定接入外部程式，命令以 argv 執行。詳細欄位與可執行的回放範例見 [README](../README.md)。

skills/ 下的三份 SKILL.md 是目前執行使用的 prompt template，不需模型支援 Skill 或檔案讀取。所有必要規則內嵌，資料以 `{{...}}` 由 Python 插入；原有 references/ 與 agents/ metadata 保留供維護者參考，不由模型載入。部署須包含 scripts/、schemas/ 與模板檔。sglang adapter 可直接使用 `request["prompt"]`；詳細欄位與單一 slot 範例見 [模板文件](prompt-templates.md)。
