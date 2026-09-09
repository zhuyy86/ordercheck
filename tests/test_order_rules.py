import json
from pathlib import Path
import pandas as pd
import pytest
from data_cleaning import DataCleaner
from order_rules import validate_orders, validate_config


@pytest.fixture
def config():
    return json.loads(Path("config/orders.json").read_text(encoding="utf-8"))


def rows(*values):
    return pd.DataFrame(values, columns=["order_id", "store", "date", "amount"])


def test_preserve_ids_and_decimal(config):
    cleaner = DataCleaner(rows(("001", "A", "2026/09/08", "10.10"), ("002", "A", "2026-09-08", "0.20")))
    result = cleaner.validate_order_batch(config)
    assert result.clean.order_id.tolist() == ["001", "002"]
    assert result.summary["accepted_amount_total"] == "10.30"
    assert result.clean.date.iloc[0] == "2026-09-08"
    assert cleaner.get_original_data().date.iloc[0] == "2026/09/08"
    assert cleaner.get_transformations_summary()["rows_after"] == 2
    assert cleaner.validate_order_batch(config).summary == result.summary


@pytest.mark.parametrize("amount", ["oops", "-1", "1,20", "1e3", "NaN", "Infinity", "0.001", "10000001"])
def test_bad_amount_quarantined(config, amount):
    result = validate_orders(rows(("001","A","2026-09-08",amount)), config)
    assert result.clean.empty
    assert result.summary["invalid_rows"] == 1
    assert amount in result.rejected.raw_json.iloc[0]


def test_dates_and_empty(config):
    result = validate_orders(rows(("", "A", "2026-02-30", "4")), config)
    assert "order_id" in result.rejected.reason.iloc[0]
    assert "date" in result.rejected.reason.iloc[0]


def test_duplicate_and_conflict(config):
    result = validate_orders(rows(
        ("001","A","2026-09-08","1"), ("001","A","2026-09-08","1.00"),
        ("002","A","2026-09-08","2"), ("002","A","2026-09-08","3")), config)
    assert result.summary["accepted_rows"] == 1
    assert result.summary["duplicate_rows"] == 1
    assert result.summary["conflict_rows"] == 2
    assert len(result.clean) + len(result.rejected) == 4


def test_ambiguous_dates(config):
    config["date_formats"] = ["%d/%m/%Y", "%m/%d/%Y"]
    result = validate_orders(rows(("001","A","01/02/2026","1")), config)
    assert result.clean.empty
    assert "歧义" in result.rejected.reason.iloc[0]


def test_bad_config(config):
    config["aliases"]["date"].append("金额")
    with pytest.raises(ValueError, match="冲突"):
        validate_config(config)


def test_custom_amount_range(config):
    config["amount_max"] = "5"
    result = validate_orders(rows(("001","A","2026-09-08","6")), config)
    assert result.summary["invalid_rows"] == 1
