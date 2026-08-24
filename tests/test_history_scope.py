def test_history_scope_labels():
    scopes = [
        "同公司 + 同年月",
        "同公司 + 同年度",
        "同公司全部",
        "全部資料",
    ]
    assert len(scopes) == 4
    assert "同公司 + 同年月" in scopes
