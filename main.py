from __future__ import annotations
import argparse
import json
from company_intel.config import load_settings
from company_intel.services.collector import collect

def main():
    p = argparse.ArgumentParser(description="Company Intelligence crawler")
    p.add_argument("--company", required=True, help='例如 9904、寶成、或 "9904 寶成"')
    p.add_argument("--year", required=True, type=int)
    p.add_argument("--month", required=True, type=int, choices=range(1, 13))
    p.add_argument("--market", default="auto", choices=["auto", "sii", "otc"])
    p.add_argument("--keywords", default="", help="額外 Google News 關鍵字，以 | 分隔")
    p.add_argument("--db", default="data/company.db")
    p.add_argument("--no-revenue", action="store_true")
    p.add_argument("--no-news", action="store_true")
    p.add_argument("--news-months", type=int, default=3, help="新聞回溯月數，預設 3")
    args = p.parse_args()

    result = collect(
        company_input=args.company,
        year=args.year,
        month=args.month,
        db_path=args.db,
        market=args.market,
        news_keywords=args.keywords,
        fetch_revenue=not args.no_revenue,
        fetch_google_news=not args.no_news,
        news_months=max(1, args.news_months),
        settings=load_settings(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

if __name__ == "__main__":
    main()
