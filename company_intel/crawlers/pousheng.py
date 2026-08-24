from __future__ import annotations
from io import StringIO
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from ..config import Settings

URL = "https://en.pousheng.com/cn/Revenue.html"

def _num(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("%", "")
    if s in {"", "-", "--", "nan"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None

def fetch_pousheng_monthly_revenue(year: int, month: int, settings: Settings) -> dict:
    r = requests.get(URL, headers={"User-Agent": settings.user_agent}, timeout=settings.request_timeout)
    r.raise_for_status()
    r.encoding = "utf-8"

    soup = BeautifulSoup(r.text, "lxml")
    years = []
    for opt in soup.find_all("option"):
        txt = opt.get_text(" ", strip=True)
        m = re.fullmatch(r"20\d{2}", txt)
        if m:
            y = int(txt)
            if y not in years:
                years.append(y)

    tables = pd.read_html(StringIO(r.text))
    revenue_tables = []
    for df in tables:
        cols = [str(c).strip() for c in df.columns]
        joined = "|".join(cols)
        if "Month" in joined and ("Monthly Rev" in joined or "Monthly Rev." in joined):
            revenue_tables.append(df)

    if not revenue_tables:
        raise RuntimeError("寶勝 IR 月收益頁找不到 revenue table")

    # 頁面通常按年份由新到舊排列；若 HTML option 有年份就用它對應。
    if years and len(years) >= len(revenue_tables):
        year_map = {y: t for y, t in zip(years, revenue_tables)}
    else:
        # 若抓不到年份 option，假設第一張是目前最新年度，往前遞減。
        current_year = max(year, 2026)
        year_map = {current_year - i: t for i, t in enumerate(revenue_tables)}

    df = year_map.get(int(year))
    if df is None:
        raise LookupError(f"寶勝官方 IR 找不到 {year} 年月收益表")

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    month_col = next((c for c in df.columns if "Month" == c or c.startswith("Month")), df.columns[0])
    rows = df[pd.to_numeric(df[month_col], errors="coerce") == int(month)]
    if rows.empty:
        raise LookupError(f"寶勝 {year}/{month:02d} 尚未公布或找不到")

    row = rows.iloc[0]
    rev_col = next(c for c in df.columns if "Monthly Rev" in c)
    ytd_col = next(c for c in df.columns if "YTD Rev" in c)
    yoy_month_col = next(c for c in df.columns if "YoY" in c and "Monthly" in c)
    yoy_ytd_col = next(c for c in df.columns if "YoY" in c and "YTD" in c)

    revenue_thousand = _num(row[rev_col])
    ytd_thousand = _num(row[ytd_col])

    # 官方表數字單位按 IR 慣例為 RMB '000；統一 DB 存「元」。
    revenue = revenue_thousand * 1000 if revenue_thousand is not None else None
    ytd = ytd_thousand * 1000 if ytd_thousand is not None else None

    return {
        "stock_id": "3813",
        "year": int(year),
        "month": int(month),
        "symbol": "3813.HK",
        "company_name": "Pou Sheng International (Holdings) Limited",
        "revenue": revenue,
        "previous_month_revenue": None,
        "revenue_last_year": None,
        "mom": None,
        "yoy": _num(row[yoy_month_col]),
        "accumulated_revenue": ytd,
        "accumulated_last_year": None,
        "accumulated_yoy": _num(row[yoy_ytd_col]),
        "note": "寶勝官方 IR Monthly Revenue；原始表金額以千元呈現，DB 已統一換算為 CNY 元。",
        "source_url": URL,
        "source_type": "pousheng_ir_monthly",
        "data_quality": "complete",
        "currency": "CNY",
        "amount_unit": "CNY",
        "unit": "CNY",
    }
