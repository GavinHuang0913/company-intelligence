from __future__ import annotations
import pandas as pd

INCOME_ALIASES = {
    "revenue": ["Total Revenue", "Operating Revenue"],
    "operating_profit": ["Operating Income"],
    "net_profit": ["Net Income", "Net Income Common Stockholders"],
    "eps": ["Basic EPS", "Diluted EPS"],
}

BALANCE_ALIASES = {
    "total_assets": ["Total Assets"],
    "total_liabilities": [
        "Total Liabilities Net Minority Interest",
        "Total Liabilities",
    ],
    "equity": [
        "Stockholders Equity",
        "Total Equity Gross Minority Interest",
    ],
}

CASH_ALIASES = {
    "operating_cashflow": [
        "Operating Cash Flow",
        "Cash Flow From Continuing Operating Activities",
    ],
}

def _value(stmt: pd.DataFrame, column, aliases: list[str]):
    if stmt is None or stmt.empty:
        return None
    for name in aliases:
        if name in stmt.index:
            try:
                val = stmt.loc[name, column]
                if pd.notna(val):
                    return float(val)
            except Exception:
                pass
    return None

def _select_column(frames: list[pd.DataFrame], year: int, month: int):
    cutoff = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
    candidates = set()
    for df in frames:
        if df is not None and not df.empty:
            for c in df.columns:
                dt = pd.to_datetime(c, errors="coerce")
                if pd.notna(dt) and dt <= cutoff:
                    candidates.add(pd.Timestamp(dt))
    if not candidates:
        return None
    return max(candidates)

def fetch_yfinance_financial(
    symbol: str,
    year: int,
    month: int,
    currency: str,
    company_name: str,
    stock_id: str,
) -> dict:
    try:
        import yfinance as yf
    except Exception as e:
        raise RuntimeError("未安裝 yfinance，請重新 pip install -r requirements.txt") from e

    ticker = yf.Ticker(symbol)

    # 先抓季資料；若沒有，再用年度資料。
    q_income = ticker.quarterly_income_stmt
    q_balance = ticker.quarterly_balance_sheet
    q_cash = ticker.quarterly_cashflow

    period = _select_column([q_income, q_balance, q_cash], year, month)
    income, balance, cash = q_income, q_balance, q_cash
    period_type = "Quarterly"

    if period is None:
        income = ticker.income_stmt
        balance = ticker.balance_sheet
        cash = ticker.cashflow
        period = _select_column([income, balance, cash], year, month)
        period_type = "FY"

    if period is None:
        raise LookupError(f"{symbol} 找不到 {year}/{month:02d} 以前的 Yahoo Finance 財報")

    if period_type == "Quarterly":
        m = period.month
        period_type = {3: "Q1", 6: "H1", 9: "Q3", 12: "FY"}.get(m, "Quarterly")

    return {
        "stock_id": stock_id,
        "symbol": symbol,
        "company_name": company_name,
        "year": int(period.year),
        "period_end": period.date().isoformat(),
        "period_type": period_type,
        "currency": currency,
        "revenue": _value(income, period, INCOME_ALIASES["revenue"]),
        "operating_profit": _value(income, period, INCOME_ALIASES["operating_profit"]),
        "net_profit": _value(income, period, INCOME_ALIASES["net_profit"]),
        "eps": _value(income, period, INCOME_ALIASES["eps"]),
        "total_assets": _value(balance, period, BALANCE_ALIASES["total_assets"]),
        "total_liabilities": _value(balance, period, BALANCE_ALIASES["total_liabilities"]),
        "equity": _value(balance, period, BALANCE_ALIASES["equity"]),
        "operating_cashflow": _value(cash, period, CASH_ALIASES["operating_cashflow"]),
        "source_type": "yfinance_financial",
        "source_url": f"https://finance.yahoo.com/quote/{symbol}/financials/",
    }
