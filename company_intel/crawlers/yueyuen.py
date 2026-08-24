from __future__ import annotations
from io import BytesIO
from urllib.parse import urljoin
import calendar
import re
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from ..config import Settings

HKEX_SEARCH = (
    "https://www1.hkexnews.hk/search/titlesearch.xhtml"
    "?category=0&market=SEHK&stockId=1172"
)

MONTHS = {
    1:"JANUARY",2:"FEBRUARY",3:"MARCH",4:"APRIL",5:"MAY",6:"JUNE",
    7:"JULY",8:"AUGUST",9:"SEPTEMBER",10:"OCTOBER",11:"NOVEMBER",12:"DECEMBER"
}

def _money(text: str, pattern: str):
    m = re.search(pattern, text, flags=re.I | re.S)
    if not m:
        return None
    return float(m.group(1).replace(",", "")) * 1000

def _pct_token(token: str):
    token = token.strip()
    neg = token.startswith("(") and token.endswith(")")
    token = token.strip("()").replace("%","")
    try:
        v = float(token)
        return -v if neg else v
    except Exception:
        return None

def _extract_revenue_yoy(text: str):
    # 例如：Net consolidated operating revenue (2.5)% (0.7)%
    m = re.search(
        r"Net consolidated operating revenue\s+(\(?[-+]?\d+(?:\.\d+)?\)?%)\s+(\(?[-+]?\d+(?:\.\d+)?\)?%)",
        text,
        flags=re.I,
    )
    if not m:
        return None, None
    return _pct_token(m.group(1)), _pct_token(m.group(2))

def fetch_yueyuen_monthly_revenue(
    year: int,
    month: int,
    settings: Settings,
) -> dict:
    title = f"MONTHLY REVENUE ANNOUNCEMENT FOR {MONTHS[int(month)]} {int(year)}"

    r = requests.get(
        HKEX_SEARCH,
        headers={"User-Agent": settings.user_agent},
        timeout=settings.request_timeout,
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    target = None
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).upper().split())
        if title in text:
            target = urljoin(HKEX_SEARCH, a["href"])
            break

    if not target:
        raise LookupError(f"HKEX 找不到裕元 {year}/{month:02d} 月營收公告")

    pdf = requests.get(
        target,
        headers={"User-Agent": settings.user_agent},
        timeout=settings.request_timeout,
    )
    pdf.raise_for_status()

    reader = PdfReader(BytesIO(pdf.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    revenue = _money(
        text,
        r"current month\s*\(USD[’']000\)\s*:\s*([\d,]+)",
    )
    ytd = _money(
        text,
        r"ended\s+\w+\s+\d{1,2},\s+\d{4}\s*\(USD[’']000\)\s*:\s*([\d,]+)",
    )
    yoy, ytd_yoy = _extract_revenue_yoy(text)

    if revenue is None:
        raise RuntimeError("找到裕元公告，但無法解析當月 Net consolidated operating revenue")

    return {
        "stock_id": "0551",
        "symbol": "0551.HK",
        "year": int(year),
        "month": int(month),
        "company_name": "Yue Yuen Industrial (Holdings) Limited",
        "revenue": revenue,
        "previous_month_revenue": None,
        "revenue_last_year": None,
        "mom": None,
        "yoy": yoy,
        "accumulated_revenue": ytd,
        "accumulated_last_year": None,
        "accumulated_yoy": ytd_yoy,
        "currency": "USD",
        "amount_unit": "USD",
        "note": "HKEX Monthly Revenue Announcement；原始單位 USD'000，DB 已換算為 USD 元。",
        "source_url": target,
        "source_type": "hkex_yueyuen_monthly",
        "data_quality": "complete",
    }
