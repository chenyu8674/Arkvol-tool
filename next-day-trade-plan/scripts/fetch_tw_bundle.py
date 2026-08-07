#!/usr/bin/env python3
"""Fetch a Taiwan-equity data bundle (yfinance-first) without all-or-nothing failure."""

import argparse
import json
import re
import signal
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

try:
    import pandas as pd
    import requests
    import yfinance as yf
except ImportError as exc:
    raise SystemExit("error: install yfinance, pandas and requests before running this script") from exc

from analyze_history import analyze, tw_tick_size

CODE_RE = re.compile(r"^(?P<root>\d{4,6}[A-Z]?)\.(?P<ex>TW|TWO)$")


def normalize_code(value):
    value = value.strip().upper()
    if "." not in value:
        raise ValueError(
            f"missing exchange suffix for {value}; use {value}.TW (TWSE) or {value}.TWO (TPEx)"
        )
    match = CODE_RE.match(value)
    if not match:
        raise ValueError(f"invalid Taiwan equity code: {value}")
    return match.group("root"), match.group("ex"), f"{match.group('root')}.{match.group('ex')}"


def json_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def records(frame, limit=None, selection="head"):
    if frame is None or getattr(frame, "empty", True):
        return []
    if limit and selection == "tail":
        selected = frame.tail(limit)
    elif limit:
        selected = frame.head(limit)
    else:
        selected = frame
    return [{str(key): json_value(value) for key, value in row.items()} for row in selected.to_dict("records")]


def call_component(name, source, function, retries=1, timeout_seconds=20):
    started = time.monotonic()
    last_error = None

    def timeout_handler(_signum, _frame):
        raise TimeoutError(f"component exceeded {timeout_seconds}s")

    for attempt in range(retries + 1):
        previous_handler = None
        try:
            previous_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
            value = function()
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
            row_count = len(value) if hasattr(value, "__len__") else None
            return {
                "name": name,
                "ok": True,
                "source": source,
                "rows": row_count,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "value": value,
            }
        except Exception as exc:  # upstream public endpoints raise heterogeneous errors
            signal.setitimer(signal.ITIMER_REAL, 0)
            if previous_handler is not None:
                signal.signal(signal.SIGALRM, previous_handler)
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
    return {
        "name": name,
        "ok": False,
        "source": source,
        "rows": 0,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "error": last_error,
        "value": None,
    }


def component_output(component, data=None):
    output = {key: value for key, value in component.items() if key != "value"}
    if data is not None:
        output["data"] = data
    return output


def use_fallback(primary, source, function):
    if primary["ok"]:
        return primary
    fallback = call_component(primary["name"], source, function, retries=0)
    fallback["fallback_from"] = {"source": primary["source"], "error": primary.get("error")}
    return fallback


def roc_year(year):
    return year - 1911


def parse_tw_number(value):
    text = str(value).strip().replace(",", "")
    if text in {"", "--", "---", "null", "None"}:
        return None
    return float(text)


def fetch_yfinance_history(symbol, start, end, auto_adjust):
    ticker = yf.Ticker(symbol)
    frame = ticker.history(start=start, end=end, auto_adjust=auto_adjust, actions=False)
    if frame is None or frame.empty:
        raise ValueError(f"yfinance returned empty history for {symbol}")
    frame = frame.reset_index()
    date_col = "Date" if "Date" in frame.columns else frame.columns[0]
    rows = []
    for _, row in frame.iterrows():
        trade_date = pd.to_datetime(row[date_col]).tz_localize(None).date()
        rows.append(
            {
                "trade_date": trade_date,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "vol": float(row["Volume"]),
            }
        )
    return pd.DataFrame(rows)


def fetch_twse_month(symbol_root, year, month):
    session = requests.Session()
    session.trust_env = False
    date_token = f"{year}{month:02d}01"
    url = (
        "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
        f"?date={date_token}&stockNo={quote(symbol_root)}&response=json"
    )
    response = session.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    payload = response.json()
    if payload.get("stat") != "OK":
        raise ValueError(payload.get("stat") or "TWSE response not OK")
    rows = []
    for item in payload.get("data") or []:
        # item: 日期,成交股數,成交金額,開盤價,最高價,最低價,收盤價,...
        roc_date = str(item[0]).strip()
        parts = roc_date.replace("-", "/").split("/")
        if len(parts) != 3:
            continue
        year_ad = int(parts[0]) + 1911
        trade_date = date(year_ad, int(parts[1]), int(parts[2]))
        open_px = parse_tw_number(item[3])
        high_px = parse_tw_number(item[4])
        low_px = parse_tw_number(item[5])
        close_px = parse_tw_number(item[6])
        vol = parse_tw_number(item[1])
        if None in (open_px, high_px, low_px, close_px, vol):
            continue
        rows.append(
            {
                "trade_date": trade_date,
                "open": open_px,
                "high": high_px,
                "low": low_px,
                "close": close_px,
                "vol": vol,
            }
        )
    return rows


