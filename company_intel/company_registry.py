from __future__ import annotations

INTERNATIONAL_COMPANIES = [
    {
        "stock_id": "1836",
        "symbol": "1836.HK",
        "company_name": "Stella International Holdings Limited",
        "short_name": "九興",
        "market": "HK",
        "exchange": "HKEX",
        "industry": "Footwear Manufacturing",
        "currency": "USD",
        "aliases": [
            "九興", "九兴", "九興控股", "九兴控股", "九興／製造", "九興/製造",
            "1836", "1836.HK", "Stella", "Stella International"
        ],
        "news_keywords": ["九興", "九兴", "Stella International", "1836"],
        "data_profile": "hk_financial",
        "official_url": "https://www.stella.com.hk/zh-hant/publications",
    },
    {
        "stock_id": "300979",
        "symbol": "300979.SZ",
        "company_name": "中山华利实业集团股份有限公司",
        "short_name": "華利集團",
        "market": "CN-SZ",
        "exchange": "SZSE",
        "industry": "Footwear Manufacturing",
        "currency": "CNY",
        "aliases": [
            "華利", "华利", "華利集團", "华利集团",
            "300979", "300979.SZ"
        ],
        "news_keywords": ["華利集團", "华利集团", "300979"],
        "data_profile": "cn_financial",
        "official_url": "http://www.huali-group.com/",
    },
    {
        "stock_id": "3813",
        "symbol": "3813.HK",
        "company_name": "Pou Sheng International (Holdings) Limited",
        "short_name": "寶勝",
        "market": "HK",
        "exchange": "HKEX",
        "industry": "Sports Retail",
        "currency": "CNY",
        "aliases": [
            "寶勝", "宝胜", "寶勝國際", "宝胜国际",
            "3813", "03813", "3813.HK", "03813.HK", "Pou Sheng"
        ],
        "news_keywords": ["寶勝", "寶勝國際", "宝胜国际", "Pou Sheng", "3813"],
        "data_profile": "hk_pousheng",
        "official_url": "https://en.pousheng.com/cn/Revenue.html",
    },
    {
        "stock_id": "0551",
        "symbol": "0551.HK",
        "company_name": "Yue Yuen Industrial (Holdings) Limited",
        "short_name": "裕元",
        "market": "HK",
        "exchange": "HKEX",
        "industry": "Footwear Manufacturing",
        "currency": "USD",
        "aliases": [
            "裕元", "裕元工業", "裕元工业", "Yue Yuen",
            "551", "0551", "00551", "0551.HK", "00551.HK"
        ],
        "news_keywords": ["裕元", "裕元工業", "Yue Yuen", "0551"],
        "data_profile": "hk_yueyuen",
        "official_url": "https://www.yueyuen.com/tc/reports_announcement.html#monthly_revenue",
    },
]

def resolve_international(keyword: str) -> dict | None:
    key = keyword.strip().lower()
    if not key:
        return None

    # exact first
    for item in INTERNATIONAL_COMPANIES:
        values = [
            item["stock_id"], item["symbol"], item["company_name"],
            item["short_name"], *item.get("aliases", [])
        ]
        if key in [str(v).lower() for v in values]:
            return dict(item)

    # contains
    for item in INTERNATIONAL_COMPANIES:
        values = [
            item["stock_id"], item["symbol"], item["company_name"],
            item["short_name"], *item.get("aliases", [])
        ]
        if any(key in str(v).lower() for v in values):
            return dict(item)

    return None
