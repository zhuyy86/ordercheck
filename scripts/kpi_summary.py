"""Summarize an OrderCheck accepted.csv file into business KPIs.

The script intentionally uses only the Python standard library so it can be
run beside the existing Streamlit/CLI workflow without adding dependencies.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _amount(row: dict[str, str]) -> Decimal | None:
    raw = (row.get("amount") or "").strip()
    if not re.fullmatch(r"(?:[0-9]+|[1-9][0-9]{0,2}(?:,[0-9]{3})+)(?:\.[0-9]{1,2})?", raw):
        return None
    try:
        value = Decimal(raw.replace(",", ""))
    except InvalidOperation:
        return None
    return value if value.is_finite() and 0 <= value <= Decimal("1e12") else None


def summarize(rows: Iterable[dict[str, str]], source: str = "accepted.csv") -> dict:
    """Return deterministic summary metrics for accepted order rows."""
    by_store: dict[str, dict[str, object]] = defaultdict(
        lambda: {"order_count": 0, "total_amount": Decimal("0")}
    )
    by_date: dict[str, dict[str, object]] = defaultdict(
        lambda: {"order_count": 0, "total_amount": Decimal("0")}
    )
    total = Decimal("0")
    row_count = 0
    amount_errors = 0

    for row in rows:
        row_count += 1
        amount = _amount(row)
        if amount is None:
            amount_errors += 1
            continue
        total += amount
        store = (row.get("store") or "未填写门店").strip() or "未填写门店"
        date = (row.get("date") or "未填写日期").strip() or "未填写日期"
        for bucket, key in ((by_store, store), (by_date, date)):
            bucket[key]["order_count"] = int(bucket[key]["order_count"]) + 1
            bucket[key]["total_amount"] = (
                bucket[key]["total_amount"] + amount
            )

    def materialize(bucket: dict[str, dict[str, object]], sort_key: str) -> list[dict]:
        items = [
            {
                sort_key: key,
                "order_count": int(value["order_count"]),
                "total_amount": _money(value["total_amount"]),
            }
            for key, value in bucket.items()
        ]
        return sorted(
            items,
            key=lambda item: (-Decimal(item["total_amount"]), str(item[sort_key])),
        )

    valid_count = row_count - amount_errors
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "summary": {
            "row_count": row_count,
            "valid_amount_rows": valid_count,
            "amount_error_rows": amount_errors,
            "total_amount": _money(total),
            "average_amount": _money(total / valid_count) if valid_count else "0.00",
        },
        "by_store": materialize(by_store, "store"),
        "by_date": sorted(
            materialize(by_date, "date"),
            key=lambda item: str(item["date"]),
        ),
    }


def summarize_csv(path: str | Path) -> dict:
    """Read an OrderCheck accepted CSV using BOM-tolerant UTF-8."""
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, strict=True)
        headers = reader.fieldnames or []
        if not {"store", "date", "amount"}.issubset(headers) or len(headers) != len(set(headers)):
            raise ValueError("CSV must have unique headers including store, date and amount.")

        def rows():
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("CSV record column count does not match the header.")
                yield row

        return summarize(rows(), path.name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize accepted.csv into store/date KPIs."
    )
    parser.add_argument("input", type=Path, help="OrderCheck accepted.csv")
    parser.add_argument(
        "-o", "--output", type=Path,
        help="Optional JSON output path; stdout when omitted",
    )
    args = parser.parse_args(argv)

    try:
        result = summarize_csv(args.input)
        payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
    except (OSError, UnicodeError, ValueError, csv.Error) as exc:
        print(f"OrderCheck KPI: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
