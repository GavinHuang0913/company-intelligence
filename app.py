from __future__ import annotations
from datetime import date
import sqlite3
import pandas as pd
import streamlit as st

from company_intel.config import load_settings
from company_intel.services.collector import collect

st.set_page_config(page_title="Company Intelligence", layout="wide")
st.title("公司財務與新聞情報")
st.caption("MOPS 月營收 + Google News RSS + SQLite")

with st.sidebar:
    st.header("查詢條件")
    company = st.text_input("公司 / 股票代號", value="9904 寶成")
    c1, c2 = st.columns(2)
    year = c1.number_input("年份", min_value=2005, max_value=2100, value=date.today().year, step=1)
    month = c2.number_input("月份", min_value=1, max_value=12, value=date.today().month, step=1)
    market = st.selectbox(
        "市場",
        ["auto", "sii", "otc"],
        format_func=lambda x: {"auto": "自動", "sii": "上市", "otc": "上櫃"}[x],
    )
    keywords = st.text_input("額外新聞關鍵字", value="", help="例如 Nike|adidas|越南|印尼")
    use_revenue = st.checkbox("抓取月營收", value=True)
    use_news = st.checkbox("抓取 Google News", value=True)
    run = st.button("開始抓取", type="primary", use_container_width=True)

if run:
    with st.spinner("抓取資料中..."):
        result = collect(
            company_input=company,
            year=int(year),
            month=int(month),
            market=market,
            news_keywords=keywords,
            fetch_revenue=use_revenue,
            fetch_google_news=use_news,
            settings=load_settings(),
        )
        st.session_state["last_result"] = result

result = st.session_state.get("last_result")

if result:
    comp = result["company"]
    st.subheader(f'{comp.get("short_name") or comp.get("company_name")} ({comp["stock_id"]})')
    st.caption(f'市場：{comp.get("market","")}　產業：{comp.get("industry","")}')

    if result["errors"]:
        for e in result["errors"]:
            st.warning(e)

    rev = result.get("revenue")
    if rev:
        st.markdown("### 月營收")
        a, b, c, d = st.columns(4)
        a.metric("當月營收", f'{rev["revenue"]:,.0f}' if rev["revenue"] is not None else "-")
        b.metric("YoY", f'{rev["yoy"]:.2f}%' if rev["yoy"] is not None else "-")
        c.metric("累計營收", f'{rev["accumulated_revenue"]:,.0f}' if rev["accumulated_revenue"] is not None else "-")
        d.metric("累計 YoY", f'{rev["accumulated_yoy"]:.2f}%' if rev["accumulated_yoy"] is not None else "-")
        st.caption("MOPS 月營收原始單位通常為新台幣仟元；請以來源頁欄位說明為準。")
        if rev.get("note"):
            st.info(rev["note"])
        st.markdown(f'來源：[{rev["source_url"]}]({rev["source_url"]})')

    news = result.get("news", [])
    st.markdown("### Google News")
    if news:
        df = pd.DataFrame(news)
        show = df[["publish_date", "source", "title", "url"]].copy()
        st.dataframe(
            show,
            use_container_width=True,
            hide_index=True,
            column_config={
                "publish_date": "日期",
                "source": "來源",
                "title": "標題",
                "url": st.column_config.LinkColumn("新聞"),
            },
        )
    else:
        st.info("目前沒有抓到新聞。")

st.divider()
st.markdown("### 歷史資料庫")
try:
    conn = sqlite3.connect("data/company.db")
    revenue_df = pd.read_sql_query(
        "SELECT stock_id,company_name,year,month,revenue,yoy,accumulated_revenue,accumulated_yoy,fetched_at "
        "FROM monthly_revenue ORDER BY year DESC, month DESC LIMIT 100",
        conn,
    )
    conn.close()
    if not revenue_df.empty:
        st.dataframe(revenue_df, use_container_width=True, hide_index=True)
    else:
        st.caption("尚無資料")
except Exception:
    st.caption("尚未建立資料庫")
