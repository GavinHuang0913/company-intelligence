from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Iterable

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS companies (
    stock_id TEXT PRIMARY KEY,
    symbol TEXT,
    company_name TEXT NOT NULL,
    short_name TEXT,
    market TEXT,
    industry TEXT,
    news_keywords TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS monthly_revenue (
    stock_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    company_name TEXT,
    revenue REAL,
    previous_month_revenue REAL,
    revenue_last_year REAL,
    mom REAL,
    yoy REAL,
    accumulated_revenue REAL,
    accumulated_last_year REAL,
    accumulated_yoy REAL,
    currency TEXT,
    amount_unit TEXT,
    source_type TEXT,
    note TEXT,
    source_url TEXT,
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(stock_id, year, month)
);

CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id TEXT NOT NULL,
    title TEXT NOT NULL,
    publish_date TEXT,
    source TEXT,
    url TEXT NOT NULL,
    query TEXT,
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, url)
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_id TEXT PRIMARY KEY,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS financial_reports (
    stock_id TEXT NOT NULL,
    symbol TEXT,
    company_name TEXT,
    year INTEGER NOT NULL,
    period_end TEXT NOT NULL,
    period_type TEXT,
    currency TEXT,
    revenue REAL,
    operating_profit REAL,
    net_profit REAL,
    eps REAL,
    total_assets REAL,
    total_liabilities REAL,
    equity REAL,
    operating_cashflow REAL,
    source_type TEXT,
    source_url TEXT,
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(stock_id, period_end)
);

