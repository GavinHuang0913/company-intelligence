from __future__ import annotations
from io import StringIO
import re
import pandas as pd
import requests
from ..config import Settings

# MOPS 歷史月營收靜態頁；上市=sii，上櫃=otc。
URL_TEMPLATE = "https://mops.twse.com.tw/nas/t21/{market}/t21sc03_{roc_year}_{month}.html"

COLUMN_ALIASES = {
    "公司代號": "stock_id",
    "公司名稱": "company_name",
    "當月營收": "revenue",
    "上月營收": "previous_month_revenue",
    "去年當月營收": "revenue_last_year",
    "上月比較增減(%)": "mom",
    "去年同月增減(%)": "yoy",
    "當月累計營收": "accumulated_revenue",
    "去年累計營收": "accumulated_last_year",
    "前期比較增減(%)": "accumulated_yoy",
    "備註": "note",
}

def _norm_col(c) -> str:
    if isinstance(c, tuple):
        c = " ".join(str(x) for x in c if str(x) != "nan")
    c = re.sub(r"\s+", "", str(c))
    c = c.replace("％", "%")
    return c

def _to_num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip().replace(",", "").replace("%", "")
    if s in {"", "-", "--", "nan", "None"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None

def fetch_monthly_revenue(stock_id: str, year: int, month: int, settings: Settings, market: str = "sii") -> dict:
    if market not in {"sii", "otc"}:
        raise ValueError("market must be sii or otc")
    roc_year = year - 1911
    if roc_year <= 0:
        raise ValueError("year must be Gregorian year, e.g. 2026")
    url = URL_TEMPLATE.format(market=market, roc_year=roc_year, month=month)

    headers = {
        "User-Agent": settings.user_agent,
        "Referer": "https://mops.twse.com.tw/",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
    }
    r = requests.get(url, headers=headers, timeout=settings.request_timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "big5"

    tables = pd.read_html(StringIO(r.text))
    wanted = None
    for df in tables:
        cols = [_norm_col(c) for c in df.columns]
        if any("公司代號" in c for c in cols) and any("當月營收" in c for c in cols):
            df = df.copy()
            df.columns = cols
            wanted = df
            break

    if wanted is None:
        raise RuntimeError(f"找不到月營收資料表：{url}")

    # 有些頁面公司代號欄位可能混入空白/總計列。
    code_col = next(c for c in wanted.columns if "公司代號" in c)
    rows = wanted[wanted[code_col].astype(str).str.strip() == str(stock_id).strip()]
    if rows.empty:
        raise LookupError(f"{stock_id} 在 {year}/{month:02d} ({market}) 找不到月營收")

    raw = rows.iloc[0].to_dict()
    normalized = {}
    for col, value in raw.items():
        canonical = None
        for zh, en in COLUMN_ALIASES.items():
            if zh in col:
                canonical = en
                break
        if canonical:
            normalized[canonical] = value

    numeric = {
        "revenue", "revenue_last_year", "yoy",
        "accumulated_revenue", "accumulated_last_year", "accumulated_yoy"
    }

    out = {
        "stock_id": str(stock_id),
        "year": int(year),
        "month": int(month),
        "company_name": str(normalized.get("company_name", "")).strip(),
        "note": str(normalized.get("note", "")).strip(),
        "source_url": url,
    }
    for key in numeric:
        out[key] = _to_num(normalized.get(key))
    return out
