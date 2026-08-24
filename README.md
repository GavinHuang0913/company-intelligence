# Company Intelligence

輸入台灣公司名稱/股票代號與年月，自動抓取：

1. 公開資訊觀測站（MOPS）歷史月營收
2. Google News RSS 當月份公司新聞
3. 將結果寫入 SQLite
4. 以 Streamlit Dashboard 顯示

> MVP 先專注「月營收 + 新聞」。正式季財報、重大訊息、AI Summary 可作為 Phase 2。

## 1. 環境

建議 Python 3.11 / 3.12。

### Windows PowerShell

```powershell
cd company-intelligence
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy config.example.json config.json
```

若使用 uv：

```powershell
uv venv
.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
copy config.example.json config.json
```

## 2. CLI 試跑

寶成 2026/07：

```powershell
python main.py --company "9904 寶成" --year 2026 --month 7
```

只抓 Google News：

```powershell
python main.py --company "9904 寶成" --year 2026 --month 7 --no-revenue
```

加入新聞關鍵字：

```powershell
python main.py --company "9904 寶成" --year 2026 --month 7 --keywords "Nike|adidas|越南|印尼"
```

如果知道是上櫃：

```powershell
python main.py --company "XXXX 公司名" --year 2026 --month 7 --market otc
```

## 3. Streamlit

```powershell
streamlit run app.py
```

瀏覽器通常會開：

```text
http://localhost:8501
```

## 4. 資料庫

SQLite：

```text
data/company.db
```

主要 tables：

- `companies`
- `monthly_revenue`
- `news`

可用 SQLite CLI：

```sql
SELECT *
FROM monthly_revenue
WHERE stock_id='9904'
ORDER BY year DESC, month DESC;
```

```sql
SELECT publish_date, source, title, url
FROM news
WHERE stock_id='9904'
ORDER BY publish_date DESC;
```

## 5. 資料來源策略

### 公司基本資料

優先使用臺灣證券交易所 OpenAPI：

```text
https://openapi.twse.com.tw/v1/opendata/t187ap03_L
```

### 最新上市公司月營收 API

```text
https://openapi.twse.com.tw/v1/opendata/t187ap05_L
```

### 歷史月營收

MOPS 歷史靜態報表：

```text
https://mops.twse.com.tw/nas/t21/sii/t21sc03_{民國年}_{月}.html
https://mops.twse.com.tw/nas/t21/otc/t21sc03_{民國年}_{月}.html
```

例如 2024/01：

```text
https://mops.twse.com.tw/nas/t21/sii/t21sc03_113_1.html
```

MOPS 可能調整網站結構或限制自動存取，因此 crawler 已獨立封裝；若日後失效，只需要更換 `company_intel/crawlers/mops_monthly.py`。

### Google News RSS

使用 Google News RSS Search，Query 會自動加入：

```text
("寶成" OR "寶成工業股份有限公司")
after:2026-07-01
before:2026-08-01
```

## 6. 注意

- MOPS 月營收金額通常以「仟元」呈現，Dashboard 目前保存原始數值。
- 使用公開網站資料時請控制請求頻率，不要高頻爬取。
- Google News RSS 返回的是新聞索引連結與摘要資料，不代表能直接抓取每家新聞網站全文。
- 非上市公司若 TWSE 公司基本資料找不到，可直接輸入 `股票代號 公司名稱`。
- `market=auto` 會依序嘗試上市與上櫃歷史月營收頁。

## 7. 下一階段

建議依序增加：

1. MOPS 季財報（綜合損益表、資產負債表、現金流量表）
2. MOPS 重大訊息
3. Google News 去重與分類
4. AI Summary
5. Streamlit 多公司比較
6. FastAPI / MCP
7. Hermes Supervisor Agent


## v2 修正

- 修正輸入 `9904 寶成` 時，公司 resolver 會把整串文字拿去比對而失敗的問題。
- MOPS 月營收改為先查現行單一公司入口：
  `https://mops.twse.com.tw/mops/web/t05st10_ifrs`
- `/nas/t21/...` 僅保留為 fallback。
- `market=auto` 在公司已解析成上市時，不會再錯誤跑到 OTC。

建議測試：

```powershell
python main.py --company "9904 寶成" --year 2026 --month 7
```

再測 Streamlit：

```powershell
streamlit run app.py
```


## v3 修正

### 月營收

