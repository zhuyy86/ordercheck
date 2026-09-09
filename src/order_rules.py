"""Order-specific validation added to Dataset Cleaner; no value imputation."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

import pandas as pd

FIELDS = ("order_id", "store", "date", "amount")
PROVENANCE = ("source_file", "source_sheet", "source_row", "raw_json")
RULE_KEYS = {"version", "aliases", "required", "duplicate_key", "date_formats",
             "amount_min", "amount_max"}


def validate_config(config):
    """Reject ambiguous/unsupported rules before any data is processed."""
    if not isinstance(config, dict) or set(config) != RULE_KEYS:
        raise ValueError("规则必须包含且仅包含 version/aliases/required/duplicate_key/date_formats/amount_min/amount_max")
    if config["version"] != 1 or isinstance(config["version"], bool):
        raise ValueError("仅支持规则版本 1")
    if not isinstance(config["aliases"], dict) or set(config["aliases"]) != set(FIELDS):
        raise ValueError("aliases 必须定义四个标准字段")
    used = {}
    for field in FIELDS:
        aliases = config["aliases"][field]
        if not isinstance(aliases, list) or any(not isinstance(x, str) or not x.strip() for x in aliases):
            raise ValueError("别名必须是非空字符串列表")
        for alias in [field, *aliases]:
            key = alias.strip().casefold()
            if key in used and used[key] != field:
                raise ValueError(f"别名冲突：{alias}")
            used[key] = field
    for name in ("required", "duplicate_key"):
        value = config[name]
        if (not isinstance(value, list) or not value
                or any(not isinstance(x, str) or x not in FIELDS for x in value)
                or len(value) != len(set(value))):
            raise ValueError(f"{name} 必须是标准字段组成的非空列表")
    if not set(config["duplicate_key"]).issubset(config["required"]):
        raise ValueError("重复键必须也是必填项")
    formats = config["date_formats"]
    supported = {"%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"}
    if not isinstance(formats, list) or not formats or any(not isinstance(x, str) or x not in supported for x in formats):
        raise ValueError("日期格式只支持 YYYY-MM-DD、YYYY/MM/DD、DD/MM/YYYY、MM/DD/YYYY")
    try:
        lo, hi = Decimal(str(config["amount_min"])), Decimal(str(config["amount_max"]))
        if not lo.is_finite() or not hi.is_finite() or lo < 0 or hi < lo or hi > Decimal("1e12"):
            raise ValueError("金额上下限不合理（要求 0 ≤ min ≤ max ≤ 1e12）")
    except InvalidOperation as exc:
        raise ValueError("金额上下限不是有效数字") from exc
    return config


def config_hash(config):
    return hashlib.sha256(json.dumps(config, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def normalize_date(value, formats):
    parsed = set()
    for fmt in formats:
        try:
            day = datetime.strptime(value, fmt)
            # strptime accepts single-digit fields: normalize them deliberately.
            parsed.add(day.strftime("%Y-%m-%d"))
        except ValueError:
            pass
    if len(parsed) != 1:
        raise ValueError("日期无效或存在日/月歧义")
    return parsed.pop()


def normalize_amount(value, config):
    # Explicit decimal point, at most two decimal places; no locale guessing.
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", value):
        raise ValueError("金额需为非负数字，使用小数点且最多两位小数")
    amount = Decimal(value)
    if not Decimal(str(config["amount_min"])) <= amount <= Decimal(str(config["amount_max"])):
        raise ValueError("金额超出配置范围")
    return format(amount.quantize(Decimal("0.01")), "f")


@dataclass
class OrderResult:
    clean: pd.DataFrame
    rejected: pd.DataFrame
    changes: pd.DataFrame
    summary: dict
    config: dict


def validate_orders(frame, config):
    validate_config(config)
    if not set(FIELDS).issubset(frame.columns):
        raise ValueError("校验输入缺少标准字段")
    records, errors, changes = [], [], []
    for _, source in frame.iterrows():
        record = {k: ("" if pd.isna(v) else str(v)) for k, v in source.items()}
        if not record.get("raw_json"):
            record["raw_json"] = json.dumps({k: record[k] for k in FIELDS}, ensure_ascii=False)
        row_errors = []
        for field in FIELDS:
            before = record[field]
            after = before.strip()
            if not after and field in config["required"]:
                row_errors.append(f"{field}: 必填值为空")
            elif after:
                try:
                    if field == "date":
                        after = normalize_date(after, config["date_formats"])
                    elif field == "amount":
                        after = normalize_amount(after, config)
                except ValueError as exc:
                    row_errors.append(f"{field}: {exc}")
            record[field] = after
            if before != after:
                changes.append({**{p: record.get(p, "") for p in PROVENANCE[:3]},
                                "field": field, "before": before, "after": after})
        records.append(record)
        errors.append(row_errors)

    groups = defaultdict(list)
    for i, row in enumerate(records):
        key = tuple(row[k] for k in config["duplicate_key"])
        if all(key):
            groups[key].append(i)
    duplicates, conflicts = set(), set()
    for indexes in groups.values():
        if len(indexes) < 2:
            continue
        signatures = {tuple(records[i][k] for k in FIELDS) for i in indexes}
        if len(signatures) > 1:
            conflicts.update(indexes)
            for i in indexes:
                errors[i].append("重复键冲突：同一订单的内容不同，整组待复核")
        elif not any(errors[i] for i in indexes):
            for i in indexes[1:]:
                duplicates.add(i)
                first = records[indexes[0]]
                errors[i].append(f"完全重复：保留 {first.get('source_file', '')} / "
                                 f"{first.get('source_sheet', '')} / {first.get('source_row', '')}")

    clean, rejected = [], []
    for i, row in enumerate(records):
        if errors[i]:
            status = "conflict" if i in conflicts else "duplicate" if i in duplicates else "invalid"
            rejected.append({**row, "status": status, "reason": "；".join(errors[i])})
        else:
            clean.append(row)
    columns = list(dict.fromkeys([*FIELDS, *PROVENANCE, *frame.columns]))
    clean_df = pd.DataFrame(clean, columns=columns)
    rejected_df = pd.DataFrame(rejected, columns=[*columns, "status", "reason"])
    total = sum((Decimal(r["amount"]) for r in clean if r["amount"]), Decimal("0"))
    summary = {
        "input_rows": len(records), "accepted_rows": len(clean), "rejected_rows": len(rejected),
        "duplicate_rows": len(duplicates), "conflict_rows": len(conflicts),
        "invalid_rows": len(rejected) - len(duplicates) - len(conflicts),
        "changed_cells": len(changes), "accepted_amount_total": format(total, ".2f"),
        "config_sha256": config_hash(config),
    }
    return OrderResult(clean_df, rejected_df,
                       pd.DataFrame(changes, columns=[*PROVENANCE[:3], "field", "before", "after"]),
                       summary, json.loads(json.dumps(config)))
