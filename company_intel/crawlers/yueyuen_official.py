from __future__ import annotations

from io import StringIO
from pathlib import Path
import re
import pandas as pd
import requests

from ..config import Settings

URL = "https://www.yueyuen.com/tc/reports_announcement.html#monthly_revenue"


def _num(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("%", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    if s in {"", "-", "--", "nan"}:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _result(
    year: int,
    month: int,
    revenue,
    accumulated_revenue,
    yoy,
    accumulated_yoy,
    source_note: str,
) -> dict:
    if revenue is None:
        raise RuntimeError("裕元官網單月營收無法解析")

    return {
        "stock_id": "0551",
        "symbol": "0551.HK",
        "year": int(year),
        "month": int(month),
        "company_name": "Yue Yuen Industrial (Holdings) Limited",
        # 官網原始金額為 USD'000，DB 保存 USD 元
        "revenue": float(revenue) * 1000,
        "previous_month_revenue": None,
        "revenue_last_year": None,
        "mom": None,
        "yoy": yoy,
        "accumulated_revenue": (
            float(accumulated_revenue) * 1000
            if accumulated_revenue is not None else None
        ),
        "accumulated_last_year": None,
        "accumulated_yoy": accumulated_yoy,
        "currency": "USD",
        "amount_unit": "USD",
        "note": (
            "Yue Yuen 官方網站月營收；"
            "綜合經營收益欄位；原始金額 USD'000，DB 已換算為 USD 元。"
            + source_note
        ),
        "source_url": URL,
        "source_type": "yueyuen_official_ir_monthly",
        "data_quality": "complete",
    }


def _try_static_html(year: int, month: int, settings: Settings) -> dict | None:
    """
    快速路徑。官網目前常對 requests 回 403，因此失敗時交給 Playwright。
    """
    r = requests.get(
        URL,
        headers={
            "User-Agent": settings.user_agent,
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.yueyuen.com/",
        },
        timeout=settings.request_timeout,
    )
    r.raise_for_status()

    try:
        tables = pd.read_html(StringIO(r.text))
    except Exception:
        return None

    # 若未來網站重新改回標準 table，可直接支援。
    for raw in tables:
        df = raw.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [
                " ".join(str(x).strip() for x in tup if str(x) != "nan")
                for tup in df.columns
            ]
        else:
            df.columns = [str(c).strip() for c in df.columns]

        all_text = " ".join(df.columns)
        if "單月營收" not in all_text or "累計營收" not in all_text:
            continue

        month_col = next(
            (c for c in df.columns if "月份" in str(c) or "Month" in str(c)),
            df.columns[0],
        )
        ms = pd.to_numeric(df[month_col], errors="coerce")
        rows = df[ms == int(month)]
        if rows.empty:
            continue

        row = rows.iloc[0]
        rev_cols = [c for c in df.columns if "單月營收" in str(c)]
        acc_cols = [c for c in df.columns if "累計營收" in str(c)]
        yoy_cols = [c for c in df.columns if "單月同比" in str(c)]
        acc_yoy_cols = [c for c in df.columns if "累計同比" in str(c)]

        return _result(
            year, month,
            _num(row[rev_cols[0]]) if rev_cols else None,
            _num(row[acc_cols[0]]) if acc_cols else None,
            _num(row[yoy_cols[0]]) if yoy_cols else None,
            _num(row[acc_yoy_cols[0]]) if acc_yoy_cols else None,
            "（static HTML）",
        )
    return None


def _select_year(page, year: int) -> None:
    """
    官網目前畫面上的年度是 native select。
    若未來改成自訂元件，也保留文字點擊 fallback。
    """
    target = str(year)

    for i in range(page.locator("select").count()):
        sel = page.locator("select").nth(i)
        try:
            options = sel.locator("option")
            labels = [
                (options.nth(j).inner_text() or "").strip()
                for j in range(options.count())
            ]
            if target in labels:
                sel.select_option(label=target)
                page.wait_for_timeout(1200)
                return
        except Exception:
            pass

    # custom dropdown fallback
    try:
        loc = page.get_by_text(target, exact=True)
        if loc.count():
            loc.first.click(timeout=2000)
            page.wait_for_timeout(800)
    except Exception:
        pass


def _find_rendered_row_text(page, month: int) -> str | None:
    """
    裕元官網月營收「看起來像表格」，但實際 DOM 是 div/grid，不是 <table>。
    從月份文字節點往上找最小 ancestor row：
    - 以月份開頭
    - 至少包含四個百分比
    - 至少有帶千分位的金額
    """
    month_text = str(int(month))
    candidates = page.get_by_text(month_text, exact=True)

    best = None

    for i in range(candidates.count()):
        node = candidates.nth(i)
        try:
            data = node.evaluate(
                """(el) => {
                    let cur = el;
                    const out = [];
                    for (let level = 0; cur && level < 8; level++, cur = cur.parentElement) {
                        const txt = (cur.innerText || '').trim();
                        if (txt) {
                            out.push({level, text: txt, tag: cur.tagName, cls: cur.className || ''});
                        }
                    }
                    return out;
                }"""
            )
        except Exception:
            continue

        for item in data:
            text = " ".join(str(item.get("text", "")).split())
            # row from screenshot:
            # 7 602,614 4,576,687 -9.7% -3.2% -10.0% -5.5% -13.9% -3.4%
            pct_count = len(re.findall(r"[-+]?\d+(?:\.\d+)?%", text))
            comma_nums = len(re.findall(r"\d{1,3}(?:,\d{3})+", text))
            if (
                re.match(rf"^{re.escape(month_text)}(?:\s|$)", text)
                and pct_count >= 4
                and comma_nums >= 2
            ):
                # Prefer the shortest matching ancestor = one rendered row.
                if best is None or len(text) < len(best):
                    best = text

    return best


def _parse_rendered_row(row_text: str, year: int, month: int) -> dict:
    """
    Rendered row column order from official site:
      月份
      綜合經營收益: 單月營收, 累計營收, 單月同比, 累計同比
      製造業務營收: 單月同比, 累計同比
      寶勝營收*:    單月同比, 累計同比

    We intentionally consume only the first 5 tokens.
    """
    tokens = re.findall(
        r"[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-+]?\d+(?:\.\d+)?%|[-+]?\d+(?:\.\d+)?",
        row_text,
    )

    if len(tokens) < 5:
        raise RuntimeError(f"裕元官網 row token 不足：{row_text}")

    parsed_month = int(float(tokens[0]))
    if parsed_month != int(month):
        raise RuntimeError(
            f"裕元官網 row 月份不符：expected={month}, actual={parsed_month}"
        )

    revenue = _num(tokens[1])
    accumulated = _num(tokens[2])
    yoy = _num(tokens[3])
    accumulated_yoy = _num(tokens[4])

    return _result(
        year,
        month,
        revenue,
        accumulated,
        yoy,
        accumulated_yoy,
        "（Playwright rendered DIV/grid）",
    )


def _browser_fetch(year: int, month: int) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        raise RuntimeError(
            "未安裝 Playwright；請使用專案 Python 安裝 playwright。"
        ) from e

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:
            raise RuntimeError(
                "Playwright Chromium 尚未安裝；"
                "請執行：.venv\\Scripts\\python.exe -m playwright install chromium"
            ) from e

        page = browser.new_page(
            locale="zh-TW",
            viewport={"width": 1440, "height": 1200},
        )

        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            _select_year(page, year)
            page.wait_for_timeout(1500)

            # 找到月營收 section，必要時捲動讓 lazy-render 元件出現。
            try:
                page.locator("#monthly_revenue").scroll_into_view_if_needed()
                page.wait_for_timeout(1000)
            except Exception:
                pass

            row_text = _find_rendered_row_text(page, month)

            if not row_text:
                # Debug artifact written locally for diagnosis.
                debug_dir = Path("data") / "debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                (debug_dir / "yueyuen_body.txt").write_text(
                    page.locator("body").inner_text(),
                    encoding="utf-8",
                )
                (debug_dir / "yueyuen_page.html").write_text(
                    page.content(),
                    encoding="utf-8",
                )
                raise RuntimeError(
                    "瀏覽器已載入官網，但找不到指定月份 rendered row；"
                    "已輸出 data/debug/yueyuen_body.txt 與 yueyuen_page.html"
                )

            return _parse_rendered_row(row_text, year, month)
        finally:
            browser.close()


def fetch_yueyuen_official_monthly_revenue(
    year: int,
    month: int,
    settings: Settings,
) -> dict:
    errors = []

    try:
        row = _try_static_html(year, month, settings)
        if row:
            return row
        errors.append("requests：HTML 無可解析資料")
    except Exception as e:
        errors.append(f"requests：{e}")

    try:
        return _browser_fetch(year, month)
    except Exception as e:
        errors.append(f"browser：{e}")

    raise RuntimeError("；".join(errors))
