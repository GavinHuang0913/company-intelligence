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

def fetch_listed_companies(settings: Settings) -> list[dict]:
    r = _session(settings).get(COMPANY_API, timeout=settings.request_timeout)
    r.raise_for_status()
    data = r.json()
    result = []
    for x in data:
        stock_id = str(
            x.get("公司代號") or x.get("公司代碼") or x.get("出表日期", "")
        ).strip()
        if not stock_id or not stock_id[:4].isdigit():
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
    found = (exact or partial)
    return found[0] if found else None

def fetch_latest_revenues(settings: Settings) -> list[dict]:
    r = _session(settings).get(LATEST_REVENUE_API, timeout=settings.request_timeout)
    r.raise_for_status()
    return r.json()
