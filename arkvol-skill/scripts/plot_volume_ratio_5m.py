# coding: utf-8
"""按 5 分钟阶段绘制开盘至今量比变化图（滚动桶 + APP 累计口径）"""
import argparse
import sys
from datetime import datetime, time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def import_deps():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.font_manager as fm
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd
        import yfinance as yf
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "缺少依赖，请执行：python3 -m pip install matplotlib pandas yfinance numpy"
        ) from exc

    preferred_fonts = ["WenQuanYi Micro Hei", "Droid Sans Fallback", "Noto Sans CJK SC", "SimHei"]
    installed = {f.name for f in fm.fontManager.ttflist}
    matched = [name for name in preferred_fonts if name in installed]
    plt.rcParams["font.sans-serif"] = matched + ["DejaVu Sans"]
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False
    return plt, mdates, np, pd, yf


def flatten(df):
    import pandas as pd

    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def load_minute_bars(yf, symbol, lookback_days=10):
    import pandas as pd

    raw = flatten(yf.download(symbol, period=f"{lookback_days}d", interval="1m", progress=False, auto_adjust=True))
    if raw.empty:
        raise SystemExit(f"无法获取 {symbol} 分钟数据")

    raw = raw.reset_index()
    dt_col = next(c for c in raw.columns if "Datetime" in str(c) or str(c) == "Datetime")
    raw["ts"] = pd.to_datetime(raw[dt_col]).dt.tz_convert("Asia/Shanghai")
    raw["date"] = raw["ts"].dt.date
    raw["hm"] = raw["ts"].dt.strftime("%H:%M")
    raw["minute_of_day"] = raw["ts"].dt.hour * 60 + raw["ts"].dt.minute
    return raw


def session_mask(df):
    """A 股常规时段 09:30-11:30, 13:00-15:00"""
    import pandas as pd

    t = df["ts"].dt.time
    am = (t >= time(9, 30)) & (t <= time(11, 30))
    pm = (t >= time(13, 0)) & (t <= time(15, 0))
    return df[am | pm].copy()


