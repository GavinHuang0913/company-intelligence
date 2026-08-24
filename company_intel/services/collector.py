from __future__ import annotations
from ..config import Settings
from ..db import (
    connect, upsert_company, upsert_revenue, upsert_news, upsert_financial_report
)
from ..crawlers.finmind import fetch_month_revenue_history
from ..crawlers.mops_monthly import fetch_monthly_revenue
from ..crawlers.google_news import fetch_news
from ..crawlers.twse import fetch_revenue_from_latest_snapshot
from ..crawlers.pousheng import fetch_pousheng_monthly_revenue
from ..crawlers.huali import fetch_huali_financial
from ..crawlers.yueyuen import fetch_yueyuen_monthly_revenue
from ..crawlers.yueyuen_official import fetch_yueyuen_official_monthly_revenue
from ..crawlers.yfinance_financial import fetch_yfinance_financial
from .company_service import resolve, make_news_keywords

def _financial_fallback(company: dict, year: int, month: int):
    return fetch_yfinance_financial(
        symbol=company["symbol"],
        year=year,
        month=month,
        currency=company.get("currency", ""),
        company_name=company.get("company_name", ""),
        stock_id=company["stock_id"],
    )

def collect(
    company_input: str,
    year: int,
    month: int,
    db_path: str = "data/company.db",
    market: str = "auto",
    news_keywords: str = "",
    fetch_revenue: bool = True,
    fetch_google_news: bool = True,
    news_months: int = 3,
    settings: Settings | None = None,
) -> dict:
    settings = settings or Settings()
    company = resolve(company_input, settings)
    keywords = make_news_keywords(company, news_keywords)
    profile = company.get("data_profile", "tw_monthly_revenue")

    result = {
        "company": company,
        "revenue": None,
        "financial_report": None,
        "revenue_source": None,
        "financial_source": None,
        "news": [],
        "news_months": news_months,
        "errors": [],
        "warnings": [],
    }

    conn = connect(db_path)
    try:
        company_row = {
            **company,
            "news_keywords": "|".join(keywords),
        }
        upsert_company(conn, company_row)

        if fetch_revenue:
            # ---------------- Taiwan ----------------
            if profile == "tw_monthly_revenue":
                try:
                    rev = fetch_month_revenue_history(
                        company["stock_id"], year, month, settings
                    )
                    rev.update({
                        "symbol": company["symbol"],
                        "company_name": company.get("company_name", ""),
                        "currency": "TWD",
                        "amount_unit": "TWD",
                    })
                    result["revenue"] = rev
                    result["revenue_source"] = "FinMind"
                    upsert_revenue(conn, rev)
                except Exception as e:
                    result["warnings"].append(f"FinMind：{e}")

                if result["revenue"] is None and "上市" in str(company.get("market", "")):
                    try:
                        rev = fetch_revenue_from_latest_snapshot(
                            company["stock_id"], year, month, settings
                        )
                        if rev:
                            rev.update({
                                "symbol": company["symbol"],
                                "currency": "TWD",
                                "amount_unit": "TWD",
                            })
                            result["revenue"] = rev
                            result["revenue_source"] = "TWSE OpenAPI"
                            upsert_revenue(conn, rev)
                    except Exception as e:
                        result["warnings"].append(f"TWSE OpenAPI：{e}")

            # ---------------- Pou Sheng ----------------
            elif profile == "hk_pousheng":
                try:
                    rev = fetch_pousheng_monthly_revenue(year, month, settings)
                    rev["symbol"] = company["symbol"]
                    result["revenue"] = rev
                    result["revenue_source"] = "Pou Sheng IR"
                    upsert_revenue(conn, rev)
                except Exception as e:
                    result["warnings"].append(f"寶勝月收益：{e}")

                try:
                    fin = _financial_fallback(company, year, month)
                    result["financial_report"] = fin
                    result["financial_source"] = "Yahoo Finance"
                    upsert_financial_report(conn, fin)
                except Exception as e:
                    result["warnings"].append(f"寶勝財報 fallback：{e}")

            # ---------------- Yue Yuen ----------------
            elif profile == "hk_yueyuen":
                # 1. 公司官方 IR
                try:
                    rev = fetch_yueyuen_official_monthly_revenue(
                        year, month, settings
                    )
                    result["revenue"] = rev
                    result["revenue_source"] = "Yue Yuen Official IR"
                    upsert_revenue(conn, rev)
                except Exception as e:
                    result["warnings"].append(f"裕元官方 IR：{e}")

                # 2. HKEX fallback
                if result["revenue"] is None:
                    try:
                        rev = fetch_yueyuen_monthly_revenue(
                            year, month, settings
                        )
                        result["revenue"] = rev
                        result["revenue_source"] = "HKEX"
                        upsert_revenue(conn, rev)
                    except Exception as e:
                        result["warnings"].append(f"裕元 HKEX fallback：{e}")

                # 3. 財報 fallback
                try:
                    fin = _financial_fallback(company, year, month)
                    result["financial_report"] = fin
                    result["financial_source"] = "Yahoo Finance"
                    upsert_financial_report(conn, fin)
                except Exception as e:
                    result["warnings"].append(f"裕元財報 fallback：{e}")

            # ---------------- Stella ----------------
            elif profile == "hk_financial":
                try:
                    fin = _financial_fallback(company, year, month)
                    fin["source_url"] = company.get("official_url") or fin["source_url"]
                    result["financial_report"] = fin
                    result["financial_source"] = "Yahoo Finance / Stella IR"
                    upsert_financial_report(conn, fin)
                except Exception as e:
                    result["errors"].append(f"九興財報：{e}")

            # ---------------- Huali ----------------
            elif profile == "cn_financial":
                try:
                    fin = fetch_huali_financial(year, month)
                    fin["symbol"] = company["symbol"]
                    result["financial_report"] = fin
                    result["financial_source"] = "AKShare / Eastmoney"
                    upsert_financial_report(conn, fin)
                except Exception as e:
                    result["warnings"].append(f"華利 AKShare：{e}")
                    try:
                        fin = _financial_fallback(company, year, month)
                        result["financial_report"] = fin
                        result["financial_source"] = "Yahoo Finance fallback"
                        upsert_financial_report(conn, fin)
                    except Exception as e2:
                        result["errors"].append(f"華利財報：{e2}")

        if fetch_google_news:
            try:
                rows = fetch_news(
                    company["stock_id"], keywords, year, month, settings,
                    months=news_months,
                )
                result["news"] = rows
                upsert_news(conn, rows)
            except Exception as e:
                result["errors"].append(f"Google News：{e}")

    finally:
        conn.close()

    return result
