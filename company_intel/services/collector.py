from __future__ import annotations
from ..config import Settings
from ..db import connect, upsert_company, upsert_revenue, upsert_news
from ..crawlers.mops_monthly import fetch_monthly_revenue
from ..crawlers.google_news import fetch_news
from .company_service import resolve, make_news_keywords

def collect(
    company_input: str,
    year: int,
    month: int,
    db_path: str = "data/company.db",
    market: str = "auto",
    news_keywords: str = "",
    fetch_revenue: bool = True,
    fetch_google_news: bool = True,
    settings: Settings | None = None,
) -> dict:
    settings = settings or Settings()
    company = resolve(company_input, settings)
    keywords = make_news_keywords(company, news_keywords)

    company_row = {
        **company,
        "news_keywords": "|".join(keywords),
    }

    result = {
        "company": company,
        "revenue": None,
        "news": [],
        "errors": [],
    }

    conn = connect(db_path)
    try:
        upsert_company(conn, company_row)

        if fetch_revenue:
            candidates = []
            if market == "auto":
                candidates = ["sii", "otc"]
            else:
                candidates = [market]
            last_error = None
            for m in candidates:
                try:
                    rev = fetch_monthly_revenue(
                        company["stock_id"], year, month, settings, market=m
                    )
                    result["revenue"] = rev
                    upsert_revenue(conn, rev)
                    break
                except Exception as e:
                    last_error = e
            if result["revenue"] is None and last_error:
                result["errors"].append(f"月營收：{last_error}")

        if fetch_google_news:
            try:
                rows = fetch_news(
                    company["stock_id"], keywords, year, month, settings
                )
                result["news"] = rows
                upsert_news(conn, rows)
            except Exception as e:
                result["errors"].append(f"Google News：{e}")
    finally:
        conn.close()

    return result
