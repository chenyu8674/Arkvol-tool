# coding: utf-8
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from client import ArkvolClient, ArkvolClientError
from config import ArkvolConfigError, get_api_key


FUND_CONFIG = {
    '513520': {'name': '华夏野村日经225 ETF', 'corr': 0.7335},
    '019455': {'name': '华泰柏瑞中韩半导体 ETF 联接 C', 'corr': 0.5779},
    '007339': {'name': '易方达沪深300ETF联接C', 'corr': 0.5085},
}


def build_parser():
    parser = argparse.ArgumentParser(description='绘制台湾加权指数与3支高相关基金一年走势')
    parser.add_argument('--api-key', help='临时覆盖配置文件中的 API Key')
    parser.add_argument('--config', help='API Key 配置文件路径，默认使用 ~/.arkvol/arkvol-entry.json')
    parser.add_argument('--base-url', default='https://arkvol.com')
    parser.add_argument(
        '--output-dir',
        default=str(Path(__file__).resolve().parents[1] / 'shared' / 'charts' / 'twii-corr'),
        help='图表与明细输出目录',
    )
    return parser


def import_matplotlib():
    try:
        import matplotlib

        matplotlib.use('Agg')
        import matplotlib.dates as mdates
        import matplotlib.font_manager as fm
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise ArkvolClientError('缺少 matplotlib，请先执行：python3 -m pip install matplotlib') from exc

    preferred_fonts = ['WenQuanYi Micro Hei', 'Droid Sans Fallback', 'Noto Sans CJK SC', 'SimHei']
    installed = {font.name for font in fm.fontManager.ttflist}
    matched = [name for name in preferred_fonts if name in installed]
    plt.rcParams['font.sans-serif'] = matched + ['DejaVu Sans']
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['axes.unicode_minus'] = False
    return plt, mdates


def extract_fund_series(payload):
    data = payload.get('data') if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise ArkvolClientError('Arkvol 返回格式错误：缺少 data 对象')

    items = data.get('items')
    series_all = data.get('series')
    if not isinstance(items, list) or not isinstance(series_all, list):
        raise ArkvolClientError('Arkvol 返回格式错误：缺少 items 或 series')

    code_to_series = {}
    for item, series in zip(items, series_all):
        code = str(item.get('fund_code') or '')
        if code not in FUND_CONFIG:
            continue

        if isinstance(series, dict):
            points = series.get('data') or []
        elif isinstance(series, list):
            points = series
        else:
            points = []

        rows = []
        for point in points:
            date_text = point.get('date') or point.get('trade_date')
            close = point.get('close')
            if close is None:
                close = point.get('close_price')
            if date_text and isinstance(close, (int, float)):
                rows.append((pd.to_datetime(date_text), float(close)))

        if rows:
            series_df = (
                pd.DataFrame(rows, columns=['date', 'close'])
                .drop_duplicates('date')
                .set_index('date')
                .sort_index()
            )
            code_to_series[code] = series_df['close']

    missing = [code for code in FUND_CONFIG if code not in code_to_series]
    if missing:
        raise ArkvolClientError(f'以下基金缺少时间序列数据：{",".join(missing)}')
    return code_to_series


def fetch_twii_close():
    history = yf.download('^TWII', period='2y', interval='1d', auto_adjust=False, progress=False)
    if history.empty:
        raise ArkvolClientError('无法获取台湾加权指数（^TWII）历史数据')

    if isinstance(history.columns, pd.MultiIndex):
        close_col = ('Close', '^TWII') if ('Close', '^TWII') in history.columns else history.columns[0]
        close_series = history[close_col].copy()
    else:
        close_series = history['Close'].copy()

    close_series.index = pd.to_datetime(close_series.index).tz_localize(None)
    return close_series.rename('台湾加权指数')


