# coding: utf-8
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from client import ArkvolClient, ArkvolClientError
from config import ArkvolConfigError, get_api_key


INDEX_CONFIG = {
    '上证50': {'code': '510050', 'slug': 'sse50'},
    '沪深300': {'code': '510300', 'slug': 'csi300'},
    '中证500': {'code': '510500', 'slug': 'csi500'},
    '中证1000': {'code': '159845', 'slug': 'csi1000'},
    '中证2000': {'code': '562660', 'slug': 'csi2000'},
    '科创50': {'code': '588000', 'slug': 'star50'},
    '创业板指': {'code': '159915', 'slug': 'chinext'},
}


def build_parser():
    parser = argparse.ArgumentParser(description='生成 A 股指数与贪婪值中文折线图（每个指数一张）')
    parser.add_argument('--api-key', help='临时覆盖配置文件中的 API Key')
    parser.add_argument('--config', help='API Key 配置文件路径，默认使用 ~/.arkvol/arkvol-entry.json')
    parser.add_argument('--base-url', default='https://arkvol.com')
    parser.add_argument('--days', type=int, default=30, help='绘制最近 N 个自然日内的交易日数据')
    parser.add_argument(
        '--output-dir',
        default=str(Path(__file__).resolve().parents[1] / 'shared' / 'charts' / 'per-index'),
        help='图片输出目录',
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
        raise ArkvolClientError(
            '缺少绘图库 matplotlib，请先执行：python3 -m pip install matplotlib'
        ) from exc

    preferred_fonts = ['WenQuanYi Micro Hei', 'Droid Sans Fallback', 'Noto Sans CJK SC', 'SimHei']
    installed = {f.name for f in fm.fontManager.ttflist}
    matched = [name for name in preferred_fonts if name in installed]
    plt.rcParams['font.sans-serif'] = matched + ['DejaVu Sans']
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['axes.unicode_minus'] = False
    return plt, mdates


def collect_series(payload, days):
    data = payload.get('data') if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise ArkvolClientError('Arkvol 返回格式错误：缺少 data 对象')

    items = data.get('items')
    series_all = data.get('series')
    if not isinstance(items, list) or not isinstance(series_all, list):
        raise ArkvolClientError('Arkvol 返回格式错误：缺少 items 或 series 序列')

    selected = {}
    for item, series in zip(items, series_all):
        index_name = item.get('index_name')
        if index_name not in INDEX_CONFIG or not isinstance(series, list):
            continue

        points = []
        for point in series:
            date_text = point.get('date')
            close = point.get('close')
            greed = point.get('greed')
            if not date_text or not isinstance(close, (int, float)) or not isinstance(greed, (int, float)):
                continue
            points.append(
                {
                    'date': datetime.strptime(date_text, '%Y-%m-%d').date(),
                    'date_text': date_text,
                    'close': float(close),
                    'greed_score': float(greed) * 100.0,
                }
            )

        points.sort(key=lambda x: x['date'])
        if points:
            selected[index_name] = points

    if not selected:
        raise ArkvolClientError('未找到可绘图的 A 股指数序列数据')

    latest = max(points[-1]['date'] for points in selected.values())
    start = latest - timedelta(days=max(days, 1))

    filtered = {}
    for index_name, points in selected.items():
        window = [point for point in points if point['date'] >= start]
        if window:
            filtered[index_name] = window
    return filtered


def plot_each_index(index_series, output_dir, plt, mdates):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    artifacts = []
    for index_name, points in index_series.items():
        code = INDEX_CONFIG[index_name]['code']
        slug = INDEX_CONFIG[index_name]['slug']
        filename = f'a-share-{slug}-{code}-index-greed.png'
        target = output / filename

        dates = [point['date'] for point in points]
        closes = [point['close'] for point in points]
        greed_scores = [point['greed_score'] for point in points]

        fig, ax_left = plt.subplots(figsize=(12, 5.8))
        ax_right = ax_left.twinx()

        left_line = ax_left.plot(
            dates,
            closes,
            color='#1f77b4',
            linewidth=2.0,
            label='指数收盘价',
        )[0]
        right_line = ax_right.plot(
            dates,
            greed_scores,
            color='#d62728',
            linewidth=2.0,
            label='贪婪值',
        )[0]

        ax_left.set_title(f'{index_name}（{code}）指数与贪婪值走势')
        ax_left.set_xlabel('日期')
        ax_left.set_ylabel('收盘价', color='#1f77b4')
        ax_right.set_ylabel('贪婪值（0-100）', color='#d62728')
        ax_right.set_ylim(0, 100)

        ax_left.grid(alpha=0.25)
        ax_left.tick_params(axis='y', colors='#1f77b4')
        ax_right.tick_params(axis='y', colors='#d62728')

        ax_left.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        ax_left.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.setp(ax_left.get_xticklabels(), rotation=30, ha='right')

        ax_left.legend([left_line, right_line], ['指数收盘价', '贪婪值'], loc='upper left')
        fig.tight_layout()
        fig.savefig(target, dpi=180)
        plt.close(fig)

        artifacts.append(str(target))
    return artifacts


def run(args):
    api_key = get_api_key(args.api_key, config_path=args.config)
    client = ArkvolClient(base_url=args.base_url, api_key=api_key)
    client.ensure_current_version()
    payload = client.fetch_page('alla', view='full')

    plt, mdates = import_matplotlib()
    index_series = collect_series(payload, args.days)
    chart_paths = plot_each_index(index_series, args.output_dir, plt, mdates)
    return json.dumps(
        {
            'charts': chart_paths,
            'count': len(chart_paths),
            'output_dir': str(Path(args.output_dir).resolve()),
            'days': args.days,
        },
        ensure_ascii=False,
        indent=2,
    )


def main(argv=None):
    try:
        print(run(build_parser().parse_args(argv)))
        return 0
    except (ArkvolConfigError, ArkvolClientError, ValueError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
