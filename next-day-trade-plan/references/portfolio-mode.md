# 多持仓与关注清单（台股）

## 默认存储

关注清单保存在：

```text
~/.cursor/data/next-day-trade-plan/watchlist.json
```

可用环境变量 `NEXT_DAY_TRADE_PLAN_WATCHLIST` 指定其他路径。该文件包含个人持仓信息，不得提交到 GitHub、写入公开报告或输出账户总资产。

## 数据结构

```json
{
  "version": 1,
  "market": "TW",
  "updated_at": "2026-08-07T08:30:00+08:00",
  "positions": [
    {
      "code": "2330.TW",
      "name": "台积电",
      "cost": 900.0,
      "position_pct": 20.0,
      "shares": 1000,
      "max_risk_pct": 0.5,
      "enabled": true,
      "notes": "核心观察仓"
    }
  ]
}
```

必需字段为 `code`。`name` 推荐填写；`cost`、`position_pct`、`shares`、`max_risk_pct` 和 `notes` 可省略。`enabled=false` 表示保留记录但暂停早盘跟踪。

## 多持仓输入

用户可以一次输入：

```text
台积电 2330.TW，成本900，仓位20%；
联发科 2454.TW，成本1200，仓位15%；
环球晶 6488.TWO，未持有，加入观察。
```

也可以输入 Markdown 表格或 JSON 数组。标准化时：

- 代码统一为 `NNNN.TW`（上市）或 `NNNN.TWO`（上柜）；ETF 等可为 4–6 位数字代码。
- 缺少交易所后缀时必须要求用户确认，不得默认猜测。
- `position_pct` 使用 0–100 的百分数，不使用 0–1 小数。
- 未持有的观察标的使用 `position_pct=0`，不要虚构成本。
- 同一代码重复出现时，以本次输入覆盖旧记录，但保留未显式更新的旧字段。
- 总仓位超过 100% 时拒绝写入并要求修正。
- 股数默认按整张（1,000 股）理解；若用户明确为零股，需在 notes 标注。

## 命令

查看清单：

```bash
python3 scripts/watchlist.py list
```

检查某只股票是否已关注：

```bash
python3 scripts/watchlist.py contains 2330.TW
```

返回码为 0 表示已存在，返回码为 1 表示尚未加入；两种情况都会输出 JSON 结果。

增加或更新一只持仓：

```bash
python3 scripts/watchlist.py add --code 2330.TW --name 台积电 --cost 900 --position-pct 20 --shares 1000
```

批量导入 JSON 数组或带 `positions` 的对象：

```bash
python3 scripts/watchlist.py import-json positions.json
```

暂停、恢复或删除：

```bash
python3 scripts/watchlist.py disable 2330.TW
python3 scripts/watchlist.py enable 2330.TW
python3 scripts/watchlist.py remove 2330.TW
```

## 早盘简报规则

- 运行时间为交易日 08:30（Asia/Taipei）。调度可以按周一至周五触发，但任务内部必须通过台股交易日历过滤法定假日和临时休市。
- 使用前一已完成交易日的前复权日线；08:30 不把开盘前非正式报价当成日线收盘数据。
- 新闻窗口补充到 08:30，优先列出隔夜重大公告和产业事件。
- 按“失效位风险 > 重大利空 > 处置/全额交割/流动性风险 > 高仓位高波动 > 突破机会 > 普通观察”的顺序排列持仓。
- 输出关注数、成功数、失败数、行情截止日和新闻截止时间。
- 没有启用持仓时只提示如何添加，不生成空泛市场评论。
- 简报最后询问是否有新持仓需要加入，并说明新增后会立即分析、后续并入 08:30 推送。

## 交互闭环

1. 用户单独询问一只股票，先完成完整交易计划。
2. 若股票尚未关注，在答案最后询问是否加入；不要在分析前打断用户。
3. 用户确认后立即保存。没有成本和仓位时保存为 0 仓位观察标的。
4. 同一股票已在清单时不再重复询问。
5. 每日 08:30 组合简报最后再次开放“新增持仓”入口。
6. 用户发来一个或多个新持仓后，先保存，再立即生成新增标的计划，不等到第二天。
7. 新增分析结束后确认这些标的已进入后续每日组合推送。
