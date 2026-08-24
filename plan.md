# Company Intelligence 開發與執行計畫 (plan.md)

> **版本**：1.0.0  
> **開發模式**：Spec-Driven Development (SDD)  
> **狀態**：In Progress  

---

## 1. 開發策略與 SDD 工作流程 (Strategy & SDD Workflow)

本專案採用 **規範驅動開發 (Spec-Driven Development, SDD)** 模式：

```mermaid
flowchart LR
    A[1. 撰寫/更新 spec.md] --> B[2. 拆解任務 plan.md]
    B --> C[3. 撰寫單元與整合測試]
    C --> D[4. 實作功能程式碼]
    D --> E[5. 自動化測試與驗證]
    E --> F[6. 更新版本與文件]
```

1. **規格先行 (Spec First)**：任何新功能必須先更新 `spec.md` 確定資料模型與 API 介面。
2. **計畫拆解 (Plan & Breakdown)**：在 `plan.md` 建立具體步驟與 Checkbox。
3. **測試與實作 (TDD / Verify)**：補齊單元測試（使用 mock 隔離外部 HTTP 請求），確認功能綠燈後發布。

---

## 2. 里程碑與階段規劃 (Milestones & Roadmap)

| 階段 | 里程碑名稱 | 主要交付物 | 狀態 |
| :--- | :--- | :--- | :---: |
| **Phase 1** | MVP 基礎建設與月營收 + 新聞 | CLI 工具、SQLite WAL DB、MOPS 爬蟲、Google News RSS、Streamlit 儀表板 | `[x]` 已完成 (驗證中) |
| **Phase 2** | MOPS 季財報與重大訊息 | 綜合損益表 / 資產負債表爬蟲、重大訊息即時爬取與儲存 | `[ ]` 規劃中 |
| **Phase 3** | AI 新聞去重與情緒摘要 | Gemini LLM 整合、新聞摘要、利多利空分數標記 | `[ ]` 規劃中 |
| **Phase 4** | Streamlit 高級儀表板 | 多公司同期 YoY 對比圖表、營收歷史走勢分析圖 | `[ ]` 規劃中 |
| **Phase 5** | FastAPI 與 MCP Server 介面 | RESTful API 服務、Model Context Protocol (MCP) Server 供 AI Agent 呼叫 | `[ ]` 規劃中 |
| **Phase 6** | Hermes Agent 自動監控 | 建立定時任務、自動觸發月營收抓取與主動通知機制 | `[ ]` 規劃中 |

---

## 3. 詳細任務拆解清單 (Detailed Task Breakdown)

### Phase 1: MVP 基礎設施與單元測試完善 (現階段)
- [x] **系統基礎架構建置**
  - [x] 建立 `company_intel/config.py` 設定模組
  - [x] 建立 `company_intel/db.py` 初始化 SQLite (companies, monthly_revenue, news)
  - [x] 實作 `crawlers/twse.py` 整合 TWSE OpenAPI 解析公司名稱
  - [x] 實作 `crawlers/mops_monthly.py` 解析 MOPS 歷史月營收 HTML
  - [x] 實作 `crawlers/google_news.py` 解析 Google News RSS XML
  - [x] 實作 `services/collector.py` 整合調用與錯誤處置
  - [x] 實作 `main.py` CLI 與 `app.py` Streamlit UI
- [ ] **測試與驗證覆蓋率提升**
  - [ ] 補全 `tests/test_crawlers.py` (針對 MOPS HTML 解析使用 mock html 測試)
  - [ ] 補全 `tests/test_db.py` (測試 SQLite upsert 冪等性)
  - [ ] 補全 `tests/test_collector.py` (測試部分失敗容錯與錯誤傳遞)

---

### Phase 2: MOPS 季財報與重大訊息 (Quarterly Financials & Material Info)
- [ ] **規格制定 (`spec.md`)**
  - [ ] 定義 `quarterly_financials` (綜合損益表、資產負債表) 資料表 Schema
  - [ ] 定義 `material_news` (重大訊息) 資料表 Schema
- [ ] **爬蟲模組擴充**
  - [ ] 新增 `company_intel/crawlers/mops_financials.py` (季報爬蟲)
  - [ ] 新增 `company_intel/crawlers/mops_announcements.py` (重大訊息爬蟲)
- [ ] **資料庫與服務整合**
  - [ ] 在 `db.py` 新增對應 upsert 邏輯
  - [ ] 擴充 `collector.py` 支援 `--fetch-financials` 與 `--fetch-announcements`
- [ ] **Streamlit UI 呈現**
  - [ ] 新增「季財報 (EPS, 淨利率, 毛利率)」分頁與「重大訊息」列表

---

### Phase 3: AI 新聞去重與情緒摘要 (LLM Integration)
- [ ] **規格制定 (`spec.md`)**
  - [ ] 定義 Gemini API Prompt 規格與 Structured Output Schema (JSON)
- [ ] **AI 服務模組**
  - [ ] 新增 `company_intel/services/ai_summary.py`
  - [ ] 實作新聞去重與聚合演算法 (Similarity Clustering)
  - [ ] 實作新聞總結與情緒評分 (-1.0 至 +1.0)
- [ ] **UI 擴充**
  - [ ] Streamlit 新增 AI Summary 卡片與重點新聞摘要列

---

### Phase 4: 多公司對比與高級圖表 (Multi-Company Comparison)
- [ ] **圖表模組建置**
  - [ ] 導入 Plotly / Altair 進行營收與 YoY 雙軸圖表繪製
  - [ ] 提供同產業多公司 (例如 寶成 vs 豐泰) 營收成長率對比分頁

---

### Phase 5: FastAPI REST API & MCP Server 介面
- [ ] **FastAPI 封裝**
  - [ ] 新增 `server.py` 提供 `/api/v1/company/{id}/revenue` 與 `/api/v1/company/{id}/news`
- [ ] **MCP Server 支援**
  - [ ] 新增 `mcp_server.py` 實作 Context Protocol，讓 AI 代理（如 Antigravity / Claude）直接調用抓取工具

---

### Phase 6: Hermes Agent 自動監控與通知 (Automation & Supervision)
- [ ] **自動排程監控**
  - [ ] 建立每月中旬自動比對並發起全台關鍵上市櫃公司月營收抓取腳本
  - [ ] 整合 LINE Notification / Telegram Bot 推播營收創新高或異常警告

---

## 4. 測試與品質控制 (QA & Testing Strategy)

### 4.1 自動化測試執行
使用 `pytest` 執行所有單元測試與整合測試：

```powershell
pytest -v tests/
```

### 4.2 程式碼風格與 Static Analysis
使用 `ruff` 或 `flake8` 確保程式碼規範：

```powershell
ruff check company_intel/
```

---

## 5. 風控與反爬蟲應對策略 (Risk & Anti-Blocking Strategy)

1. **User-Agent 隨機化 / 擬真**：在 `Settings` 中配置常見瀏覽器 User-Agent 標頭。
2. **自動 Delay**：大量連線 MOPS 時自動加上 `time.sleep(1.0 + random.random())`。
3. **離線與 快取機制 (Caching)**：對於已抓取過的月營收數據（歷史營收不會異動），直接讀取本地 SQLite 避免重複對外請求。
