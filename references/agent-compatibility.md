# Agent 載入與模型相容性

核心規則是兩份標準 `SKILL.md` 與共用 schema，沒有指定模型供應商，也不依賴 OpenAI 工具呼叫。`agents/openai.yaml` 只是 OpenAI 的顯示名稱、介紹與預設提示，不是可執行的 agent 定義，更不是 LLM provider 設定。

| 執行環境 | 本專案入口 | 使用方式 | 驗證範圍 |
| --- | --- | --- | --- |
| OpenAI / Codex | `skills/*/SKILL.md`、各自的 `agents/openai.yaml` | 在目前專案明確載入兩份 Skill，或由支援的 Skill loader 掛入整個 repo | 檔案、引用與合成契約測試 |
| Claude Code | `.claude/skills -> ../skills` | 在此 repo 開啟 Claude Code，使用 `/news-analysis` 與 `/news-presentation` | 已驗證入口連結與參考檔可讀；未執行 Claude CLI |
| Gemini CLI | `.gemini/skills -> ../skills` | 在此 repo 開啟 Gemini CLI，以 `/skills list` 確認探索結果 | 已驗證入口連結與參考檔可讀；未執行 Gemini CLI |
| 其他模型 API／自建 agent | `skills/*/SKILL.md` 與其參考資料 | 應用程式載入共用規則，使用相同輸入／輸出 schema 與驗證器 | 資料契約相同；模型遵循度需個別評測 |

本專案保留單一份內容，用相對 symlink 提供 Claude/Gemini 的原生探索入口；不建立它們沒有規格的 `agents/claude.yaml` 或 `agents/gemini.yaml`。symlink 不會複製一份可能漂移的規則。

Skill 中的參考路徑以實際的 `skills/<name>/` 目錄為基準。程式載入時先 resolve symlink，再解析相對路徑；不要只複製 SKILL.md，否則共用 schema 與 references 會遺失。其他專案若要使用，掛入整個 repo 或自行打包依賴並重寫參考路徑。

部分工具也支援 `.agents/skills/` 作為共用探索位置；目前環境禁止寫入這個目錄，所以本版採 `.claude/skills/`、`.gemini/skills/` 入口。此限制不影響 Skill 的供應商中立性。

模型 API 整合時，由各供應商的訊息介面載入兩份規則；不要把 OpenAI 專屬 role 名稱直接假設為所有供應商的 API 欄位。應用程式負責 adapter、token 預算、有限重試與延遲評測。

參考規格（查閱日期 2026-10-28）：[Agent Skills](https://agentskills.io/specification)、[Claude Code Skills](https://code.claude.com/docs/en/skills)、[Gemini CLI Skills](https://geminicli.com/docs/cli/skills/)。
