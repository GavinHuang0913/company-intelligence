from pathlib import Path

def test_mops_does_not_use_apparent_encoding():
    src = Path("company_intel/crawlers/mops_monthly.py").read_text(encoding="utf-8")
    assert ".apparent_encoding" not in src
