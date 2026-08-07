#!/usr/bin/env python3
"""Manage the private local watchlist for next-day-trade-plan (Taiwan equities)."""

import argparse
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

DEFAULT_PATH = Path.home() / ".cursor" / "data" / "next-day-trade-plan" / "watchlist.json"
# Accept 4-6 digit codes, optional letter suffix for special shares, TW or TWO exchange.
CODE_RE = re.compile(r"^\d{4,6}[A-Z]?\.(TW|TWO)$")


def watchlist_path():
    return Path(os.environ.get("NEXT_DAY_TRADE_PLAN_WATCHLIST", DEFAULT_PATH)).expanduser()


def empty_data():
    return {"version": 1, "market": "TW", "updated_at": None, "positions": []}


def load_data(path):
    if not path.exists():
        return empty_data()
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("positions"), list):
        raise ValueError("watchlist must be an object containing a positions array")
    data.setdefault("market", "TW")
    return data


def normalize_code(code):
    code = str(code or "").strip().upper()
    if CODE_RE.match(code):
        return code
    # Allow bare codes like 2330 / 6488; require explicit exchange when ambiguous later.
    if re.fullmatch(r"\d{4,6}[A-Z]?", code):
        raise ValueError(
            f"missing exchange suffix for {code}; use {code}.TW (TWSE) or {code}.TWO (TPEx)"
        )
    raise ValueError(f"invalid Taiwan equity code: {code or '<missing>'}")


def normalize(position):
    if not isinstance(position, dict):
        raise ValueError("each position must be an object")
    result = dict(position)
    code = normalize_code(result.get("code", ""))
    result["code"] = code
    result["name"] = str(result.get("name", "")).strip()
    for key in ("cost", "position_pct", "max_risk_pct"):
        if result.get(key) is not None:
            result[key] = float(result[key])
            if result[key] < 0:
                raise ValueError(f"{code}: {key} must be non-negative")
    if result.get("position_pct", 0) > 100:
        raise ValueError(f"{code}: position_pct cannot exceed 100")
    if result.get("shares") is not None:
        result["shares"] = int(result["shares"])
        if result["shares"] < 0:
            raise ValueError(f"{code}: shares must be non-negative")
    result["enabled"] = bool(result.get("enabled", True))
    result["notes"] = str(result.get("notes", "")).strip()
    return result


def validate_total(positions):
    total = sum(item.get("position_pct") or 0 for item in positions if item.get("enabled", True))
    if total > 100.000001:
        raise ValueError(f"enabled position_pct totals {total:.2f}%, exceeding 100%")


def merge_positions(existing, updates):
    by_code = {normalize(item)["code"]: normalize(item) for item in existing}
    for raw in updates:
        if not isinstance(raw, dict):
            raise ValueError("each position must be an object")
        code = normalize_code(raw.get("code", ""))
        previous = by_code.get(code, {})
        by_code[code] = normalize(previous | raw | {"code": code})
    positions = sorted(by_code.values(), key=lambda item: item["code"])
    validate_total(positions)
    return positions


def save_data(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    data["version"] = 1
    data["market"] = "TW"
    data["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    validate_total(data["positions"])
    fd, temp_name = tempfile.mkstemp(prefix="watchlist-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def print_data(data, path):
    output = dict(data)
    output["path"] = str(path)
    output["enabled_count"] = sum(1 for item in data["positions"] if item.get("enabled", True))
    output["enabled_position_pct"] = round(
        sum(item.get("position_pct") or 0 for item in data["positions"] if item.get("enabled", True)), 4
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Manage the Taiwan next-day trade plan watchlist")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("path")
    contains = sub.add_parser("contains")
    contains.add_argument("code")

    add = sub.add_parser("add")
    add.add_argument("--code", required=True)
    add.add_argument("--name", default="")
    add.add_argument("--cost", type=float)
    add.add_argument("--position-pct", type=float)
    add.add_argument("--shares", type=int)
    add.add_argument("--max-risk-pct", type=float)
    add.add_argument("--notes", default="")

    bulk = sub.add_parser("import-json")
    bulk.add_argument("file", type=Path)
    for command in ("remove", "disable", "enable"):
        item = sub.add_parser(command)
        item.add_argument("code")

    args = parser.parse_args()
    path = watchlist_path()
    if args.command == "path":
        print(path)
        return
    data = load_data(path)
    if args.command == "contains":
        code = normalize_code(args.code)
        position = next((item for item in data["positions"] if item["code"] == code), None)
        print(json.dumps({"code": code, "exists": position is not None, "position": position}, ensure_ascii=False, indent=2))
        raise SystemExit(0 if position is not None else 1)
    if args.command == "list":
        print_data(data, path)
        return
    if args.command == "add":
        update = {"code": args.code, "enabled": True}
        for key, value in {
            "name": args.name or None,
            "cost": args.cost,
            "position_pct": args.position_pct,
            "shares": args.shares,
            "max_risk_pct": args.max_risk_pct,
            "notes": args.notes or None,
        }.items():
            if value is not None:
                update[key] = value
        data["positions"] = merge_positions(data["positions"], [update])
    elif args.command == "import-json":
        with args.file.open("r", encoding="utf-8") as handle:
            imported = json.load(handle)
        updates = imported.get("positions") if isinstance(imported, dict) else imported
        if not isinstance(updates, list):
            raise ValueError("import must be an array or an object containing positions")
        data["positions"] = merge_positions(data["positions"], updates)
    else:
        code = normalize_code(args.code)
        matches = [item for item in data["positions"] if item["code"] == code]
        if not matches:
            raise ValueError(f"position not found: {code}")
        if args.command == "remove":
            data["positions"] = [item for item in data["positions"] if item["code"] != code]
        else:
            for item in data["positions"]:
                if item["code"] == code:
                    item["enabled"] = args.command == "enable"
            validate_total(data["positions"])
    save_data(path, data)
    print_data(data, path)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: {exc}") from exc
