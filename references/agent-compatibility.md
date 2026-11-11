# 模型與執行介面

Python 執行入口為 `scripts.pipeline.run_workflow(rag_input, generate)`。程式直接讀取 schemas 下的分類、類別、slot 與元件，將各階段的指令、輸入資料及完整 response_schema 交給 generate。

generate 是應用程式提供的同步函式，接受一個 request dict，回傳 JSON dict 或字串。可依 request.stage 選擇不同模型。命令列可透過 CommandModel 以 stdin/stdout JSON 協定接入外部程式，命令以 argv 執行。詳細欄位與可執行的回放範例見 [README](../README.md)。

skills/ 與既有 agent metadata 保留早期使用方式的參考文件；Python workflow 的執行依賴為 scripts/ 與 schemas/。模型 prompt 與資料契約的程式入口以 pipeline.py 為準。
