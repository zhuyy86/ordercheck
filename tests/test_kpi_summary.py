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


def test_sync_failure_preserves_old_json_and_allows_retry(tmp_path, monkeypatch, capsys):
    from scripts import kpi_summary
    source = tmp_path / 'accepted.csv'
    source.write_text('store,date,amount\nA,2026-11-06,2.50\n', encoding='utf-8')
    output = tmp_path / 'kpi.json'
    output.write_bytes(b'previous complete report')
    original_sync = kpi_summary.os.fsync

    def fail_sync(fd):
        assert output.read_bytes() == b'previous complete report'
        raise OSError('simulated sync failure')

    monkeypatch.setattr(kpi_summary.os, 'fsync', fail_sync)
    assert main([str(source), '-o', str(output)]) == 2
    assert output.read_bytes() == b'previous complete report'
    assert not list(tmp_path.glob('.ordercheck-kpi-*'))
    assert 'sync failure' in capsys.readouterr().err
    monkeypatch.setattr(kpi_summary.os, 'fsync', original_sync)
    assert main([str(source), '-o', str(output)]) == 0
    assert json.loads(output.read_text())['summary']['total_amount'] == '2.50'


def test_replace_failure_does_not_publish_partial_json(tmp_path, monkeypatch):
    from scripts import kpi_summary
    output = tmp_path / 'fresh.json'

    def fail_replace(source, target):
        assert json.loads(source.read_text(encoding='utf-8')) == {'complete': True}
        assert not target.exists()
        raise PermissionError('simulated rename failure')

    monkeypatch.setattr(kpi_summary.os, 'replace', fail_replace)
    with pytest.raises(PermissionError):
        kpi_summary.write_summary(output, '{"complete":true}')
    assert not list(tmp_path.iterdir())


def test_kpi_rejects_input_as_output_and_hardlink_alias(tmp_path, capsys):
    import os
    source = tmp_path / 'accepted.csv'
    original = 'store,date,amount\nA,2026-11-06,1.00\n'
    source.write_text(original, encoding='utf-8')
    alias = tmp_path / 'alias.csv'
    os.link(source, alias)
    for output in [source, alias]:
        assert main([str(source), '-o', str(output)]) == 2
        assert source.read_text(encoding='utf-8') == original
    assert 'must not replace' in capsys.readouterr().err


def test_concurrent_json_replacements_are_complete(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from scripts.kpi_summary import write_summary
    output = tmp_path / 'kpi.json'
    payloads = [json.dumps({'writer': x, 'data': x * 100000}) for x in ['A', 'B']]
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda payload: write_summary(output, payload), payloads))
    assert output.read_text(encoding='utf-8') in payloads
    assert list(tmp_path.iterdir()) == [output]