CREATE INDEX IF NOT EXISTS idx_news_stock_date
ON news(stock_id, publish_date);
"""

MONEY_COLUMNS = [
    "revenue",
    "previous_month_revenue",
    "revenue_last_year",
    "accumulated_revenue",
    "accumulated_last_year",
]


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _ensure_monthly_revenue_columns(conn: sqlite3.Connection) -> None:
    cols = _table_columns(conn, "monthly_revenue")
    additions = {
        "previous_month_revenue": "REAL",
        "mom": "REAL",
        "currency": "TEXT",
        "amount_unit": "TEXT",
        "source_type": "TEXT",
    }
    for name, sql_type in additions.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE monthly_revenue ADD COLUMN {name} {sql_type}")
    conn.commit()




def _ensure_symbol_columns(conn: sqlite3.Connection) -> None:
    for table in ["companies", "monthly_revenue", "financial_reports"]:
        cols = _table_columns(conn, table)
        if "symbol" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN symbol TEXT")
    conn.commit()


def _migration_applied(conn: sqlite3.Connection, migration_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE migration_id=?", (migration_id,)
    ).fetchone()
    return row is not None


def _apply_unit_normalization_migration(conn: sqlite3.Connection) -> None:
    """
    v8 migration:
    - TWSE OpenAPI / MOPS historical values were previously stored in source unit (NTD thousand).
      Normalize monetary columns to NTD dollars by multiplying by 1000.
    - FinMind already returns NTD dollars and must NOT be multiplied.
    - Run exactly once per database.
    """
    migration_id = "20260824_normalize_monthly_revenue_to_twd_v1"
    if _migration_applied(conn, migration_id):
        return

    # Existing TWSE/MOPS rows from v1-v6 were stored as "thousand TWD".
    source_predicate = "(source_url LIKE '%openapi.twse.com.tw%' OR source_url LIKE '%mops.twse.com.tw%')"
    for col in MONEY_COLUMNS:
        conn.execute(
            f"UPDATE monthly_revenue SET {col} = {col} * 1000 "
            f"WHERE {source_predicate} AND {col} IS NOT NULL"
        )

    conn.execute(
        """
        UPDATE monthly_revenue
           SET currency='TWD', amount_unit='TWD',
               source_type=CASE
                   WHEN source_url LIKE '%openapi.twse.com.tw%' THEN 'twse_openapi'
                   WHEN source_url LIKE '%mops.twse.com.tw%' THEN 'mops'
                   WHEN source_url LIKE '%api.finmindtrade.com%' THEN 'finmind_historical'
                   ELSE COALESCE(source_type, 'legacy_unknown')
               END
        """
    )

    conn.execute(
        "INSERT INTO schema_migrations(migration_id) VALUES(?)", (migration_id,)
    )
    conn.commit()


def connect(db_path: str = "data/company.db") -> sqlite3.Connection:
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _ensure_monthly_revenue_columns(conn)
    _ensure_symbol_columns(conn)
    _apply_unit_normalization_migration(conn)
    return conn


def upsert_company(conn, company: dict) -> None:
    payload = {
        "stock_id": company.get("stock_id"),
        "symbol": company.get("symbol") or company.get("stock_id"),
        "company_name": company.get("company_name", ""),
        "short_name": company.get("short_name", ""),
        "market": company.get("market", ""),
        "industry": company.get("industry", ""),
        "news_keywords": company.get("news_keywords", ""),
    }
    conn.execute("""
        INSERT INTO companies(
            stock_id,symbol,company_name,short_name,market,industry,news_keywords,updated_at
        )
        VALUES(
            :stock_id,:symbol,:company_name,:short_name,:market,:industry,:news_keywords,CURRENT_TIMESTAMP
        )
        ON CONFLICT(stock_id) DO UPDATE SET
            symbol=excluded.symbol,
            company_name=excluded.company_name,
            short_name=excluded.short_name,
            market=excluded.market,
            industry=excluded.industry,
            news_keywords=excluded.news_keywords,
            updated_at=CURRENT_TIMESTAMP
    """, payload)
    conn.commit()

def upsert_revenue(conn, row: dict) -> None:
    payload = {
        "stock_id": row.get("stock_id"),
        "symbol": row.get("symbol") or row.get("stock_id"),
        "year": row.get("year"),
        "month": row.get("month"),
        "company_name": row.get("company_name", ""),
        "revenue": row.get("revenue"),
        "previous_month_revenue": row.get("previous_month_revenue"),
        "revenue_last_year": row.get("revenue_last_year"),
        "mom": row.get("mom"),
        "yoy": row.get("yoy"),
        "accumulated_revenue": row.get("accumulated_revenue"),
        "accumulated_last_year": row.get("accumulated_last_year"),
        "accumulated_yoy": row.get("accumulated_yoy"),
        "currency": row.get("currency") or "TWD",
        "amount_unit": row.get("amount_unit") or row.get("unit") or "TWD",
        "source_type": row.get("source_type"),
        "note": row.get("note", ""),
        "source_url": row.get("source_url", ""),
    }
    conn.execute("""
        INSERT INTO monthly_revenue(
            stock_id,symbol,year,month,company_name,revenue,previous_month_revenue,
            revenue_last_year,mom,yoy,accumulated_revenue,accumulated_last_year,
            accumulated_yoy,currency,amount_unit,source_type,note,source_url,fetched_at
        ) VALUES (
            :stock_id,:symbol,:year,:month,:company_name,:revenue,:previous_month_revenue,
            :revenue_last_year,:mom,:yoy,:accumulated_revenue,:accumulated_last_year,
            :accumulated_yoy,:currency,:amount_unit,:source_type,:note,:source_url,CURRENT_TIMESTAMP
        )
        ON CONFLICT(stock_id,year,month) DO UPDATE SET
            symbol=excluded.symbol,
            company_name=excluded.company_name,
            revenue=excluded.revenue,
            previous_month_revenue=excluded.previous_month_revenue,
            revenue_last_year=excluded.revenue_last_year,
            mom=excluded.mom,
            yoy=excluded.yoy,
            accumulated_revenue=excluded.accumulated_revenue,
            accumulated_last_year=excluded.accumulated_last_year,
            accumulated_yoy=excluded.accumulated_yoy,
            currency=excluded.currency,
            amount_unit=excluded.amount_unit,
            source_type=excluded.source_type,
            note=excluded.note,
            source_url=excluded.source_url,
            fetched_at=CURRENT_TIMESTAMP
    """, payload)
    conn.commit()


def upsert_news(conn, rows: Iterable[dict]) -> int:
    count = 0
    for row in rows:
        cur = conn.execute("""
            INSERT OR IGNORE INTO news(stock_id,title,publish_date,source,url,query,fetched_at)
            VALUES(:stock_id,:title,:publish_date,:source,:url,:query,CURRENT_TIMESTAMP)
        """, row)
        count += cur.rowcount
    conn.commit()
    return count


def upsert_financial_report(conn, row: dict) -> None:
    payload = {
        "stock_id": row.get("stock_id"),
        "symbol": row.get("symbol") or row.get("stock_id"),
        "company_name": row.get("company_name", ""),
        "year": row.get("year"),
        "period_end": row.get("period_end"),
        "period_type": row.get("period_type"),
        "currency": row.get("currency"),
        "revenue": row.get("revenue"),
        "operating_profit": row.get("operating_profit"),
        "net_profit": row.get("net_profit"),
        "eps": row.get("eps"),
        "total_assets": row.get("total_assets"),
        "total_liabilities": row.get("total_liabilities"),
        "equity": row.get("equity"),
        "operating_cashflow": row.get("operating_cashflow"),
        "source_type": row.get("source_type"),
        "source_url": row.get("source_url"),
    }
    conn.execute("""
        INSERT INTO financial_reports(
            stock_id,symbol,company_name,year,period_end,period_type,currency,
            revenue,operating_profit,net_profit,eps,total_assets,total_liabilities,
            equity,operating_cashflow,source_type,source_url,fetched_at
        ) VALUES (
            :stock_id,:symbol,:company_name,:year,:period_end,:period_type,:currency,
            :revenue,:operating_profit,:net_profit,:eps,:total_assets,:total_liabilities,
            :equity,:operating_cashflow,:source_type,:source_url,CURRENT_TIMESTAMP
        )
        ON CONFLICT(stock_id,period_end) DO UPDATE SET
            symbol=excluded.symbol,
            company_name=excluded.company_name,
            year=excluded.year,
            period_type=excluded.period_type,
            currency=excluded.currency,
            revenue=excluded.revenue,
            operating_profit=excluded.operating_profit,
            net_profit=excluded.net_profit,
            eps=excluded.eps,
            total_assets=excluded.total_assets,
            total_liabilities=excluded.total_liabilities,
            equity=excluded.equity,
            operating_cashflow=excluded.operating_cashflow,
            source_type=excluded.source_type,
            source_url=excluded.source_url,
            fetched_at=CURRENT_TIMESTAMP
    """, payload)
    conn.commit()

