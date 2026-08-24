def test_sort_strings_iso_date_desc():
    rows = [
        {"publish_date": "2026-04-01"},
        {"publish_date": "2026-06-10"},
        {"publish_date": "2026-05-02"},
    ]
    rows.sort(key=lambda x: x["publish_date"], reverse=True)
    assert [x["publish_date"] for x in rows] == ["2026-06-10","2026-05-02","2026-04-01"]
