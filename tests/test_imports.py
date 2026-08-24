def test_imports():
    from company_intel.config import Settings
    from company_intel.crawlers.google_news import build_query
    q = build_query(["寶成", "Pou Chen"], 2026, 7)
    assert "after:2026-07-01" in q
    assert "before:2026-08-01" in q