def build_dataset(fund_series, twii_close):
    frame = pd.concat(
        [
            fund_series['513520'].rename('513520'),
            fund_series['019455'].rename('019455'),
            fund_series['007339'].rename('007339'),
            twii_close.rename('twii'),
        ],
        axis=1,
        join='inner',
    ).dropna()
    if frame.empty:
        raise ArkvolClientError('基金与台湾加权指数没有可用的重叠交易日')

    end_date = frame.index.max()
    start_date = end_date - pd.Timedelta(days=365)
    window = frame[(frame.index >= start_date) & (frame.index <= end_date)].copy()
    if len(window) < 120:
        raise ArkvolClientError('近一年重叠交易日过少，无法稳定绘图')

    weight_sum = sum(item['corr'] for item in FUND_CONFIG.values())
    window['weighted_combo'] = (
        window['513520'] * FUND_CONFIG['513520']['corr']
        + window['019455'] * FUND_CONFIG['019455']['corr']
        + window['007339'] * FUND_CONFIG['007339']['corr']
    ) / weight_sum

    window['513520_norm_100'] = window['513520'] / window['513520'].iloc[0] * 100.0
    window['019455_norm_100'] = window['019455'] / window['019455'].iloc[0] * 100.0
    window['007339_norm_100'] = window['007339'] / window['007339'].iloc[0] * 100.0
    window['weighted_combo_norm_100'] = window['weighted_combo'] / window['weighted_combo'].iloc[0] * 100.0
    window['twii_norm_100'] = window['twii'] / window['twii'].iloc[0] * 100.0
    return window


def save_outputs(dataset, output_dir, plt, mdates):
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    png_path = target_dir / 'twii-top3-corr-1y.png'
    csv_path = target_dir / 'twii-top3-corr-1y.csv'

    export = dataset.copy()
    export.index = export.index.strftime('%Y-%m-%d')
    export.index.name = 'date'
    export.to_csv(csv_path, encoding='utf-8', lineterminator='\n')

    fig, ax_left = plt.subplots(figsize=(15, 8))
    ax_right = ax_left.twinx()

    line1 = ax_left.plot(dataset.index, dataset['513520'], label='513520 华夏野村日经225 ETF', linewidth=1.8)[0]
    line2 = ax_left.plot(dataset.index, dataset['019455'], label='019455 华泰柏瑞中韩半导体ETF联接C', linewidth=1.8)[0]
    line3 = ax_left.plot(dataset.index, dataset['007339'], label='007339 易方达沪深300ETF联接C', linewidth=1.8)[0]
    line4 = ax_left.plot(
        dataset.index,
        dataset['weighted_combo'],
        label='相关性加权组合线',
        linewidth=2.6,
        color='#111111',
    )[0]
    line5 = ax_right.plot(
        dataset.index,
        dataset['twii'],
        label='台湾加权指数',
        linewidth=2.0,
        linestyle='--',
        color='#d62728',
    )[0]

    ax_left.set_title('一年走势：三支高相关基金 vs 台湾加权指数（含相关性加权组合线）')
    ax_left.set_xlabel('日期')
    ax_left.set_ylabel('基金净值/价格')
    ax_right.set_ylabel('台湾加权指数点位')
    ax_left.grid(alpha=0.25)

    ax_left.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax_left.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.setp(ax_left.get_xticklabels(), rotation=30, ha='right')

    all_lines = [line1, line2, line3, line4, line5]
    all_labels = [line.get_label() for line in all_lines]
    ax_left.legend(all_lines, all_labels, loc='upper left', fontsize=9)

    note = (
        '加权组合线 = (513520×0.7335 + 019455×0.5779 + 007339×0.5085) / (0.7335+0.5779+0.5085)'
    )
    ax_left.text(0.01, 0.01, note, transform=ax_left.transAxes, fontsize=9, color='#333333')

    fig.tight_layout()
    fig.savefig(png_path, dpi=180)
    plt.close(fig)

    return png_path, csv_path


def run(args):
    api_key = get_api_key(args.api_key, config_path=args.config)
    client = ArkvolClient(base_url=args.base_url, api_key=api_key)
    client.ensure_current_version()
    payload = client.fetch_page('funds-greed', view='full')

    fund_series = extract_fund_series(payload)
    twii_close = fetch_twii_close()
    dataset = build_dataset(fund_series, twii_close)
    plt, mdates = import_matplotlib()
    png_path, csv_path = save_outputs(dataset, args.output_dir, plt, mdates)

    result = {
        'chart': str(png_path),
        'csv': str(csv_path),
        'start_date': dataset.index.min().strftime('%Y-%m-%d'),
        'end_date': dataset.index.max().strftime('%Y-%m-%d'),
        'trading_days': int(len(dataset)),
        'weights': {code: config['corr'] for code, config in FUND_CONFIG.items()},
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


def main(argv=None):
    try:
        print(run(build_parser().parse_args(argv)))
        return 0
    except (ArkvolConfigError, ArkvolClientError, ValueError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