1. 上市公司查詢時，優先使用 TWSE 官方 OpenAPI `t187ap05_L`。
2. OpenAPI 只提供最新一期，因此會檢查 `資料年月` 必須與指定年月一致。
3. 指定歷史月份時，才 fallback 至 MOPS。
4. `requirements.txt` 已加入 `html5lib`，修正 `pandas.read_html()` parser 缺套件錯誤。

### Google News 日期卡控

預設以所選年月為截止月，保留最近 3 個完整月份。

例如：

```text
查詢年月：2026/07
新聞期間：3 個月
實際日期：2026/05/01 ~ 2026/07/31
```

RSS query 會加日期條件，抓回資料後 Python 還會再依 `publish_date` 過濾一次。

CLI：

```powershell
python main.py --company "9904 寶成" --year 2026 --month 7 --news-months 3
```


## v4 修正：歷史月份 / charset_normalizer

若 v3 出現：

```text
module 'charset_normalizer' has no attribute 'detect'
```

原因不是公司或月份資料，而是 `requests.apparent_encoding` 觸發本機
`charset_normalizer` 套件相依異常。

v4 已完全移除 MOPS crawler 對 `apparent_encoding` 的使用：

- 現行 MOPS 頁：UTF-8
- 舊 MOPS fallback：CP950
- requirements 釘住相容的 `requests` / `charset-normalizer`

建議先修復既有虛擬環境：

```powershell
python -m pip install --upgrade --force-reinstall "requests>=2.32,<3" "charset-normalizer>=3.3,<4" html5lib lxml
```

再測歷史月份：

```powershell
python main.py --company "豐泰" --year 2026 --month 6
python main.py --company "豐泰" --year 2026 --month 5
python main.py --company "9904 寶成" --year 2026 --month 6
```

注意：TWSE `t187ap05_L` 只處理官方最新一期；歷史指定月份仍由 MOPS 現行單一公司頁處理。


## v5 修正：MOPS 歷史月份改為 POST

v4 的歷史月份仍以 GET 方式開啟 `t05st10_ifrs`，因此取得的是查詢表單頁，
不是查詢結果頁，常見錯誤：

```text
No tables found
```

v5 改為：

1. GET `t05st10_ifrs` 建立 session/cookie
2. POST form data 至 `t05st10_ifrs`
3. 若失敗再 POST `ajax_t05st10_ifrs`
4. 最後才使用 legacy `/nas/t21/...`

POST payload 包含：

```text
step=1
firstin=1
off=1
queryName=co_id
TYPEK=all
isnew=false
co_id=9910
year=115
month=06
```

解析不再依賴固定 table index，而是依：

- 本月
- 去年同期
- 增減百分比
- 本年累計
- 去年累計
- 累計增減百分比

等欄位名稱抓取。

測試：

```powershell
python main.py --company "豐泰" --year 2026 --month 6
python main.py --company "豐泰" --year 2026 --month 5
python main.py --company "9904 寶成" --year 2026 --month 6
```


## v6：歷史月份容錯 + 新聞排序

### 月營收策略

- 指定月份 = TWSE OpenAPI 最新月份：完整欄位
- 指定月份 = 最新月份前一個月：
  - 使用最新快照中的 `營業收入-上月營收`
  - 僅回傳可確定的當月營收
  - YoY / 累計欄位保持空值，不做推估
- 更早月份：
  - 再嘗試 MOPS POST 歷史查詢
  - 若 MOPS 被安全機制阻擋，會明確回報來源限制

此設計避免「歷史月份抓不到就整筆 revenue=null」。

### 新聞排序

Google News 抓回後先依 `publish_date` 由新到舊排序。

Streamlit UI 可切換：

- 最新 → 最舊
- 最舊 → 最新


## v7：完整歷史月營收改用 FinMind

主來源改為 FinMind `TaiwanStockMonthRevenue`：

- 歷史範圍：2002-02 ~ now
- 上市 / 上櫃 / 興櫃
- 指定股票代號 + 起訖日期
- 可選 `FINMIND_TOKEN`

### 完整欄位計算

FinMind 提供每月 revenue，v7 會自行計算：

- 當月營收
- 上月營收
- 去年當月營收
- MoM
- YoY
- 當年累計營收
- 去年同期累計營收
- 累計 YoY

因此不再依賴 MOPS HTML 版型取得歷史月份。

### 資料來源優先順序

1. FinMind historical
2. TWSE OpenAPI latest snapshot
3. MOPS fallback

