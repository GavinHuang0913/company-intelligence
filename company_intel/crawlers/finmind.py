from __future__ import annotations

from datetime import date
import os
import requests
from dateutil.relativedelta import relativedelta
from ..config import Settings

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

def _to_int(v):
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None

def _pct(current, base):
    if current is None or base in (None, 0):
        return None
    return (current - base) / base * 100.0

def fetch_month_revenue_history(
    stock_id: str,
    year: int,
    month: int,
    settings: Settings,
    token: str | None = None,
) -> dict:
    """
    用 FinMind TaiwanStockMonthRevenue 取得歷史月營收，
    並自行計算 MOPS 常見完整欄位。

    FinMind 的 date 通常是資料建立/公布月份；
    真正營收所屬年月以 revenue_year / revenue_month 為準。
    """
    if not 1 <= int(month) <= 12:
        raise ValueError("month 必須是 1~12")

    # 為了計算去年累計，至少從「前一年 1 月」開始抓。
    start = date(int(year) - 1, 1, 1)

    # target 月資料通常於次月建立，因此 end_date 多留兩個月。
    target_first = date(int(year), int(month), 1)
    end = target_first + relativedelta(months=2)

    params = {
        "dataset": "TaiwanStockMonthRevenue",
        "data_id": str(stock_id),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }

    headers = {
        "User-Agent": settings.user_agent,
        "Accept": "application/json",
    }
    token = token or os.getenv("FINMIND_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    r = requests.get(
        FINMIND_URL,
        params=params,
        headers=headers,
        timeout=settings.request_timeout,
    )
    r.raise_for_status()
    payload = r.json()

    status = payload.get("status")
    if status not in (None, 200):
        msg = payload.get("msg") or payload.get("message") or str(payload)
        raise RuntimeError(f"FinMind API status={status}: {msg}")

    rows = payload.get("data") or []
    if not rows:
        raise LookupError(f"FinMind 找不到 {stock_id} 的月營收歷史資料")

    # 以營收所屬年月建立 index；若重複則取後出現的一筆。
    idx: dict[tuple[int, int], int] = {}
    for row in rows:
        ry = _to_int(row.get("revenue_year"))
        rm = _to_int(row.get("revenue_month"))
        revenue = _to_int(row.get("revenue"))
        if ry is None or rm is None or revenue is None:
            continue
        idx[(ry, rm)] = revenue

    key = (int(year), int(month))
    revenue = idx.get(key)
    if revenue is None:
        raise LookupError(f"FinMind 找不到 {stock_id} {year}/{month:02d} 月營收")

    prev_first = target_first - relativedelta(months=1)
    prev_revenue = idx.get((prev_first.year, prev_first.month))
    last_year_revenue = idx.get((int(year) - 1, int(month)))

    # 累計要求 1..target month 都有值；若缺資料則不猜。
    current_months = [idx.get((int(year), m)) for m in range(1, int(month) + 1)]
    previous_months = [idx.get((int(year) - 1, m)) for m in range(1, int(month) + 1)]

    accumulated_revenue = (
        sum(current_months) if all(v is not None for v in current_months) else None
    )
    accumulated_last_year = (
        sum(previous_months) if all(v is not None for v in previous_months) else None
    )

    missing_current = [m for m, v in enumerate(current_months, start=1) if v is None]
    missing_previous = [m for m, v in enumerate(previous_months, start=1) if v is None]

    notes = []
    if missing_current:
        notes.append(
            "本年累計未計算，缺少月份：" + ",".join(f"{m:02d}" for m in missing_current)
        )
    if missing_previous:
        notes.append(
            "去年累計未計算，缺少月份：" + ",".join(f"{m:02d}" for m in missing_previous)
        )

    return {
        "stock_id": str(stock_id),
        "year": int(year),
        "month": int(month),
        "company_name": "",
        # FinMind revenue 單位為新台幣「元」
        "revenue": revenue,
        "previous_month_revenue": prev_revenue,
        "revenue_last_year": last_year_revenue,
        "mom": _pct(revenue, prev_revenue),
        "yoy": _pct(revenue, last_year_revenue),
        "accumulated_revenue": accumulated_revenue,
        "accumulated_last_year": accumulated_last_year,
        "accumulated_yoy": _pct(accumulated_revenue, accumulated_last_year),
        "note": "；".join(notes),
        "source_url": FINMIND_URL,
        "source_type": "finmind_historical",
        "data_quality": "complete" if not notes else "partial",
        "currency": "TWD",
        "amount_unit": "TWD",
        "unit": "TWD",
    }
