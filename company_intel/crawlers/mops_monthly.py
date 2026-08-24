from __future__ import annotations
from io import StringIO
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from ..config import Settings

MODERN_URL = "https://mops.twse.com.tw/mops/web/t05st10_ifrs"
AJAX_URL = "https://mops.twse.com.tw/mops/web/ajax_t05st10_ifrs"
LEGACY_URL = "https://mops.twse.com.tw/nas/t21/{market}/t21sc03_{roc_year}_{month}.html"

def _headers(settings: Settings) -> dict:
    return {
        "User-Agent": settings.user_agent,
        "Referer": MODERN_URL,
        "Origin": "https://mops.twse.com.tw",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "close",
    }

def _payload(stock_id: str, year: int, month: int) -> dict:
    roc_year = year - 1911
    return {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "queryName": "co_id",
        "inputType": "co_id",
        "inpuType": "co_id",   # MOPS 某些版本使用這個拼法
        "TYPEK": "all",
        "isnew": "false",
        "co_id": str(stock_id),
        "year": str(roc_year),
        "month": f"{month:02d}",
    }

def _security_blocked(text: str) -> bool:
    upper = text.upper()
    return (
        "FOR SECURITY REASONS" in upper
        or "因為安全性考量" in text
        or "查詢過於頻繁" in text
    )

