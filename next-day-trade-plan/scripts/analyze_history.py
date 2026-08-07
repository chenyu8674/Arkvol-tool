#!/usr/bin/env python3
"""Compute deterministic daily-bar evidence for a next-session trade plan."""

import argparse
import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path

REQUIRED = ("trade_date", "open", "high", "low", "close", "vol")


def mean(values):
    return sum(values) / len(values) if values else None


def round_value(value, digits=4):
    return None if value is None or not math.isfinite(value) else round(value, digits)


def parse_date(value):
    value = value.strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unsupported trade_date: {value}")


def load_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in REQUIRED if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("missing columns: " + ", ".join(missing))
        rows = []
        for line_no, raw in enumerate(reader, start=2):
            try:
                row = {"trade_date": parse_date(raw["trade_date"])}
                for key in REQUIRED[1:]:
                    row[key] = float(raw[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"line {line_no}: {exc}") from exc
            if min(row["open"], row["high"], row["low"], row["close"]) <= 0:
                raise ValueError(f"line {line_no}: prices must be positive")
            if row["high"] < row["low"] or row["vol"] < 0:
                raise ValueError(f"line {line_no}: invalid high/low or volume")
            rows.append(row)
    rows.sort(key=lambda item: item["trade_date"])
    if len({row["trade_date"] for row in rows}) != len(rows):
        raise ValueError("duplicate trade_date")
    if len(rows) < 20:
        raise ValueError("at least 20 daily bars are required")
    return rows


def swing_points(rows, side):
    points = []
    key = "low" if side == "low" else "high"
    for i in range(2, len(rows) - 2):
        value = rows[i][key]
        neighbors = [rows[j][key] for j in (i - 2, i - 1, i + 1, i + 2)]
        if (side == "low" and value < min(neighbors)) or (side == "high" and value > max(neighbors)):
            points.append({"date": rows[i]["trade_date"].isoformat(), "price": value})
    return points[-3:]


def analyze(rows):
    closes = [row["close"] for row in rows]
    volumes = [row["vol"] for row in rows]
    latest = rows[-1]
    true_ranges = []
    for i, row in enumerate(rows):
        previous_close = closes[i - 1] if i else row["close"]
        true_ranges.append(max(row["high"] - row["low"], abs(row["high"] - previous_close), abs(row["low"] - previous_close)))

    def moving_average(window):
        return mean(closes[-window:]) if len(rows) >= window else None

    def prior_volume_ratio(window):
        base = mean(volumes[-window - 1:-1]) if len(rows) > window else None
        return latest["vol"] / base if base else None

    def period_return(window):
        return latest["close"] / closes[-window - 1] - 1 if len(rows) > window else None

    result = {
        "data": {
            "bars": len(rows),
            "start_date": rows[0]["trade_date"].isoformat(),
            "end_date": latest["trade_date"].isoformat(),
            "latest": {key: round_value(latest[key]) for key in REQUIRED[1:]},
            "sample_warning": "fewer than 60 bars" if len(rows) < 60 else None,
        },
        "trend": {f"ma{window}": round_value(moving_average(window)) for window in (5, 10, 20, 60)},
        "momentum": {
            "return_5d": round_value(period_return(5), 6),
            "return_20d": round_value(period_return(20), 6),
        },
        "volatility": {
            "atr14": round_value(mean(true_ranges[-14:])),
            "atr14_pct_close": round_value(mean(true_ranges[-14:]) / latest["close"], 6),
        },
        "volume": {
            "ratio_to_prior_5d": round_value(prior_volume_ratio(5)),
            "ratio_to_prior_20d": round_value(prior_volume_ratio(20)),
        },
        "ranges": {},
        "swings": {"recent_lows": swing_points(rows, "low"), "recent_highs": swing_points(rows, "high")},
    }
    for window in (20, 60):
        if len(rows) >= window:
            result["ranges"][f"high_{window}d"] = round_value(max(row["high"] for row in rows[-window:]))
            result["ranges"][f"low_{window}d"] = round_value(min(row["low"] for row in rows[-window:]))
        else:
            result["ranges"][f"high_{window}d"] = None
            result["ranges"][f"low_{window}d"] = None
    return result


def tw_tick_size(price):
    """Return Taiwan cash-equity tick size for a positive price."""
    if price is None or price <= 0:
        return None
    if price < 10:
        return 0.01
    if price < 50:
        return 0.05
    if price < 100:
        return 0.1
    if price < 500:
        return 0.5
    if price < 1000:
        return 1.0
    return 5.0


def main():
    parser = argparse.ArgumentParser(description="Analyze front-adjusted Taiwan equity daily bars")
    parser.add_argument("history", type=Path, help="CSV containing front-adjusted daily bars")
    parser.add_argument(
        "--adjust",
        required=True,
        choices=("qfq",),
        help="required adjustment mode; only qfq (front-adjusted) is accepted",
    )
    args = parser.parse_args()
    try:
        rows = load_rows(args.history)
        result = analyze(rows)
        result["data"]["adjust"] = args.adjust
        latest_close = rows[-1]["close"]
        result["market_rules"] = {
            "board_lot": 1000,
            "tick_size_at_last_close": tw_tick_size(latest_close),
            "default_price_limit_pct": 10.0,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