### 可選 Token

PowerShell：

```powershell
$env:FINMIND_TOKEN="你的 token"
python main.py --company "9904 寶成" --year 2026 --month 5
```

不設定 token 時也會先嘗試 Free API。

### 測試

```powershell
python main.py --company "9904 寶成" --year 2026 --month 5
python main.py --company "豐泰" --year 2026 --month 6
python main.py --company "9904 寶成" --year 2025 --month 12
```

## v8：統一幣別與金額單位

所有 `monthly_revenue` 金額欄位統一保存為：

- `currency = TWD`
- `amount_unit = TWD`
- 金額單位 = 新台幣「元」

### 為什麼舊資料看起來少 1000 倍？

FinMind `TaiwanStockMonthRevenue.revenue` 是新台幣元；TWSE OpenAPI / MOPS 月營收原始數字則是新台幣千元。
因此舊版直接混存時：

- TWSE：`19,563,446`（千元）
- FinMind：`21,701,839,000`（元）

兩者其實是同一量級，只是單位差 1000。

### 自動 migration

第一次使用 v8 開啟既有 `data/company.db` 時會執行一次：

1. 新增 `currency`, `amount_unit`, `source_type`, `previous_month_revenue`, `mom`
2. 舊 TWSE / MOPS 金額欄位乘 1000，統一轉成 TWD 元
3. FinMind 資料不乘 1000
4. migration 記錄在 `schema_migrations`，不會重複執行

不需要刪除既有 SQLite。


## v9：查詢結果 / 歷史資料分頁

Streamlit 畫面改成兩個 Tab：

### 📊 查詢結果

只顯示本次查詢：

- 月營收
- MoM / YoY
- 累計營收
- Google News

### 🗄️ 歷史資料庫

歷史資料獨立顯示，不再放在查詢結果頁最下方。

左側「歷史資料篩選」可選：

1. `同公司 + 同年月`
   - 完全套用目前公司 / 年 / 月查詢條件。
2. `同公司 + 同年度`
   - 顯示該公司指定年度 1~12 月資料。
3. `同公司全部`
   - 顯示該公司 DB 中全部歷史月份。
4. `全部資料`
   - 不限制公司與年月。

歷史資料表同樣使用：

- 千分位金額
- TWD 幣別
- MoM / YoY %
- 資料來源
- 更新時間

左側條件修改後，歷史 Tab 會同步重新篩選，不需要再次執行 crawler。


## v10：顯示單位切換

左側新增顯示單位：

- 元
- 千元（預設）
- 百萬元
- 億元

SQLite 仍統一保存 `TWD 元`，只在 Streamlit 畫面換算。

例如 DB 金額：

```text
6,720,476,000 TWD
```

顯示：

```text
元      → 6,720,476,000
千元    → 6,720,476
百萬元  → 6,720.48
億元    → 67.20
```

查詢結果與歷史資料庫會使用同一個顯示單位。


## v11：國際公司

新增公司：

### 華利集團
- 股票：300979.SZ
- 市場：中國深圳
- 幣別：CNY
- 財報來源：AKShare / Eastmoney
- 支援：
  - 損益表
  - 資產負債表
  - 現金流
  - 最新已公布 Q1 / H1 / Q3 / FY

### 寶勝國際
- 股票：03813.HK
- 市場：香港
- 幣別：CNY
- 月收益來源：Pou Sheng 官方 IR Monthly Revenue
- DB 統一存 CNY 元

測試：

```powershell
pip install -r requirements.txt

python main.py --company "寶勝" --year 2026 --month 6
python main.py --company "華利集團" --year 2026 --month 6

streamlit run app.py
```

資料路由：

```text
台灣公司 -> FinMind -> TWSE -> MOPS
寶勝國際 -> Pou Sheng IR Monthly Revenue
華利集團 -> AKShare / Eastmoney Financial Statements
所有公司 -> Google News RSS
```


## v12：Canonical Symbol + 四家國際公司

### Canonical Symbol

```text
寶成       9904.TW
九興       1836.HK
華利集團   300979.SZ
寶勝       3813.HK
裕元       0551.HK
```

UI、Company Resolver、歷史資料會優先顯示 `symbol`。

### 公司資料路由