def _to_num(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("%", "")
    if s in {"", "-", "--", "nan", "None"}:
        return None
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return None


def _thousand_twd_to_twd(v):
    n = _to_num(v)
    return None if n is None else n * 1000

def _extract_by_label(html: str, labels: list[str]):
    soup = BeautifulSoup(html, "lxml")
    for label in labels:
        # 精確 th/td
        node = soup.find(
            lambda tag: tag.name in {"th", "td"} and tag.get_text(" ", strip=True) == label
        )
        if node:
            sib = node.find_next_sibling(["td", "th"])
            while sib:
                txt = sib.get_text(" ", strip=True)
                num = _to_num(txt)
                if num is not None:
                    return num
                sib = sib.find_next_sibling(["td", "th"])
        # 寬鬆 contains
        node = soup.find(
            lambda tag: tag.name in {"th", "td"} and label in tag.get_text(" ", strip=True)
        )
        if node:
            row = node.find_parent("tr")
            if row:
                vals = [x.get_text(" ", strip=True) for x in row.find_all(["th", "td"])]
                for txt in vals[1:]:
                    num = _to_num(txt)
                    if num is not None:
                        return num
    return None

def _extract_text_by_label(html: str, labels: list[str]) -> str:
    soup = BeautifulSoup(html, "lxml")
    for label in labels:
        node = soup.find(
            lambda tag: tag.name in {"th", "td"} and label in tag.get_text(" ", strip=True)
        )
        if node:
            row = node.find_parent("tr")
            if row:
                vals = [x.get_text(" ", strip=True) for x in row.find_all(["th", "td"])]
                if len(vals) >= 2:
                    return vals[-1].strip()
    return ""

def _parse_result(html: str, stock_id: str, year: int, month: int, source_url: str) -> dict:
    # 先確認頁面真的有營收相關欄位
    if not any(k in html for k in ["本月", "當月營收", "去年同期", "本年累計"]):
        raise RuntimeError("MOPS 回傳頁不是月營收結果頁")

    revenue = _extract_by_label(html, ["本月", "當月營收", "本月營業收入"])
    revenue_last_year = _extract_by_label(html, ["去年同期", "去年當月營收"])
    yoy = _extract_by_label(html, ["增減百分比", "去年同月增減(%)", "去年同月增減％"])
    accumulated_revenue = _extract_by_label(html, ["本年累計", "當月累計營收"])
    accumulated_last_year = _extract_by_label(html, ["去年累計", "去年累計營收"])
    accumulated_yoy = _extract_by_label(html, ["累計增減百分比", "前期比較增減(%)"])
    note = _extract_text_by_label(html, ["備註"])

    if revenue is None:
        # 最後才嘗試 pandas，避免版型差異。
        try:
            tables = pd.read_html(StringIO(html))
            for df in tables:
                txt = df.astype(str).to_string()
                if "本月" in txt or "當月營收" in txt:
                    # 不假設固定 table index；僅作診斷 fallback
                    for _, row in df.iterrows():
                        vals = [str(x).strip() for x in row.tolist()]
                        if vals and ("本月" in vals[0] or "當月營收" in vals[0]):
                            for cand in vals[1:]:
                                num = _to_num(cand)
                                if num is not None:
                                    revenue = num
                                    break
                        if revenue is not None:
                            break
                if revenue is not None:
                    break
        except Exception:
            pass

    if revenue is None:
        raise RuntimeError("MOPS 已回傳結果頁，但無法解析「本月營收」")

    return {
        "stock_id": str(stock_id),
        "year": int(year),
        "month": int(month),
        "company_name": "",
        "revenue": None if revenue is None else revenue * 1000,
        "revenue_last_year": None if revenue_last_year is None else revenue_last_year * 1000,
        "yoy": yoy,
        "accumulated_revenue": None if accumulated_revenue is None else accumulated_revenue * 1000,
        "accumulated_last_year": None if accumulated_last_year is None else accumulated_last_year * 1000,
        "accumulated_yoy": accumulated_yoy,
        "note": note,
        "source_url": source_url,
        "source_type": "mops",
        "currency": "TWD",
        "amount_unit": "TWD",
        "unit": "TWD",
    }

def _post_and_parse(url: str, stock_id: str, year: int, month: int, settings: Settings):
    s = requests.Session()
    # 先 GET 一次建立 cookie/session，再 POST 查詢。
    s.get(MODERN_URL, headers=_headers(settings), timeout=settings.request_timeout)
    r = s.post(
        url,
        data=_payload(stock_id, year, month),
        headers=_headers(settings),
        timeout=settings.request_timeout,
    )
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() in {"iso-8859-1", "latin-1"}:
        r.encoding = "utf-8"
    if _security_blocked(r.text):
        raise RuntimeError("MOPS 查詢被安全機制阻擋")
    return _parse_result(r.text, stock_id, year, month, r.url)

def _fetch_legacy(stock_id: str, year: int, month: int, settings: Settings, market: str) -> dict:
    roc_year = year - 1911
    url = LEGACY_URL.format(market=market, roc_year=roc_year, month=month)
    r = requests.get(url, headers=_headers(settings), timeout=settings.request_timeout)
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() in {"iso-8859-1", "latin-1"}:
        r.encoding = "cp950"
    if _security_blocked(r.text):
        raise RuntimeError("MOPS legacy 查詢被安全機制阻擋")

    tables = pd.read_html(StringIO(r.text))
    for df in tables:
        cols = [re.sub(r"\s+", "", str(c)) for c in df.columns]
        if not (any("公司代號" in c for c in cols) and any("當月營收" in c for c in cols)):
            continue
        df = df.copy()
        df.columns = cols
        code_col = next(c for c in df.columns if "公司代號" in c)
        rows = df[df[code_col].astype(str).str.strip() == str(stock_id)]
        if rows.empty:
            continue
        raw = rows.iloc[0].to_dict()

        def pick(fragment):
            key = next((k for k in raw if fragment in k), None)
            return _to_num(raw.get(key)) if key else None

        return {
            "stock_id": str(stock_id),
            "year": int(year),
            "month": int(month),
            "company_name": str(raw.get(next((k for k in raw if "公司名稱" in k), ""), "")).strip(),
            "revenue": None if pick("當月營收") is None else pick("當月營收") * 1000,
            "revenue_last_year": None if pick("去年當月營收") is None else pick("去年當月營收") * 1000,
            "yoy": pick("去年同月增減"),
            "accumulated_revenue": None if pick("當月累計營收") is None else pick("當月累計營收") * 1000,
            "accumulated_last_year": None if pick("去年累計營收") is None else pick("去年累計營收") * 1000,
            "accumulated_yoy": pick("前期比較增減"),
            "note": "",
            "source_url": url,
            "source_type": "mops",
            "currency": "TWD",
            "amount_unit": "TWD",
            "unit": "TWD",
        }

    raise RuntimeError("legacy 頁找不到指定公司月營收")

def fetch_monthly_revenue(stock_id: str, year: int, month: int, settings: Settings, market: str = "sii") -> dict:
    if not 1 <= int(month) <= 12:
        raise ValueError("month 必須是 1~12")
    if year <= 1911:
        raise ValueError("year 請使用西元，例如 2026")

    errors = []

    # 1) MOPS 正式頁 POST
    try:
        return _post_and_parse(MODERN_URL, stock_id, year, month, settings)
    except Exception as e:
        errors.append(f"POST t05st10_ifrs：{e}")

    # 2) AJAX POST
    try:
        return _post_and_parse(AJAX_URL, stock_id, year, month, settings)
    except Exception as e:
        errors.append(f"POST ajax_t05st10_ifrs：{e}")

    # 3) 舊靜態頁最後 fallback
    try:
        return _fetch_legacy(stock_id, year, month, settings, market)
    except Exception as e:
        errors.append(f"legacy：{e}")

    raise RuntimeError("；".join(errors))
