from scripts.kpi_summary import summarize


def test_summarize_groups_store_and_date():
    result = summarize(
        [
            {"store": "A", "date": "2026-09-01", "amount": "10.50"},
            {"store": "A", "date": "2026-09-01", "amount": "2.00"},
            {"store": "B", "date": "2026-09-02", "amount": "7.50"},
            {"store": "B", "date": "2026-09-02", "amount": "bad"},
        ],
        source="fixture.csv",
    )

    assert result["summary"]["row_count"] == 4
    assert result["summary"]["valid_amount_rows"] == 3
    assert result["summary"]["amount_error_rows"] == 1
    assert result["summary"]["total_amount"] == "20.00"
    assert result["summary"]["average_amount"] == "6.67"
    assert result["by_store"][0] == {
        "store": "A", "order_count": 2, "total_amount": "12.50"
    }
    assert result["by_date"][0]["date"] == "2026-09-01"