| 公司 | Symbol | 月營收 | 財報 |
|---|---|---|---|
| 寶成 | 9904.TW | FinMind / TWSE | - |
| 九興 | 1836.HK | - | Yahoo Finance + Stella IR |
| 華利 | 300979.SZ | - | AKShare/Eastmoney，Yahoo fallback |
| 寶勝 | 3813.HK | Pou Sheng 官方 IR | Yahoo Finance |
| 裕元 | 0551.HK | HKEX Monthly Revenue Announcement | Yahoo Finance |

### 測試

```powershell
pip install -r requirements.txt

python main.py --company "1836.HK" --year 2026 --month 6
python main.py --company "300979.SZ" --year 2026 --month 6
python main.py --company "3813.HK" --year 2026 --month 5
python main.py --company "0551.HK" --year 2026 --month 5
python main.py --company "9904.TW" --year 2026 --month 5

streamlit run app.py
```

### 幣別

DB 保存公司原始報告幣別的「元」：

- TW：TWD
- 華利：CNY
- 寶勝：CNY
- 裕元：USD
- 九興：USD

Streamlit 的「元 / 千元 / 百萬元 / 億元」只做顯示換算，不做跨幣別換匯。


## v13：Official IR First + 公司下拉清單 + 同年月跨公司比較

### 公司 / 股票代號

改成下拉選單：

- 寶成 9904.TW
- 九興 1836.HK
- 華利集團 300979.SZ
- 寶勝 3813.HK
- 裕元 0551.HK

另提供「＋ 新增公司到選項清單」。

新增內容會保存到：

```text
data/company_options.json
```

因此重新啟動 Streamlit 後仍會保留。

### 歷史資料範圍

新增：

```text
所有公司 + 同年月
```

例如選 2026 / 05，會顯示所有公司在 2026/05 的月營收資料。

### 裕元資料來源優先順序

```text
Yue Yuen 官方 IR
    ↓
HKEX fallback
    ↓
Yahoo Finance 財報 fallback
```

官方來源：

```text
https://www.yueyuen.com/tc/reports_announcement.html#monthly_revenue
```

### 裕元新聞降噪

Google News 查詢自動排除：

- 酒店
- 花園酒店
- 餐廳
- 粽
- 下午茶
- 龍蝦
- 合唱

避免「裕元花園酒店」干擾裕元工業公司情報。


## v14：Yue Yuen 官方網站 Browser Fallback

裕元官方 Monthly Revenue 頁面可能使用 JavaScript / AJAX 動態載入，
一般 `requests` 可能得到 403 或不含表格的 HTML。

v14 流程：

```text
requests
   ↓ 找不到完整 table / 403
Playwright Chromium
   ↓
等待頁面 JS 載入
   ↓
選指定年度
   ↓
解析瀏覽器實際看到的 Monthly Revenue table
```

解析欄位：

- 綜合經營收益 / 單月營收
- 綜合經營收益 / 累計營收
- 綜合經營收益 / 單月同比
- 綜合經營收益 / 累計同比

原始金額按 USD'000 轉為 USD 元寫入 DB。

### 首次安裝

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

之後：

```powershell
python main.py --company "0551.HK" --year 2026 --month 7
streamlit run app.py
```

同時將 Streamlit metric 數值字體縮小至 1.85rem，
降低大型累計營收被截斷的情況。


## v15：Yue Yuen rendered DIV/grid parser

v14 已確認 Playwright 可以開啟裕元官網，但該頁月營收畫面不是標準
`<table>`，而是前端以 DIV/grid 方式呈現。

v15 不再依賴 `<table>`：
1. Playwright 開啟裕元官方 IR。
2. 選擇指定年份。
3. 找月份文字節點（例如 `7`）。
4. 沿 DOM ancestor 找「該月份的一整列 rendered row」。
5. 依官方欄位順序解析：
   - 單月營收
   - 累計營收
   - 單月同比
   - 累計同比
6. 金額從 USD'000 換算成 USD 元寫入 SQLite。

以 2026/07 官方畫面為例，應解析：
- 單月營收：602,614
- 累計營收：4,576,687
- 單月同比：-9.7%
- 累計同比：-3.2%

若 DOM 再次改版而解析失敗，會自動寫出：
- `data/debug/yueyuen_body.txt`
- `data/debug/yueyuen_page.html`

方便下一步直接依實際 DOM 修 selector。

另外，裕元 Google News 增加「query 排除 + Python title hard filter」雙層降噪，
排除裕元花園酒店、裕元獎、餐飲/合唱等非裕元工業公司情報。
