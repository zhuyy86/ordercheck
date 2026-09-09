"""Synthetic fixtures only; no customer data or invented business outcomes."""
import csv
from io import BytesIO
from pathlib import Path
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]


def demo_inputs():
    inputs = [(name, (ROOT / "examples" / name).read_bytes())
              for name in ("north.csv", "south.csv")]
    book = Workbook()
    book.active.title = "Orders"
    with (ROOT / "examples/east.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            book.active.append(row)
    buffer = BytesIO()
    book.save(buffer)
    inputs.append(("east.xlsx", buffer.getvalue()))
    return inputs
