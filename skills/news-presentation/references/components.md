# 元件選型 v0.2

參考《資料視覺化選型指引_圖解版.html》（文件標示 2026-09-24）：**13 種視覺化 + text、quote 兩種基本區塊，共 15 種 block type**。新聞回答的 13 類是另一個分類軸。

[原文件](https://chatgpt.com/library?file_id=libfile_b6e37c57c6c48191b6bd95b87a57023c&account_id=personal)。forms/ 保留逐類選型條件、65 個情境、替代呈現、缺漏處理與繪圖規格的文字擷取；移除圖像及互動。未重新查證 READr 原文，指引的虛構示例不能作為新聞證據。

先辨認閱讀任務 → 確認圖比文字多提供什麼 → 盤點證據與資料門檻 → 選元件。文字足夠就不製圖；值得畫但資料不足時，交付可支持的文字並列缺口。

| 原指引 | type | 資料門檻 | 逐類指引 |
| --- | --- | --- | --- |
| 01 折線圖 | `line_chart` | 同指標、同口徑的時間序列 | [折線圖](forms/01-line-chart.md) |
| 02 長條圖 | `bar_chart` | 同基準類別數值；從零開始 | [長條圖](forms/02-bar-chart.md) |
| 03 堆疊圖 | `stacked_chart` | 互斥、完整、可加總的分項與總量 | [堆疊圖](forms/03-stacked-chart.md) |
| 04 散佈圖 | `scatter_plot` | 同對象成對的兩項數值 | [散佈圖](forms/04-scatter-plot.md) |
| 05 比例氣泡圖 | `bubble_chart` | 非負數值；以面積同比縮放 | [比例氣泡圖](forms/05-bubble-chart.md) |
| 06 單位圖示／點陣圖 | `unit_chart` | 完整分母、固定單位與餘數 | [單位圖示／點陣圖](forms/06-unit-chart.md) |
| 07 地圖 | `map` | 座標或行政區 ID／邊界版本 | [地圖](forms/07-map.md) |
| 08 比較表／矩陣 | `table` | 共同維度；各格保留條件與未知 | [比較表／矩陣](forms/08-table.md) |
| 09 事件時間軸 | `timeline` | 可靠事件時間；不混淆刊出日 | [事件時間軸](forms/09-timeline.md) |
| 10 流程圖 | `flowchart` | 步驟、限定對象的入口、條件、出口與例外 | [流程圖](forms/10-flowchart.md) |
| 11 關係網絡圖 | `network_graph` | 去重對象與逐筆連結證據 | [關係網絡圖](forms/11-network-graph.md) |
| 12 文字雲 | `word_cloud` | 語料範圍與方法；無計數時用等大字 | [文字雲](forms/12-word-cloud.md) |
| 13 矩形樹圖 | `treemap` | 單一整體與互斥分項；父子逐層加總 | [矩形樹圖](forms/13-treemap.md) |

## 本專案的基礎形式

line_chart 至少三個可比較的非缺值，期間須連續且同精度；未取得的中間年份改表格或文字，不補造 null evidence。bar_chart 維持共同母體與期間，跨地區可用表格或地圖。兩者數值精確複製 measurement。

stacked_chart 與 unit_chart 引用第一階段已核對的 partition；treemap 每一層父子引用 partition，總數與分項 measurement 必須可加總。總量與分項在資料中都保留，但 renderer 不把父類小計重複畫成額外葉節點。stacked_chart 的 percentage 由已有分項與總量換算，不推算未知總量。unit_chart 支援整數單位與明示餘數；比例模式須有來源支持的 100% 完整分項，附換算註記。

scatter_plot 的 x/y measurement.category 必須配成同對象、同期間、同母體。bubble_chart 基礎版是自由排版比例圓，固定 scale=area；半徑由 renderer 依面積計算，位置無數值意義。

map 基礎版支援 points／choropleth，features 配對 location 與 measurement，地區必須相同。經緯度或 region_code/boundary_id 來自證據。renderer 必須使用已登錄且有版本的邊界資產，不讓模型生成行政區多邊形；缺值與零用不同樣式。

flowchart 引用 process_step/process_link，基礎版一個限定對象的入口，至少一個出口。每個節點由入口可達且能到出口；補件可返回中間步驟，不回到範圍入口。分支須有條件，保留例外；regulation/practice/case 與適用版本不能混為一套制度。

network_graph 引用 entity/relationship，期間一致。每條線的方向與類型有證據；線寬另有專屬 measurement，不能將共同合計複製成每條線的金額。排版距離不表示強弱或因果。

word_cloud 引用 text_term，mode=frequency/topic/presence。前兩者須有樣本數與正數權重；presence 的 value/unit 必須 null，使用等大字。基礎版每區塊一組同口徑語料；不同群體先分開呈現。

原指引的其他應用保留於 forms/；schema 支援上述基礎形式，尚未涵蓋小多圖、三指標氣泡與互動篩選等所有變體。不要輸出未定義欄位。完整欄位見共用契約與 schema。

## 基本區塊與交付

text 原樣保留 section 的 body 與 evidence_ids；quote 只引用來源可找到原文的 verbatim claim。它們不是原指引的 13 種圖表。每一節仍有完整文字回答，圖表附來源與限制。

會改變結論的條件跟著數值、日期或出口顯示，不只藏進 tooltip。保留單位與圖例；不可挪動數值位置來避開重疊。文字雲不代表民意比例，網絡不代表違法，前後差異不等於政策因果。

資料核對與畫面驗收分開；本 repo 尚無 renderer，不宣稱已通過窄螢幕、遮擋、鍵盤與互動驗收。
