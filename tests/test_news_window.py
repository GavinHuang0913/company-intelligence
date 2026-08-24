from company_intel.crawlers.google_news import news_window, build_query

def test_news_window_3_months():
    start, end = news_window(2026, 7, 3)
    assert start.isoformat() == "2026-05-01"
    assert end.isoformat() == "2026-07-31"

def test_news_query():
    q = build_query(["寶成"], 2026, 7, 3)
    assert "after:2026-05-01" in q
    assert "before:2026-08-01" in q