def assign_bucket(df, bucket_minutes=5):
    import pandas as pd

    def bucket_start(ts):
        m = ts.hour * 60 + ts.minute
        base = (m // bucket_minutes) * bucket_minutes
        h, mi = divmod(base, 60)
        return f"{h:02d}:{mi:02d}"

    out = df.copy()
    out["bucket"] = out["ts"].apply(bucket_start)
    return out


def bucket_volume(df):
    import pandas as pd

    g = df.groupby(["date", "bucket"], as_index=False)["Volume"].sum()
    return g


def cumulative_app_ratio(today_df, hist_df):
    """每个分钟：APP 口径累计量比"""
    import pandas as pd

    rows = []
    today_sorted = today_df.sort_values("ts")
    for _, row in today_sorted.iterrows():
        if not is_trading_bucket(row["bucket"]):
            continue
        sub_today = today_sorted[today_sorted["ts"] <= row["ts"]]
        cum = float(sub_today["Volume"].sum())
        mins = len(sub_today)
        rate_t = cum / max(mins, 1)
        hm = row["hm"]
        past_rates = []
        for d, g in hist_df.groupby("date"):
            sub = g[g["hm"] <= hm].sort_values("ts")
            if len(sub) < 5:
                continue
            past_rates.append(float(sub["Volume"].sum()) / len(sub))
        if not past_rates:
            continue
        avg_p = sum(past_rates) / len(past_rates)
        ratio = rate_t / avg_p if avg_p > 0 else float("nan")
        h, m = map(int, row["bucket"].split(":"))
        ts = datetime.combine(row["date"], time(h, m))
        rows.append({"ts": ts, "bucket": row["bucket"], "app_ratio": ratio})
    return pd.DataFrame(rows)


def is_trading_bucket(bucket_str):
    h, m = map(int, bucket_str.split(":"))
    mins = h * 60 + m
    am = 9 * 60 + 30 <= mins <= 11 * 60 + 30
    pm = 13 * 60 <= mins <= 15 * 60
    return am or pm


def bucket_ratio_series(today_buckets, hist_buckets):
    import pandas as pd

    rows = []
    hist_by_bucket = hist_buckets.groupby("bucket")["Volume"]
    for _, row in today_buckets.sort_values("bucket").iterrows():
        b = row["bucket"]
        if not is_trading_bucket(b):
            continue
        v_t = float(row["Volume"])
        past = hist_by_bucket.get_group(b) if b in hist_by_bucket.groups else pd.Series(dtype=float)
        avg_p = float(past.mean()) if len(past) else float("nan")
        ratio = v_t / avg_p if avg_p and avg_p > 0 else float("nan")
        h, m = map(int, b.split(":"))
        ts = datetime.combine(row["date"], time(h, m))
        rows.append(
            {
                "bucket": b,
                "ts": ts,
                "vol_today": v_t,
                "vol_past_avg": avg_p,
                "bucket_ratio": ratio,
            }
        )
    return pd.DataFrame(rows)


def bucket_app_at_end(today_df, hist_df, bucket_minutes=5):
    """每个 5 分钟阶段结束时刻的 APP 累计量比"""
    import pandas as pd

    app = cumulative_app_ratio(today_df, hist_df)
    if app.empty:
        return pd.DataFrame()
    app = assign_bucket(app, bucket_minutes)
    end = app.groupby("bucket", as_index=False).last()
    end = end[end["bucket"].apply(is_trading_bucket)]
    return end[["bucket", "ts", "app_ratio"]]


def plot_chart(symbol, name, bucket_df, app_end_df, output_path, hist_days):
    plt, mdates, np, pd, _ = import_deps()

    fig, ax = plt.subplots(figsize=(12, 6), dpi=120)
    x = pd.to_datetime(bucket_df["ts"])
    y = bucket_df["bucket_ratio"].astype(float)

    colors = ["#e5484d" if v >= 1.0 else "#3b82f6" for v in y]
    ax.bar(x, y, width=0.0035, color=colors, alpha=0.85, label="5分钟阶段量比", align="center")

    if not app_end_df.empty:
        ax.plot(
            pd.to_datetime(app_end_df["ts"]),
            app_end_df["app_ratio"].astype(float),
            color="#f4b740",
            linewidth=2.2,
            marker="o",
            markersize=4,
            label="APP累计量比（阶段末）",
        )

    ax.axhline(1.0, color="#666666", linestyle="--", linewidth=1, alpha=0.7, label="量比=1")
    ax.set_xlim(x.min(), x.max())
    ax.set_title(f"{name} ({symbol})  5分钟阶段量比（开盘至今）", fontsize=14, pad=12)
    ax.set_xlabel("时间（北京）")
    ax.set_ylabel("量比")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.grid(True, alpha=0.3, linestyle=":")
    ax.legend(loc="upper right", fontsize=9)

    trade_date = bucket_df["ts"].iloc[0].strftime("%Y-%m-%d") if len(bucket_df) else ""
    note = (
        f"日期 {trade_date}  |  5分钟量比 = 该阶段成交量 ÷ 过去{hist_days}个交易日同时段均量\n"
        "APP累计量比 = 开盘至该阶段末均速 ÷ 历史同时刻均速（同花顺常见口径）"
    )
    fig.text(0.5, 0.02, note, ha="center", fontsize=8, color="#555555")

    fig.autofmt_xdate()
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def build_parser():
    p = argparse.ArgumentParser(description="5分钟阶段量比变化图")
    p.add_argument("--symbol", default="588200.SS", help="标的代码，如 588200.SS")
    p.add_argument("--name", default="588200科创芯片ETF", help="图表标题名称")
    p.add_argument("--bucket", type=int, default=5, help="阶段分钟数，默认5")
    p.add_argument("--lookback", type=int, default=7, help="历史分钟数据回溯天数（1m 数据建议≤7）")
    p.add_argument(
        "--output",
        default="",
        help="输出路径，默认 shared/charts/volume-ratio/",
    )
    return p


def main():
    args = build_parser().parse_args()
    plt, mdates, np, pd, yf = import_deps()

    bars = session_mask(load_minute_bars(yf, args.symbol, args.lookback))
    bars = assign_bucket(bars, args.bucket)
    bucketed = bucket_volume(bars)

    trade_dates = sorted(bucketed["date"].unique())
    if not trade_dates:
        raise SystemExit("无有效交易日数据")
    today_date = trade_dates[-1]
    hist_dates = [d for d in trade_dates if d < today_date]

    today_b = bucketed[bucketed["date"] == today_date].copy()
    hist_b = bucketed[bucketed["date"].isin(hist_dates)].copy()
    today_m = bars[bars["date"] == today_date].copy()
    hist_m = bars[bars["date"].isin(hist_dates)].copy()

    hist_days = len(hist_dates)
    if hist_days == 0:
        raise SystemExit("缺少历史交易日，无法计算量比基准（请增大 --lookback）")

    bucket_df = bucket_ratio_series(today_b, hist_b)
    app_end_df = bucket_app_at_end(today_m, hist_m, args.bucket)

    if bucket_df.empty:
        raise SystemExit("今日无 5 分钟桶数据")

    slug = args.symbol.replace(".", "_").lower()
    out = (
        Path(args.output)
        if args.output
        else SCRIPT_DIR.parent / "shared" / "charts" / "volume-ratio" / f"{slug}-volratio-5m-{today_date}.png"
    )

    plot_chart(args.symbol, args.name, bucket_df, app_end_df, out, hist_days)
    print(f"已生成: {out}")
    print(f"交易日: {today_date}  历史基准: {hist_days} 日")
    print("\n最近几个 5 分钟阶段量比:")
    tail = bucket_df.tail(6)[["bucket", "bucket_ratio", "vol_today", "vol_past_avg"]]
    for _, r in tail.iterrows():
        print(f"  {r['bucket']}  量比 {r['bucket_ratio']:.2f}  (今 {r['vol_today']:.0f} / 均 {r['vol_past_avg']:.0f})")


if __name__ == "__main__":
    main()
