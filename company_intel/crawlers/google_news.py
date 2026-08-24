from __future__ import annotations
from datetime import date, timedelta
from urllib.parse import quote_plus
import calendar
import feedparser
import requests
from bs4 import BeautifulSoup
from ..config import Settings

def _month_range(year: int, month: int) -> tuple[date, date]:
    last = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    # Google search 的 before: 是排除該日，因此使用次月 1 日。
    end_exclusive = date(year, month, last) + timedelta(days=1)
    return start, end_exclusive

def build_query(keywords: list[str], year: int, month: int) -> str:
    start, end_exclusive = _month_range(year, month)
    terms = [k.strip() for k in keywords if k and k.strip()]
    if not terms:
        raise ValueError("至少需要一個新聞關鍵字")
    company_part = " OR ".join(f'"{x}"' for x in terms)
    return f"({company_part}) after:{start.isoformat()} before:{end_exclusive.isoformat()}"

def build_rss_url(query: str, settings: Settings) -> str:
    return (
        "https://news.google.com/rss/search"
        f"?q={quote_plus(query)}"
        f"&hl={quote_plus(settings.news_language)}"
        f"&gl={quote_plus(settings.news_country)}"
        f"&ceid={quote_plus(settings.news_ceid)}"
    )

def fetch_news(stock_id: str, keywords: list[str], year: int, month: int, settings: Settings, limit: int = 100) -> list[dict]:
    query = build_query(keywords, year, month)
    url = build_rss_url(query, settings)
    r = requests.get(
        url,
        headers={"User-Agent": settings.user_agent},
        timeout=settings.request_timeout,
    )
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    rows = []
    for e in feed.entries[:limit]:
        source = ""
        if getattr(e, "source", None):
            source = getattr(e.source, "title", "") or ""
        title = BeautifulSoup(getattr(e, "title", ""), "html.parser").get_text(" ", strip=True)
        rows.append({
            "stock_id": str(stock_id),
            "title": title,
            "publish_date": getattr(e, "published", ""),
            "source": source,
            "url": getattr(e, "link", ""),
            "query": query,
        })
    return rows
