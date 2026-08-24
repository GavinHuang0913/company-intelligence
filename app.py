from __future__ import annotations

from datetime import date
import pandas as pd
import streamlit as st

from company_intel.config import load_settings
from company_intel.db import connect
from company_intel.services.collector import collect


DB_PATH = "data/company.db"

DISPLAY_UNITS = {
    "元": {"divisor": 1, "decimals": 0},
    "千元": {"divisor": 1_000, "decimals": 0},
    "百萬元": {"divisor": 1_000_000, "decimals": 2},
    "億元": {"divisor": 100_000_000, "decimals": 2},
}


COMPANY_OPTIONS_PATH = "data/company_options.json"

DEFAULT_COMPANY_OPTIONS = [
    {"label": "寶成 9904.TW", "value": "9904.TW"},
    {"label": "九興 1836.HK", "value": "1836.HK"},
    {"label": "華利集團 300979.SZ", "value": "300979.SZ"},
    {"label": "寶勝 3813.HK", "value": "3813.HK"},
    {"label": "裕元 0551.HK", "value": "0551.HK"},
]


def _load_company_options() -> list[dict]:
    from pathlib import Path
    import json

    path = Path(COMPANY_OPTIONS_PATH)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(DEFAULT_COMPANY_OPTIONS, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return list(DEFAULT_COMPANY_OPTIONS)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            return data
    except Exception:
        pass

    return list(DEFAULT_COMPANY_OPTIONS)


def _save_company_options(options: list[dict]) -> None:
    from pathlib import Path
    import json

    path = Path(COMPANY_OPTIONS_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(options, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _display_amount(value, display_unit: str) -> str:
    """SQLite 保存各公司原始幣別的「元」；僅在畫面上換算顯示單位。"""
    if value is None or pd.isna(value):
        return "-"
    cfg = DISPLAY_UNITS[display_unit]
    amount = float(value) / cfg["divisor"]
    return f'{amount:,.{cfg["decimals"]}f}'


def _display_amount_with_unit(value, display_unit: str) -> str:
    value_text = _display_amount(value, display_unit)
    return "-" if value_text == "-" else f"{value_text} {display_unit}"


st.set_page_config(page_title="Company Intelligence", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stMetricValue"] {
        font-size: 1.85rem !important;
        line-height: 1.2 !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.92rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("公司財務與新聞情報")
st.caption("TW / HK / CN 公司財務 + Google News RSS + SQLite")


def _company_filter_value(company_input: str, result: dict | None) -> tuple[str | None, str]:
    """
    優先使用本次查詢已解析出的 stock_id。
    若尚未執行查詢，則從輸入框嘗試取股票代號；否則用名稱 LIKE 搜尋。
    """
    if result and result.get("company"):
        comp = result["company"]
        return str(comp.get("stock_id") or "").strip() or None, str(
            comp.get("short_name") or comp.get("company_name") or ""
        ).strip()

    raw = company_input.strip()
    if not raw:
        return None, ""

    first = raw.split(maxsplit=1)[0]
    if first.isdigit():
        return first, raw.split(maxsplit=1)[1] if len(raw.split(maxsplit=1)) > 1 else ""

    return None, raw


def _load_history(
    company_input: str,
    result: dict | None,
    year: int,
    month: int,
    scope: str,
    limit: int,
) -> pd.DataFrame:
    stock_id, company_keyword = _company_filter_value(company_input, result)

    where = []
    params: list[object] = []

    company_scoped = scope in {
        "同公司 + 同年月",
        "同公司 + 同年度",
        "同公司全部",
    }

    if company_scoped:
        if stock_id:
            where.append("stock_id = ?")
            params.append(stock_id)
        elif company_keyword:
            where.append("(company_name LIKE ? OR stock_id LIKE ?)")
            like = f"%{company_keyword}%"
            params.extend([like, like])

    if scope == "同公司 + 同年月":
        where.append("year = ?")
        where.append("month = ?")
        params.extend([int(year), int(month)])

    elif scope == "所有公司 + 同年月":
        where.append("year = ?")
        where.append("month = ?")
        params.extend([int(year), int(month)])

    elif scope == "同公司 + 同年度":
        where.append("year = ?")
        params.append(int(year))

    elif scope == "同公司全部":
        pass

    elif scope == "全部資料":
        pass

    sql = """
        SELECT
            stock_id,
            COALESCE(symbol, stock_id) AS symbol,
            company_name,
            year,
            month,
            currency,
            revenue,
            previous_month_revenue,
            mom,
            revenue_last_year,
            yoy,
            accumulated_revenue,
            accumulated_last_year,
            accumulated_yoy,
            source_type,
            fetched_at
        FROM monthly_revenue
    """
    if where:
        sql += " WHERE " + " AND ".join(where)

    sql += " ORDER BY year DESC, month DESC, fetched_at DESC LIMIT ?"
    params.append(int(limit))

    conn = connect(DB_PATH)
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def _format_history(df: pd.DataFrame, display_unit: str) -> pd.DataFrame:
    display_df = df.copy()

    money_cols = [
        "revenue",
        "previous_month_revenue",
        "revenue_last_year",
        "accumulated_revenue",
        "accumulated_last_year",
    ]
    for col in money_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(
                lambda v: _display_amount(v, display_unit)
            )

    pct_cols = ["mom", "yoy", "accumulated_yoy"]
    for col in pct_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(
                lambda v: "-" if pd.isna(v) else f"{v:,.2f}%"
            )

    return display_df


with st.sidebar:
    st.header("查詢條件")

    display_unit = st.selectbox(
        "顯示單位",
        ["元", "千元", "百萬元", "億元"],
        index=1,
        help="只影響畫面顯示；SQLite 保存各公司原始幣別的元。",
    )

    company_options = _load_company_options()

    option_labels = [x["label"] for x in company_options]
    selected_label = st.selectbox(
        "公司 / 股票代號",
        option_labels,
        index=0,
    )
    company = next(
        x["value"] for x in company_options
        if x["label"] == selected_label
    )

    with st.expander("＋ 新增公司到選項清單"):
        new_label = st.text_input(
            "顯示名稱",
            placeholder="例如：志強 6768.TW",
            key="new_company_label",
        )
        new_value = st.text_input(
            "查詢代號 / 名稱",
            placeholder="例如：6768.TW",
            key="new_company_value",
        )
        add_company = st.button(
            "加入公司清單",
            use_container_width=True,
            key="add_company_option",
        )

        if add_company:
            label = new_label.strip()
            value = new_value.strip()

            if not label or not value:
                st.warning("請同時輸入顯示名稱與查詢代號。")
            elif any(
                x["value"].lower() == value.lower()
                for x in company_options
            ):
                st.info("這個公司已經在清單內。")
            else:
                company_options.append({
                    "label": label,
                    "value": value,
                })
                _save_company_options(company_options)
                st.success(f"已加入：{label}")
                st.rerun()

    c1, c2 = st.columns(2)
    year = c1.number_input(
        "年份",
        min_value=2005,
        max_value=2100,
        value=date.today().year,
        step=1,
    )
    month = c2.number_input(
        "月份",
        min_value=1,
        max_value=12,
        value=date.today().month,
        step=1,
    )

    market = st.selectbox(
        "市場",
        ["auto", "sii", "otc"],
        format_func=lambda x: {
            "auto": "自動",
            "sii": "上市",
            "otc": "上櫃",
        }[x],
    )

    keywords = st.text_input(
        "額外新聞關鍵字",
        value="",
        help="例如 Nike|adidas|越南|印尼",
    )

    use_revenue = st.checkbox("抓取月營收", value=True)
    use_news = st.checkbox("抓取 Google News", value=True)

    news_months = st.selectbox(
        "新聞期間",
        [1, 3, 6, 12],
        index=1,
        format_func=lambda x: f"截止所選月份往前 {x} 個月",
    )

    run = st.button(
        "開始抓取",
        type="primary",
        use_container_width=True,
    )

    st.divider()
    st.subheader("歷史資料篩選")

    history_scope = st.selectbox(
        "歷史資料範圍",
        [
            "同公司 + 同年月",
            "所有公司 + 同年月",
            "同公司 + 同年度",
            "同公司全部",
            "全部資料",
        ],
        index=0,
        help="預設完全套用上方公司、年份、月份查詢條件。",
    )

    history_limit = st.selectbox(
        "最多顯示筆數",
        [50, 100, 200, 500, 1000],
        index=1,
    )


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
            news_months=int(news_months),
            settings=load_settings(),
        )
        st.session_state["last_result"] = result

result = st.session_state.get("last_result")

tab_query, tab_history = st.tabs(["📊 查詢結果", "🗄️ 歷史資料庫"])


# -------------------------------------------------------------------------
# Tab 1 - Query result
# -------------------------------------------------------------------------
with tab_query:
    if not result:
        st.info("請從左側設定公司與年月後，按「開始抓取」。")
    else:
        comp = result["company"]

        st.subheader(
            f'{comp.get("short_name") or comp.get("company_name")} '
            f'({comp.get("symbol") or comp["stock_id"]})'
        )
        st.caption(
            f'市場：{comp.get("market","")}　'
            f'交易所：{comp.get("exchange","")}　'
            f'幣別：{comp.get("currency","")}　'
            f'產業：{comp.get("industry","")}　'
            f'查詢年月：{int(year)}/{int(month):02d}'
        )

        if result.get("warnings"):
            for w in result["warnings"]:
                st.info(w)

        if result.get("errors"):
            for e in result["errors"]:
                st.warning(e)

        rev = result.get("revenue")

        if rev:
            st.markdown("### 月營收")

            currency = rev.get("currency") or "TWD"
            unit = rev.get("amount_unit") or rev.get("unit") or "TWD"
            unit_label = "元" if unit == "TWD" else unit

            a, b, c, d = st.columns(4)
            a.metric(
                "當月營收",
                _display_amount_with_unit(rev.get("revenue"), display_unit),
            )
            b.metric(
                "MoM",
                f'{rev.get("mom"):.2f}%'
                if rev.get("mom") is not None
                else "-",
            )
            c.metric(
                "YoY",
                f'{rev.get("yoy"):.2f}%'
                if rev.get("yoy") is not None
                else "-",
            )
            d.metric(
                "去年同月",
                _display_amount_with_unit(rev.get("revenue_last_year"), display_unit),
            )

            e, f, g, h = st.columns(4)
            e.metric(
                "上月營收",
                _display_amount_with_unit(rev.get("previous_month_revenue"), display_unit),
            )
            f.metric(
                "累計營收",
                _display_amount_with_unit(rev.get("accumulated_revenue"), display_unit),
            )
            g.metric(
                "去年同期累計",
                _display_amount_with_unit(rev.get("accumulated_last_year"), display_unit),
            )
            h.metric(
                "累計 YoY",
                f'{rev.get("accumulated_yoy"):.2f}%'
                if rev.get("accumulated_yoy") is not None
                else "-",
            )

            st.caption(
                f'資料來源：'
                f'{result.get("revenue_source") or rev.get("source_type","未知")}；'
                f'幣別：{currency}；'
                f'顯示單位：{display_unit}（DB 儲存：{currency} 元）'
            )

            quality = rev.get("data_quality")
            if quality == "partial":
                st.warning(
                    "此月份為部分資料：僅顯示來源可以可靠取得的欄位，"
                    "未提供的欄位不推估。"
                )

            if rev.get("note"):
                st.info(rev["note"])

            if rev.get("source_url"):
                st.markdown(
                    f'來源：[{rev["source_url"]}]({rev["source_url"]})'
                )
        else:
            st.info("本次沒有取得月營收資料。")

        fin = result.get("financial_report")
        if fin:
            st.markdown("### 最新可取得財報")
            st.caption(
                f'代號：{fin.get("symbol") or comp.get("symbol")}｜'
                f'報告期：{fin.get("period_end")}｜'
                f'類型：{fin.get("period_type")}｜'
                f'幣別：{fin.get("currency")}｜'
                f'來源：{result.get("financial_source") or fin.get("source_type")}'
            )
            a, b, c, d = st.columns(4)
            a.metric("營業收入", _display_amount_with_unit(fin.get("revenue"), display_unit))
            b.metric("營業利益", _display_amount_with_unit(fin.get("operating_profit"), display_unit))
            c.metric("淨利", _display_amount_with_unit(fin.get("net_profit"), display_unit))
            d.metric("EPS", f'{fin.get("eps"):,.2f}' if fin.get("eps") is not None else "-")

            e, f, g, h = st.columns(4)
            e.metric("總資產", _display_amount_with_unit(fin.get("total_assets"), display_unit))
            f.metric("總負債", _display_amount_with_unit(fin.get("total_liabilities"), display_unit))
            g.metric("股東權益", _display_amount_with_unit(fin.get("equity"), display_unit))
            h.metric("營業現金流", _display_amount_with_unit(fin.get("operating_cashflow"), display_unit))
            if fin.get("source_url"):
                st.markdown(f'來源：[{fin["source_url"]}]({fin["source_url"]})')

        if not rev and not fin:
            st.warning("本次沒有取得任何財務資料。")

        st.divider()

        news = result.get("news", [])
        st.markdown(
            f"### Google News（最近 {result.get('news_months', 3)} 個月）"
        )

        if news:
            sort_order = st.radio(
                "新聞排序",
                ["最新 → 最舊", "最舊 → 最新"],
                horizontal=True,
                key="news_sort_order",
            )

            df = pd.DataFrame(news)
            df["publish_date"] = pd.to_datetime(
                df["publish_date"],
                errors="coerce",
            )
            df = df.sort_values(
                "publish_date",
                ascending=(sort_order == "最舊 → 最新"),
                na_position="last",
            )
            df["publish_date"] = df["publish_date"].dt.strftime("%Y-%m-%d")

            show = df[
                ["publish_date", "source", "title", "url"]
            ].copy()

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


# -------------------------------------------------------------------------
# Tab 2 - History database
# -------------------------------------------------------------------------
with tab_history:
    st.subheader("歷史月營收資料庫")

    scope_text = {
        "同公司 + 同年月":
            f"公司：{company}｜年月：{int(year)}/{int(month):02d}",
        "所有公司 + 同年月":
            f"所有公司｜年月：{int(year)}/{int(month):02d}",
        "同公司 + 同年度":
            f"公司：{company}｜年度：{int(year)}",
        "同公司全部":
            f"公司：{company}｜全部月份",
        "全部資料":
            "全部公司 / 全部年月",
    }[history_scope]

    st.caption(
        f"目前歷史篩選：{scope_text}；顯示單位：{display_unit}。"
        " 左側修改查詢條件或顯示單位後，這裡會同步重新呈現。"
    )

    try:
        history_df = _load_history(
            company_input=company,
            result=result,
            year=int(year),
            month=int(month),
            scope=history_scope,
            limit=int(history_limit),
        )

        if history_df.empty:
            st.info("目前條件下沒有歷史資料。")
        else:
            # Summary
            c1, c2, c3 = st.columns(3)
            c1.metric("資料筆數", f"{len(history_df):,}")

            min_period = (
                history_df[["year", "month"]]
                .sort_values(["year", "month"])
                .iloc[0]
            )
            max_period = (
                history_df[["year", "month"]]
                .sort_values(["year", "month"])
                .iloc[-1]
            )

            c2.metric(
                "最早月份",
                f'{int(min_period["year"])}/{int(min_period["month"]):02d}',
            )
            c3.metric(
                "最新月份",
                f'{int(max_period["year"])}/{int(max_period["month"]):02d}',
            )

            display_df = _format_history(history_df, display_unit)

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "stock_id": "原始代號",
                    "symbol": "股票代號",
                    "company_name": "公司",
                    "year": "年",
                    "month": "月",
                    "currency": "幣別",
                    "revenue": f"當月營收（{display_unit}）",
                    "previous_month_revenue": f"上月營收（{display_unit}）",
                    "mom": "MoM",
                    "revenue_last_year": f"去年同月（{display_unit}）",
                    "yoy": "YoY",
                    "accumulated_revenue": f"累計營收（{display_unit}）",
                    "accumulated_last_year": f"去年同期累計（{display_unit}）",
                    "accumulated_yoy": "累計 YoY",
                    "source_type": "資料來源",
                    "fetched_at": "更新時間",
                },
            )

    except Exception as exc:
        st.error(f"讀取歷史資料失敗：{exc}")

    st.divider()
    st.subheader("歷史財報")
    try:
        stock_id, _ = _company_filter_value(company, result)
        conn = connect(DB_PATH)
        if stock_id:
            fin_df = pd.read_sql_query(
                """
                SELECT stock_id,COALESCE(symbol,stock_id) AS symbol,company_name,year,period_end,period_type,currency,
                       revenue,operating_profit,net_profit,eps,total_assets,
                       total_liabilities,equity,operating_cashflow,source_type,fetched_at
                FROM financial_reports
                WHERE stock_id=?
                ORDER BY period_end DESC
                LIMIT ?
                """,
                conn,
                params=[stock_id, int(history_limit)],
            )
        else:
            fin_df = pd.read_sql_query(
                """
                SELECT stock_id,COALESCE(symbol,stock_id) AS symbol,company_name,year,period_end,period_type,currency,
                       revenue,operating_profit,net_profit,eps,total_assets,
                       total_liabilities,equity,operating_cashflow,source_type,fetched_at
                FROM financial_reports
                ORDER BY period_end DESC
                LIMIT ?
                """,
                conn,
                params=[int(history_limit)],
            )
        conn.close()

        if fin_df.empty:
            st.caption("目前沒有歷史財報資料。")
        else:
            for col in ["revenue","operating_profit","net_profit","total_assets","total_liabilities","equity","operating_cashflow"]:
                fin_df[col] = fin_df[col].apply(lambda v: _display_amount(v, display_unit))
            st.dataframe(fin_df, use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error(f"讀取歷史財報失敗：{exc}")
