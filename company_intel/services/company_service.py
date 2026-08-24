from __future__ import annotations
from ..crawlers.twse import resolve_company
from ..config import Settings

def make_news_keywords(company: dict, user_keywords: str = "") -> list[str]:
    base = [
        company.get("short_name", ""),
        company.get("company_name", ""),
    ]
    extra = [x.strip() for x in user_keywords.replace("；", "|").replace(",", "|").split("|")]
    out = []
    for x in base + extra:
        if x and x not in out:
            out.append(x)
    return out

def resolve(keyword: str, settings: Settings) -> dict:
    company = resolve_company(keyword, settings)
    if company:
        return company

    # 若非上市公司或 OpenAPI 查不到，允許直接輸入「股票代號 公司名稱」。
    parts = keyword.strip().split(maxsplit=1)
    if parts and parts[0].isdigit():
        stock_id = parts[0]
        name = parts[1] if len(parts) > 1 else parts[0]
        return {
            "stock_id": stock_id,
            "company_name": name,
            "short_name": name,
            "market": "未知",
            "industry": "",
        }
    raise LookupError(
        f"找不到公司：{keyword}。可改輸入「股票代號 公司名稱」，例如：9904 寶成。"
    )
