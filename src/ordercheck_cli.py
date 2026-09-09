"""Runnable CLI: returns 0=all accepted, 2=review needed, 1=input/config failure."""
import argparse
import json
from pathlib import Path
import sys

from order_batch import MAX_FILES, MAX_BYTES, read_tables, run_batch, report_zip
from order_demo import ROOT, demo_inputs


def main(argv=None):
    parser = argparse.ArgumentParser(description="OrderCheck — repeatable order batch validation")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="Run synthetic fixtures")
    source.add_argument("--input", nargs="+", type=Path, help="CSV/XLSX files")
    parser.add_argument("--rules", type=Path, default=ROOT / "config/orders.json")
    parser.add_argument("--mappings", type=Path, help="JSON table-key to field mappings (manifest.mappings)")
    parser.add_argument("--output", required=True, type=Path, help="New report ZIP; existing files are never overwritten")
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError("输出文件已存在，请使用新文件名")
        config = json.loads(args.rules.read_text(encoding="utf-8-sig"))
        mapping = json.loads(args.mappings.read_text(encoding="utf-8-sig")) if args.mappings else None
        if args.demo:
            inputs = demo_inputs()
        else:
            if len(args.input) > MAX_FILES:
                raise ValueError("最多 20 个文件")
            inputs = []
            for path in args.input:
                if path.stat().st_size > MAX_BYTES:
                    raise ValueError(f"{path.name}: 超过 5 MB")
                inputs.append((path.name, path.read_bytes()))
        tables = [table for name, content in inputs for table in read_tables(name, content)]
        result, manifest = run_batch(tables, config, mapping)
        payload = report_zip(result, manifest)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as handle:
            handle.write(payload)
        print(json.dumps(result.summary, ensure_ascii=True, indent=2))
        print(f"Report: {args.output.resolve()}")
        return 2 if result.summary["rejected_rows"] else 0
    except (ValueError, OSError, TypeError) as exc:
        print(f"OrderCheck: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