def fetch_twse_history(symbol_root, start, end):
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()
    cursor = date(start_date.year, start_date.month, 1)
    end_month = date(end_date.year, end_date.month, 1)
    collected = []
    while cursor <= end_month:
        collected.extend(fetch_twse_month(symbol_root, cursor.year, cursor.month))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
        time.sleep(0.25)
    frame = pd.DataFrame(collected)
    if frame.empty:
        raise ValueError("TWSE returned no daily bars")
    frame = frame.drop_duplicates(subset=["trade_date"]).sort_values("trade_date")
    frame = frame[(frame["trade_date"] >= start_date) & (frame["trade_date"] <= end_date)]
    if frame.empty:
        raise ValueError("TWSE history empty after date filter")
    return frame.reset_index(drop=True)


def latest_ohlc(frame):
    row = frame.iloc[-1]
    return {
        "date": pd.to_datetime(row["trade_date"]).date().isoformat(),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
    }


def history_rows(frame):
    result = []
    for _, row in frame.iterrows():
        result.append(
            {
                "trade_date": pd.to_datetime(row["trade_date"]).date(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "vol": float(row["vol"]),
            }
        )
    return result


def extract_profile(symbol):
    ticker = yf.Ticker(symbol)
    info = ticker.info or {}
    profile = {
        "symbol": symbol,
        "shortName": info.get("shortName"),
        "longName": info.get("longName"),
        "exchange": info.get("exchange"),
        "currency": info.get("currency"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market": info.get("market"),
        "quoteType": info.get("quoteType"),
        "website": info.get("website"),
        "previousClose": info.get("previousClose"),
        "regularMarketPrice": info.get("regularMarketPrice"),
    }
    return {key: value for key, value in profile.items() if value is not None}


def fetch_news(symbol, limit):
    ticker = yf.Ticker(symbol)
    items = ticker.news or []
    rows = []
    for item in items[:limit]:
        content = item.get("content") if isinstance(item, dict) else None
        if isinstance(content, dict):
            provider = content.get("provider") or {}
            rows.append(
                {
                    "id": item.get("id") or content.get("id"),
                    "title": content.get("title"),
                    "summary": content.get("summary") or content.get("description"),
                    "publisher": provider.get("displayName") if isinstance(provider, dict) else None,
                    "link": (content.get("canonicalUrl") or {}).get("url")
                    if isinstance(content.get("canonicalUrl"), dict)
                    else content.get("clickThroughUrl"),
                    "pubDate": content.get("pubDate"),
                    "contentType": content.get("contentType"),
                }
            )
        elif isinstance(item, dict):
            rows.append(
                {
                    "id": item.get("uuid") or item.get("id"),
                    "title": item.get("title"),
                    "summary": item.get("summary"),
                    "publisher": item.get("publisher"),
                    "link": item.get("link"),
                    "pubDate": item.get("providerPublishTime"),
                }
            )
    if not rows:
        raise ValueError("no news returned")
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="Fetch Taiwan equity quotes, profile and news")
    parser.add_argument("code", help="Taiwan equity code, e.g. 2330.TW or 6488.TWO")
    parser.add_argument("--start", default=(date.today() - timedelta(days=550)).strftime("%Y-%m-%d"))
    parser.add_argument("--end", default=(date.today() + timedelta(days=1)).strftime("%Y-%m-%d"))
    parser.add_argument("--news-limit", type=int, default=30)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root, exchange, symbol = normalize_code(args.code)

    bundle = {
        "meta": {
            "code": symbol,
            "root": root,
            "exchange": exchange,
            "market": "TW",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "yfinance_version": getattr(yf, "__version__", "unknown"),
            "policy": "yfinance-first; MOPS/TWSE/TPEx verification required for high-impact facts",
        },
        "components": {},
    }

    profile_call = call_component("company_profile", "Yahoo Finance via yfinance", lambda: extract_profile(symbol))
    profile = profile_call["value"] if profile_call["ok"] else {}
    industry = None
    if isinstance(profile, dict):
        industry = profile.get("industry") or profile.get("sector")
    bundle["components"]["company_profile"] = component_output(profile_call, profile)

    qfq_call = call_component(
        "history_qfq",
        "Yahoo Finance via yfinance (auto_adjust=True)",
        lambda: fetch_yfinance_history(symbol, args.start, args.end, True),
    )
    raw_call = call_component(
        "history_raw",
        "Yahoo Finance via yfinance (auto_adjust=False)",
        lambda: fetch_yfinance_history(symbol, args.start, args.end, False),
    )
    if exchange == "TW":
        raw_call = use_fallback(
            raw_call,
            "TWSE STOCK_DAY open data",
            lambda: fetch_twse_history(root, args.start, (date.today()).strftime("%Y-%m-%d")),
        )

    history_check = {"ok": False, "reason": "qfq or raw history unavailable"}
    metrics = None
    recent_bars = []
    if qfq_call["ok"] and raw_call["ok"] and len(qfq_call["value"]) and len(raw_call["value"]):
        qfq_latest = latest_ohlc(qfq_call["value"])
        raw_latest = latest_ohlc(raw_call["value"])
        differences = {
            key: round(abs(qfq_latest[key] - raw_latest[key]), 6) for key in ("open", "high", "low", "close")
        }
        # Taiwan quotes are in TWD; allow one tick of noise at latest close.
        tolerance = max(0.01, (tw_tick_size(raw_latest["close"]) or 0.01))
        history_check = {
            "ok": qfq_latest["date"] == raw_latest["date"] and max(differences.values()) <= tolerance,
            "qfq_latest": qfq_latest,
            "raw_latest": raw_latest,
            "absolute_differences": differences,
            "tolerance": tolerance,
            "tick_size": tw_tick_size(raw_latest["close"]),
            "board_lot": 1000,
            "default_price_limit_pct": 10.0,
        }
        rows = history_rows(qfq_call["value"])
        if len(rows) >= 20:
            metrics = analyze(rows)
            metrics["data"]["adjust"] = "qfq"
            metrics["market_rules"] = {
                "board_lot": 1000,
                "tick_size_at_last_close": tw_tick_size(rows[-1]["close"]),
                "default_price_limit_pct": 10.0,
            }
        recent_bars = records(qfq_call["value"], 30, selection="tail")

    bundle["components"]["history_qfq"] = component_output(qfq_call, {"recent_bars": recent_bars, "metrics": metrics})
    bundle["components"]["history_raw"] = component_output(raw_call, {"latest": history_check.get("raw_latest")})
    bundle["components"]["history_validation"] = history_check

    news_call = call_component(
        "company_news",
        "Yahoo Finance news via yfinance",
        lambda: fetch_news(symbol, args.news_limit),
    )
    bundle["components"]["company_news"] = component_output(news_call, records(news_call["value"], args.news_limit))

    # Industry news has no stable free Taiwan endpoint in-bundle; mark explicit gap.
    industry_call = {
        "name": "industry_news",
        "ok": False,
        "source": "manual/MOPS/media",
        "rows": 0,
        "elapsed_seconds": 0,
        "error": "no bundled Taiwan industry-news API; search MOPS/media with verified industry keywords",
        "value": None,
    }
    bundle["components"]["industry_news"] = component_output(
        industry_call,
        {
            "industry": industry,
            "guidance": [
                "https://mops.twse.com.tw/",
                "https://www.twse.com.tw/",
                "https://www.tpex.org.tw/",
            ],
        },
    )

    notices_call = {
        "name": "notices",
        "ok": False,
        "source": "MOPS",
        "rows": 0,
        "elapsed_seconds": 0,
        "error": "open MOPS for official filings; not auto-scraped in this bundle",
        "value": None,
    }
    bundle["components"]["notices"] = component_output(
        notices_call,
        {"portal": "https://mops.twse.com.tw/", "symbol": symbol},
    )

    research_call = {
        "name": "research_reports",
        "ok": False,
        "source": "broker/research portals",
        "rows": 0,
        "elapsed_seconds": 0,
        "error": "no bundled Taiwan research API; treat broker notes as market expectations only",
        "value": None,
    }
    bundle["components"]["research_reports"] = component_output(research_call, [])

    statuses = list(bundle["components"].values())
    callable_statuses = [item for item in statuses if isinstance(item, dict) and "ok" in item]
    bundle["summary"] = {
        "components_ok": sum(1 for item in callable_statuses if item["ok"]),
        "components_failed": sum(1 for item in callable_statuses if not item["ok"]),
        "failed_components": [
            item.get("name", key)
            for key, item in bundle["components"].items()
            if isinstance(item, dict) and item.get("ok") is False
        ],
        "history_usable": bool(history_check.get("ok")) and metrics is not None and metrics["data"]["bars"] >= 60,
        "industry": industry,
        "market": "TW",
    }

    payload = json.dumps(bundle, ensure_ascii=False, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    if not bundle["summary"]["history_usable"]:
        raise SystemExit(2)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2) from exc
