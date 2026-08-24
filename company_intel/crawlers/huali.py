from __future__ import annotations
from datetime import date
import pandas as pd

def _first(row: pd.Series, names: list[str]):
    for name in names:
        if name in row.index:
            v = row[name]
            if pd.notna(v):
                try:
                    return float(v)
                except Exception:
                    return v
    return None

def _pick_period(df: pd.DataFrame, year: int, month: int) -> pd.Series:
    if df is None or df.empty:
        raise LookupError("財報資料為空")
    date_col = next((c for c in ["REPORT_DATE", "报告期", "報告期"] if c in df.columns), None)
    if date_col is None:
        raise RuntimeError("AKShare 回傳資料找不到 REPORT_DATE/報告期")

    tmp = df.copy()
    tmp["_date"] = pd.to_datetime(tmp[date_col], errors="coerce")
    tmp = tmp[tmp["_date"].notna()]
    cutoff = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
    tmp = tmp[tmp["_date"] <= cutoff]
    if tmp.empty:
        raise LookupError(f"找不到 {year}/{month:02d} 以前已公布的財報")
    tmp = tmp.sort_values("_date", ascending=False)
    return tmp.iloc[0]

def fetch_huali_financial(year: int, month: int) -> dict:
    try:
        import akshare as ak
    except Exception as e:
        raise RuntimeError("未安裝 akshare，請執行 pip install -r requirements.txt") from e

    symbol = "SZ300979"
    profit = ak.stock_profit_sheet_by_report_em(symbol=symbol)
    balance = ak.stock_balance_sheet_by_report_em(symbol=symbol)
    cash = ak.stock_cash_flow_sheet_by_report_em(symbol=symbol)

    prow = _pick_period(profit, year, month)
    brow = _pick_period(balance, year, month)
    crow = _pick_period(cash, year, month)

    report_date = pd.to_datetime(prow["_date"]).date().isoformat()

    return {
        "stock_id": "300979",
        "symbol": "300979.SZ",
        "company_name": "中山华利实业集团股份有限公司",
        "year": int(report_date[:4]),
        "period_end": report_date,
        "period_type": (
            "FY" if report_date.endswith("-12-31")
            else "Q3" if report_date.endswith("-09-30")
            else "H1" if report_date.endswith("-06-30")
            else "Q1"
        ),
        "currency": "CNY",
        "revenue": _first(prow, ["TOTAL_OPERATE_INCOME", "OPERATE_INCOME", "营业总收入", "营业收入"]),
        "operating_profit": _first(prow, ["OPERATE_PROFIT", "营业利润"]),
        "net_profit": _first(prow, ["PARENT_NETPROFIT", "NETPROFIT", "归属于母公司股东的净利润", "净利润"]),
        "eps": _first(prow, ["BASIC_EPS", "基本每股收益"]),
        "total_assets": _first(brow, ["TOTAL_ASSETS", "资产总计"]),
        "total_liabilities": _first(brow, ["TOTAL_LIABILITIES", "负债合计"]),
        "equity": _first(brow, ["TOTAL_EQUITY", "TOTAL_PARENT_EQUITY", "股东权益合计", "所有者权益合计"]),
        "operating_cashflow": _first(crow, ["NETCASH_OPERATE", "NET_CASH_OPERATE", "经营活动产生的现金流量净额"]),
        "source_type": "akshare_eastmoney_financial",
        "source_url": "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=SZ300979",
    }
