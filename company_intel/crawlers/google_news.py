from __future__ import annotations
from datetime import date, datetime, timezone
from urllib.parse import quote_plus
from email.utils import parsedate_to_datetime
import calendar
import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from ..config import Settings

NEGATIVE_TITLE_TERMS_BY_STOCK = {
    "0551": [
        "裕元花園酒店", "花園酒店", "酒店", "餐廳", "下午茶",
        "端粽", "粽禮", "粽", "父親節", "蛋糕",
        "裕元獎", "合唱", "交響樂團",
    ],
}

def news_window(year: int, month: int, months: int = 3) -> tuple[date, date]:
    if months < 1:
        raise ValueError("months must be >= 1")
    selected = date(year, month, 1)
    start = selected - relativedelta(months=months - 1)
    last_day = calendar.monthrange(year, month)[1]
    end = date(year, month, last_day)
    return start, end

def build_query(keywords: list[str], year: int, month: int, months: int = 3, stock_id: str | None = None) -> str:
    start, end = news_window(year, month, months)
    terms = [k.strip() for k in keywords if k and k.strip()]
    if not terms:
        raise ValueError("至少需要一個新聞關鍵字")
    company_part = " OR ".join(f'"{x}"' for x in terms)
    # before 是排除該日，所以用 end + 1 day
    end_exclusive = end + relativedelta(days=1)
    negative = ""
    if stock_id:
        for term in NEGATIVE_TITLE_TERMS_BY_STOCK.get(str(stock_id), []):
            negative += f' -"{term}"'
    return (
        f"({company_part}){negative} "
        f"after:{start.isoformat()} before:{end_exclusive.isoformat()}"
    )

def build_rss_url(query: str, settings: Settings) -> str:
    return (
        "https://news.google.com/rss/search"
        f"?q={quote_plus(query)}"
        f"&hl={quote_plus(settings.news_language)}"
        f"&gl={quote_plus(settings.news_country)}"
        f"&ceid={quote_plus(settings.news_ceid)}"
    )

def _parse_pub_date(raw: str):
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date()
    except Exception:
        return None

def _company_relevant(title: str, keywords: list[str]) -> bool:
    t = title.lower()
    # 至少命中一個公司/使用者關鍵字，降低「寶成」被切成一般中文字詞造成的雜訊。
    return any(k.strip().lower() in t for k in keywords if k and k.strip())

def fetch_news(
    stock_id: str,
    keywords: list[str],
    year: int,
    month: int,
    settings: Settings,
    limit: int = 100,
    months: int = 3,
) -> list[dict]:
    start, end = news_window(year, month, months)
    query = build_query(keywords, year, month, months, stock_id=stock_id)
    url = build_rss_url(query, settings)
    r = requests.get(
        url,
        headers={"User-Agent": settings.user_agent},
        timeout=settings.request_timeout,
    )
    r.raise_for_status()
    feed = feedparser.parse(r.content)

    rows = []
    for e in feed.entries:
        title = BeautifulSoup(
            getattr(e, "title", ""), "html.parser"
        ).get_text(" ", strip=True)

        published_raw = getattr(e, "published", "")
        pub_date = _parse_pub_date(published_raw)

        # 日期硬卡控：RSS 即使回傳超出 query 的內容也丟掉。
        if pub_date is None or not (start <= pub_date <= end):
            continue

        # 標題相關性卡控，避免完全不相干的文章。
        if not _company_relevant(title, keywords):
            continue

        negative_terms = NEGATIVE_TITLE_TERMS_BY_STOCK.get(str(stock_id), [])
        if any(term.lower() in title.lower() for term in negative_terms):
            continue

        source = ""
        if getattr(e, "source", None):
            source = getattr(e.source, "title", "") or ""

        rows.append({
            "stock_id": str(stock_id),
            "title": title,
            "publish_date": pub_date.isoformat(),
            "source": source,
            "url": getattr(e, "link", ""),
            "query": query,
        })
        if len(rows) >= limit:
            break

    # 固定先按日期由新到舊，UI 可再切換升冪/降冪。
    rows.sort(key=lambda x: x.get("publish_date") or "", reverse=True)
    return rows
