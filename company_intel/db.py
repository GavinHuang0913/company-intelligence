from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Iterable

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS companies (
    stock_id TEXT PRIMARY KEY,
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
    revenue_last_year REAL,
    yoy REAL,
    accumulated_revenue REAL,
    accumulated_last_year REAL,
    accumulated_yoy REAL,
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

CREATE INDEX IF NOT EXISTS idx_news_stock_date
ON news(stock_id, publish_date);
"""

def connect(db_path: str = "data/company.db") -> sqlite3.Connection:
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn

def upsert_company(conn, company: dict) -> None:
    conn.execute("""
        INSERT INTO companies(stock_id, company_name, short_name, market, industry, news_keywords, updated_at)
        VALUES(:stock_id,:company_name,:short_name,:market,:industry,:news_keywords,CURRENT_TIMESTAMP)
        ON CONFLICT(stock_id) DO UPDATE SET
            company_name=excluded.company_name,
            short_name=excluded.short_name,
            market=excluded.market,
            industry=excluded.industry,
            news_keywords=excluded.news_keywords,
            updated_at=CURRENT_TIMESTAMP
    """, company)
    conn.commit()

def upsert_revenue(conn, row: dict) -> None:
    conn.execute("""
        INSERT INTO monthly_revenue(
            stock_id,year,month,company_name,revenue,revenue_last_year,yoy,
            accumulated_revenue,accumulated_last_year,accumulated_yoy,note,source_url,fetched_at
        ) VALUES (
            :stock_id,:year,:month,:company_name,:revenue,:revenue_last_year,:yoy,
            :accumulated_revenue,:accumulated_last_year,:accumulated_yoy,:note,:source_url,CURRENT_TIMESTAMP
        )
        ON CONFLICT(stock_id,year,month) DO UPDATE SET
            company_name=excluded.company_name,
            revenue=excluded.revenue,
            revenue_last_year=excluded.revenue_last_year,
            yoy=excluded.yoy,
            accumulated_revenue=excluded.accumulated_revenue,
            accumulated_last_year=excluded.accumulated_last_year,
            accumulated_yoy=excluded.accumulated_yoy,
            note=excluded.note,
            source_url=excluded.source_url,
            fetched_at=CURRENT_TIMESTAMP
    """, row)
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
