from io import BytesIO
from datetime import datetime
import json
from pathlib import Path
import pandas as pd
import pytest
from openpyxl import Workbook
from order_batch import read_tables, run_batch
from order_rules import validate_config, validate_orders


@pytest.fixture
def config():
    return json.loads(Path("config/orders.json").read_text(encoding="utf-8"))


def test_multisheet_and_native_date(config):
    book = Workbook()
    for sheet in [book.active, book.create_sheet("Other")]:
        sheet.append(["order_id","store","date","amount"])
        sheet.append(["001",sheet.title,datetime(2026,9,8),10])
    buf = BytesIO()
    book.save(buf)
    tables = read_tables("native.xlsx", buf.getvalue())
    result, manifest = run_batch(tables, config)
    assert result.summary["accepted_rows"] == 2  # same ID, different stores
    assert result.clean.date.tolist() == ["2026-09-08"] * 2
    assert len({row["sha256"] for row in manifest["inputs"]}) == 1


def test_multiline_csv_provenance(config):
    text = 'order_id,store,date,amount,note\n001,A,2026-09-08,0,"line1\nline2"\n002,A,2026-09-08,1,test\n'
    result, _ = run_batch(read_tables("a.csv", text.encode()), config)
    assert result.clean.source_row.tolist() == ["2", "3"]
    assert json.loads(result.clean.raw_json.iloc[0])["note"] == "line1\nline2"


def test_invalid_and_valid_same_key_both_quarantined(config):
    frame = pd.DataFrame([["001","A","2026-09-08","2"],["001","A","2026-09-08","bad"]],
                         columns=["order_id","store","date","amount"])
    result = validate_orders(frame, config)
    assert result.clean.empty
    assert result.summary["conflict_rows"] == 2
    assert result.summary["accepted_amount_total"] == "0.00"


@pytest.mark.parametrize("key,value", [
    ("amount_min","NaN"),("amount_max","Infinity"),
    ("amount_max","-1"),("date_formats",[{}]),("required",[]),
    ("duplicate_key",["unknown"]),("version",True)])
def test_malformed_config(config, key, value):
    config[key] = value
    with pytest.raises(ValueError):
        validate_config(config)


def test_inconsistent_mapping(config):
    tables = read_tables("a.csv", b"order_id,store,date,amount\n001,A,2026-09-08,1\n")
    with pytest.raises(ValueError, match="多个"):
        run_batch(tables, config, {tables[0].key: {"order_id":"order_id","store":"order_id",
                                                  "date":"date","amount":"amount"}})


def test_unknown_mapping(config):
    tables = read_tables("a.csv", b"order_id,store,date,amount\n001,A,2026-09-08,1\n")
    with pytest.raises(ValueError, match="未知"):
        run_batch(tables, config, {"missing.csv / CSV": {}})


def test_non_utf8():
    with pytest.raises(ValueError):
        read_tables("a.csv", "订单号,金额\n1,2".encode("gbk"))


def test_control_char():
    with pytest.raises(ValueError, match="控制"):
        read_tables("a.csv", b"a,b\n1,hi\x00\n")


def test_resource_limit(monkeypatch, config):
    import order_batch
    tables = read_tables("a.csv", b"order_id,store,date,amount\n001,A,2026-09-08,1\n")
    monkeypatch.setattr(order_batch, "MAX_ROWS", 0)
    with pytest.raises(ValueError, match="最多"):
        run_batch(tables, config)
