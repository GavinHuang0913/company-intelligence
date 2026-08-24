from company_intel.crawlers.finmind import _pct

def test_pct():
    assert round(_pct(110, 100), 2) == 10.00
    assert _pct(100, 0) is None
