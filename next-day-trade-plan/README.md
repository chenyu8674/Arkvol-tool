# next-day-trade-plan（台股版）

将原 A 股次日交易计划 skill 适配为台湾股市（TWSE `.TW` / TPEx `.TWO`）。

## 保留的核心思路

- 仅用已完成交易日数据，输出条件式三情景盘前计划
- 前复权行情计算指标与关键价位，并与未复权末日核对
- 新闻影响评分后只调整情景概率/仓位，不替代价格确认
- 本地关注清单 + 交易日 08:30 组合简报

## 台股适配要点

- 数据源：`yfinance` 优先，上市未复权可降级证交所 `STOCK_DAY`；公告以 MOPS 为准
- 代码：`NNNN.TW` / `NNNN.TWO`
- 交易规则：整张 1,000 股、价格相关 tick、默认约 ±10% 涨跌幅、Asia/Taipei 交易日历

## 快速检查

```bash
pip install -r next-day-trade-plan/requirements.txt
python3 next-day-trade-plan/scripts/fetch_tw_bundle.py 2330.TW
python3 next-day-trade-plan/scripts/watchlist.py add --code 2330.TW --name 台积电 --position-pct 10
```
