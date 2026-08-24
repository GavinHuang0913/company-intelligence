from __future__ import annotations
import requests
from typing import Optional
from ..config import Settings

BASE = "https://openapi.twse.com.tw/v1"
COMPANY_API = f"{BASE}/opendata/t187ap03_L"
LATEST_REVENUE_API = f"{BASE}/opendata/t187ap05_L"

def _session(settings: Settings) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": settings.user_agent,
        "Accept": "application/json,text/plain,*/*",
    })
    return s

def _num(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("%", "")
    if s in {"", "-", "--", "None", "nan"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _thousand_twd_to_twd(v):
    n = _num(v)
    return None if n is None else n * 1000

def _parse_roc_yyyymm(value: str) -> tuple[int, int] | None:
    s = str(value or "").strip()
    if len(s) < 5 or not s[:5].isdigit():
        return None
    roc_year = int(s[:-2])
    month = int(s[-2:])
    if not 1 <= month <= 12:
        return None
    return roc_year + 1911, month

def fetch_listed_companies(settings: Settings) -> list[dict]:
    r = _session(settings).get(COMPANY_API, timeout=settings.request_timeout)
    r.raise_for_status()
    data = r.json()
    result = []
    for x in data:
        stock_id = str(x.get("公司代號", "")).strip()
        if not stock_id:
            continue
        result.append({
            "stock_id": stock_id,
            "company_name": str(x.get("公司名稱", "")).strip(),
            "short_name": str(x.get("公司簡稱", "")).strip(),
            "market": "上市",
            "industry": str(x.get("產業別", "")).strip(),
        })
    return result

def resolve_company(keyword: str, settings: Settings) -> Optional[dict]:
    key = keyword.strip().lower()
    companies = fetch_listed_companies(settings)
    exact, partial = [], []
    for c in companies:
        values = [c["stock_id"], c["company_name"], c["short_name"]]
        lowered = [str(v).lower() for v in values if v]
        if key in lowered:
            exact.append(c)
        elif any(key in v for v in lowered):
            partial.append(c)
    found = exact or partial
    return found[0] if found else None

def fetch_latest_revenues(settings: Settings) -> list[dict]:
    r = _session(settings).get(LATEST_REVENUE_API, timeout=settings.request_timeout)
    r.raise_for_status()
    return r.json()

def fetch_latest_revenue_for_company(
    stock_id: str,
    requested_year: int,
    requested_month: int,
    settings: Settings,
) -> dict | None:
    rows = fetch_latest_revenues(settings)
    raw = next(
        (x for x in rows if str(x.get("公司代號", "")).strip() == str(stock_id).strip()),
        None
    )
    if raw is None:
        return None

    period = _parse_roc_yyyymm(raw.get("資料年月", ""))
    if period is None:
        raise RuntimeError("TWSE OpenAPI 缺少或無法解析「資料年月」")
    year, month = period

    # OpenAPI 只提供最新一期，月份不吻合時不能假裝是使用者查的月份。
    if (year, month) != (int(requested_year), int(requested_month)):
        return None

    return {
        "stock_id": str(stock_id),
        "year": year,
        "month": month,
        "company_name": str(raw.get("公司名稱", "")).strip(),
        "revenue": _thousand_twd_to_twd(raw.get("營業收入-當月營收")),
        "revenue_last_year": _thousand_twd_to_twd(raw.get("營業收入-去年當月營收")),
        "yoy": _num(raw.get("營業收入-去年同月增減(%)")),
        "accumulated_revenue": _thousand_twd_to_twd(raw.get("累計營業收入-當月累計營收")),
        "accumulated_last_year": _thousand_twd_to_twd(raw.get("累計營業收入-去年累計營收")),
        "accumulated_yoy": _num(raw.get("累計營業收入-前期比較增減(%)")),
        "note": str(raw.get("備註", "")).strip(),
        "source_url": LATEST_REVENUE_API,
        "source_type": "twse_openapi_latest",
        "currency": "TWD",
        "amount_unit": "TWD",
        "unit": "TWD",
    }


from datetime import date
from dateutil.relativedelta import relativedelta

def _latest_row_for_company(stock_id: str, settings: Settings) -> dict | None:
    rows = fetch_latest_revenues(settings)
    return next(
        (x for x in rows if str(x.get("公司代號", "")).strip() == str(stock_id).strip()),
        None
    )

def fetch_revenue_from_latest_snapshot(
    stock_id: str,
    requested_year: int,
    requested_month: int,
    settings: Settings,
) -> dict | None:
    """
    以 TWSE 最新月營收快照處理：
    1) 指定月 = 最新月：完整回傳
    2) 指定月 = 最新月前一個月：可可靠取得「上月營收」，
       其他無法由快照還原的欄位保持 None，不猜測。
    3) 其餘月份：回傳 None，交由歷史來源處理。
    """
    raw = _latest_row_for_company(stock_id, settings)
    if raw is None:
        return None

    period = _parse_roc_yyyymm(raw.get("資料年月", ""))
    if period is None:
        raise RuntimeError("TWSE OpenAPI 缺少或無法解析「資料年月」")

    latest_year, latest_month = period

    if (latest_year, latest_month) == (int(requested_year), int(requested_month)):
        return {
            "stock_id": str(stock_id),
            "year": latest_year,
            "month": latest_month,
            "company_name": str(raw.get("公司名稱", "")).strip(),
            "revenue": _thousand_twd_to_twd(raw.get("營業收入-當月營收")),
            "revenue_last_year": _thousand_twd_to_twd(raw.get("營業收入-去年當月營收")),
            "yoy": _num(raw.get("營業收入-去年同月增減(%)")),
            "accumulated_revenue": _thousand_twd_to_twd(raw.get("累計營業收入-當月累計營收")),
            "accumulated_last_year": _thousand_twd_to_twd(raw.get("累計營業收入-去年累計營收")),
            "accumulated_yoy": _num(raw.get("累計營業收入-前期比較增減(%)")),
            "note": str(raw.get("備註", "")).strip(),
            "source_url": LATEST_REVENUE_API,
            "source_type": "twse_openapi_latest",
            "currency": "TWD",
            "amount_unit": "TWD",
            "unit": "TWD",
            "data_quality": "complete",
        }

    latest_first = date(latest_year, latest_month, 1)
    prev = latest_first - relativedelta(months=1)
    if (prev.year, prev.month) == (int(requested_year), int(requested_month)):
        # 只能從最新快照可靠取得上月營收；其他欄位不能杜撰。
        return {
            "stock_id": str(stock_id),
            "year": int(requested_year),
            "month": int(requested_month),
            "company_name": str(raw.get("公司名稱", "")).strip(),
            "revenue": _thousand_twd_to_twd(raw.get("營業收入-上月營收")),
            "revenue_last_year": None,
            "yoy": None,
            "accumulated_revenue": None,
            "accumulated_last_year": None,
            "accumulated_yoy": None,
            "note": "此月份由 TWSE 最新月營收快照的「上月營收」欄位還原；YoY/累計欄位未由官方快照提供，因此不推估。",
            "source_url": LATEST_REVENUE_API,
            "source_type": "twse_openapi_previous_month",
            "currency": "TWD",
            "amount_unit": "TWD",
            "unit": "TWD",
            "data_quality": "partial",
        }

    return None
