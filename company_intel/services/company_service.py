from __future__ import annotations
from ..crawlers.twse import resolve_company
from ..config import Settings
from ..company_registry import resolve_international

def make_news_keywords(company: dict, user_keywords: str = "") -> list[str]:
    base = [
        company.get("short_name", ""),
        company.get("company_name", ""),
        company.get("symbol", ""),
        *company.get("news_keywords", []),
    ]
    extra = [
        x.strip()
        for x in user_keywords.replace("；", "|").replace(",", "|").split("|")
    ]
    out = []
    for x in base + extra:
        if x and x not in out:
            out.append(x)
    return out

def resolve(keyword: str, settings: Settings) -> dict:
    raw = keyword.strip()

    intl = resolve_international(raw)
    if intl:
        return intl

    # 支援 9904.TW
    upper = raw.upper()
    if upper.endswith(".TW"):
        raw = raw[:-3].strip()

    parts = raw.split(maxsplit=1)
    stock_hint = parts[0] if parts and parts[0].isdigit() else None
    name_hint = parts[1].strip() if len(parts) > 1 else ""

    search_key = stock_hint or raw
    company = resolve_company(search_key, settings)
    if company:
        company.update({
            "symbol": f'{company["stock_id"]}.TW',
            "currency": "TWD",
            "exchange": "TWSE",
            "data_profile": "tw_monthly_revenue",
        })
        return company

    if name_hint:
        company = resolve_company(name_hint, settings)
        if company:
            company.update({
                "symbol": f'{company["stock_id"]}.TW',
                "currency": "TWD",
                "exchange": "TWSE",
                "data_profile": "tw_monthly_revenue",
            })
            return company

    if stock_hint:
        name = name_hint or stock_hint
        return {
            "stock_id": stock_hint,
            "symbol": f"{stock_hint}.TW",
            "company_name": name,
            "short_name": name,
            "market": "TW",
            "exchange": "TWSE",
            "industry": "",
            "currency": "TWD",
            "data_profile": "tw_monthly_revenue",
        }

    raise LookupError(f"找不到公司：{keyword}")
