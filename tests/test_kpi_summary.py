import json

import pytest

from scripts.kpi_summary import main, summarize, summarize_csv


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


@pytest.mark.parametrize("amount", [
    "NaN", "sNaN", "Infinity", "-Infinity", "1e2", "-1", "1,2", "1,,000", "0.001",
    "1000000000000.01", "", "bad",
])
def test_invalid_amounts_are_counted_without_crashing_or_changing_totals(amount):
    result = summarize([{"amount": amount}, {"amount": "0.30"}])
    assert result["summary"]["amount_error_rows"] == 1
    assert result["summary"]["total_amount"] == "0.30"
    assert result["summary"]["average_amount"] == "0.30"


def test_decimal_precision_grouped_amounts_and_zero_are_preserved():
    result = summarize([{"amount": value} for value in ["0.10", "0.20", "1,234.50", "0.00"]])
    assert result["summary"]["total_amount"] == "1234.80"
    assert result["summary"]["valid_amount_rows"] == 4
    assert result["by_store"][0]["store"] == "未填写门店"
    assert result["by_date"][0]["date"] == "未填写日期"


@pytest.mark.parametrize("content", [
    "store,date\nA,2026-11-05\n", "store,date,amount,amount\nA,2026-11-05,1,2\n",
    "store,date,amount\nA,2026-11-05,1,extra\n", "store,date,amount\nA,2026-11-05\n",
])
def test_malformed_csv_is_rejected(content, tmp_path):
    source = tmp_path / "accepted.csv"
    source.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        summarize_csv(source)


def test_cli_reads_bom_and_reports_missing_input_without_writing_output(tmp_path, capsys):
    source = tmp_path / "accepted.csv"
    output = tmp_path / "kpi.json"
    source.write_text("store,date,amount\nA,2026-11-05,0.10\n", encoding="utf-8-sig")
    assert main([str(source), "-o", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["summary"]["total_amount"] == "0.10"
    before = output.read_bytes()
    assert main([str(tmp_path / "missing.csv"), "-o", str(output)]) == 2
    assert output.read_bytes() == before
    assert "OrderCheck KPI:" in capsys.readouterr().err
