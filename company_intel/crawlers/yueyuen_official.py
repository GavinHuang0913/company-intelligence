from __future__ import annotations

from pathlib import Path
import re

from ..config import Settings

URL = "https://www.yueyuen.com/tc/reports_announcement.html#monthly_revenue"

TABLE_SELECTOR = "#monthly_revenue table.primary-table.type-1"


def _num(text: str | None):
    if text is None:
        return None
    s = str(text).strip().replace(",", "").replace("%", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    if s in {"", "-", "--"}:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _result(year: int, month: int, cells: list[str]) -> dict:
    """
    官網 row:
    月份
    綜合經營收益:
      單月營收 / 累計營收 / 單月同比 / 累計同比
    製造業務營收:
      單月同比 / 累計同比
    寶勝營收:
      單月同比 / 累計同比
    """
    if len(cells) < 5:
        raise RuntimeError(f"裕元官網 row 欄位不足: {cells}")

    revenue = _num(cells[1])
    accumulated = _num(cells[2])
    yoy = _num(cells[3])
    accumulated_yoy = _num(cells[4])

    if revenue is None:
        raise RuntimeError(f"裕元官網單月營收無法解析: {cells}")

    return {
        "stock_id": "0551",
        "symbol": "0551.HK",
        "year": int(year),
        "month": int(month),
        "company_name": "Yue Yuen Industrial (Holdings) Limited",
        "revenue": revenue * 1000,
        "previous_month_revenue": None,
        "revenue_last_year": None,
        "mom": None,
        "yoy": yoy,
        "accumulated_revenue": accumulated * 1000 if accumulated is not None else None,
        "accumulated_last_year": None,
        "accumulated_yoy": accumulated_yoy,
        "currency": "USD",
        "amount_unit": "USD",
        "note": (
            "Yue Yuen 官方網站 Monthly Revenue；"
            "原始金額 USD'000，DB 已換算成 USD 元。"
        ),
        "source_url": URL,
        "source_type": "yueyuen_official_ir_monthly",
        "data_quality": "complete",
    }


def _select_year(page, year: int) -> None:
    target = str(year)

    # 官網月營收區塊內優先找 select
    selects = page.locator("#monthly_revenue select")
    if selects.count() == 0:
        selects = page.locator("select")

    for i in range(selects.count()):
        sel = selects.nth(i)
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
            continue


def fetch_yueyuen_official_monthly_revenue(
    year: int,
    month: int,
    settings: Settings,
) -> dict:
    """
    Yue Yuen 官網對 requests / headless Chromium 會回 403。
    因此使用本機真正的 Google Chrome + headed + persistent profile。

    第一次執行時會開啟一個 Chrome 視窗。
    Profile 放在 data/yueyuen-chrome-profile，不碰使用者原本 Chrome profile。
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        raise RuntimeError("未安裝 playwright") from e

    profile_dir = Path("data") / "yueyuen-chrome-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir.resolve()),
                channel="chrome",
                headless=False,
                locale="zh-TW",
                viewport={"width": 1440, "height": 1000},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                ],
            )
        except Exception as e:
            raise RuntimeError(
                "無法啟動本機 Google Chrome。請確認 Chrome 已安裝；"
                "Playwright 會使用 channel='chrome'。"
            ) from e

        try:
            page = context.pages[0] if context.pages else context.new_page()

            # Hide the most obvious webdriver flag.
            page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                """
            )

            response = page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            page.wait_for_timeout(2500)

            status = response.status if response else None
            if status == 403 or "403 Forbidden" in page.locator("body").inner_text():
                raise RuntimeError(
                    "Google Chrome 仍收到 403；此網路/網站阻擋自動化 session"
                )

            # Exact DOM confirmed from DevTools.
            page.wait_for_selector(TABLE_SELECTOR, timeout=20000)

            _select_year(page, year)
            page.wait_for_timeout(1500)
            page.wait_for_selector(TABLE_SELECTOR, timeout=10000)

            rows = page.locator(f"{TABLE_SELECTOR} tbody tr")

            target = None
            for i in range(rows.count()):
                row = rows.nth(i)
                cells = [
                    " ".join((row.locator("th,td").nth(j).inner_text() or "").split())
                    for j in range(row.locator("th,td").count())
                ]

                if not cells:
                    continue

                try:
                    row_month = int(float(cells[0]))
                except Exception:
                    continue

                if row_month == int(month):
                    target = cells
                    break

            if target is None:
                raise LookupError(
                    f"Yue Yuen 官網已正常載入，但找不到 {year}/{month:02d} row"
                )

            return _result(year, month, target)

        finally:
            context.close()
