# 📈 Analyzers - 分析模块

股票分析、估值、选股、市场温度等**纯计算 + 编排**逻辑。

---

## 📁 文件列表

### 共享指标层

| 文件 | 功能 |
|------|------|
| `ma_indicators.py` | 共享技术指标：均线 `add_ma` / 排列 `is_*_arrangement` / 金叉 / 斜率 `slope_pct`·`slope_regression` / 乖离（**选股与趋势分析共用**） |
| `factor_utils.py` | 因子计算专用工具（numpy/pandas 依赖） |
| `factors_registry.py` | 轻量因子注册表（dict + dataclass） |

### 选股（条件注册表）

| 文件 | 功能 |
|------|------|
| `conditions.py` | **条件注册表** —— 技术面 6 条件 + 估值面 7 条件，`condition_catalog()` 供前端动态渲染 |
| `picker_rules.py` | 原「长周期均线趋势 + 回调买点」4 条件规则引擎（纯计算）+ `Params` |
| `picker_runner.py` | 批量编排：**技术面粗筛 → 估值面精筛** → 结果快照（后台单例运行器） |
| `picker_web.py` | 选股 REST API（`/api/picker/*`） |

### 估值

| 文件 | 功能 |
|------|------|
| `valuation_engine.py` | 估值报告引擎：`run_valuation()` 全量报告 / `compute_readings()` 轻量读数（供选股估值条件用，按天缓存） |
| `valuation_report.py` | 估值报告 JSON 构建器（供前端渲染） |
| `valuation_runner.py` | 估值报告后台运行器（单例） |
| `valuation_web.py` | 估值报告 REST API |
| `factor_valuation.py` | 估值因子：市赚率 / 盈利调节市净率 / 盈利调节市销率（单股，日频） |
| `factor_price_cycle.py` | 价格周期因子：均线偏离 / z 分数 / 距高点 / 动量 / RSI / 波动（6 项等权） |
| `factor_fusion.py` | 多因子融合：把估值维度读数融合成一个 0~1 的「融合读数」 |

### 其它

| 文件 | 功能 |
|------|------|
| `trend_trading_analyzer.py` | 趋势交易分析（K 线图表数据 + 报告） |
| `market_temperature.py` | 市场温度 / 水位（合并自 market_signal + market_level + market_report） |
| `market_runner.py` | 市场温度后台运行器（单例） |
| `fund_rotation_backtester.py` | 基金轮动回测（研究用，暂无调用方） |

---

## 🚀 使用方法

### 趋势分析

```python
from analyzers.trend_trading_analyzer import TrendTradingAnalyzer

analyzer = TrendTradingAnalyzer()
result = analyzer.analyze_stock_trend('000001', '平安银行')
print(result['report'])
```

### 条件注册表（选股）

```python
from analyzers.conditions import all_conditions, condition_catalog

for c in all_conditions():
    print(c.id, c.label, list(c.params))

catalog = condition_catalog()      # 供前端渲染：分组 + 参数元信息 + 默认值
```

### 估值轻量读数

```python
from analyzers.valuation_engine import compute_readings

readings = compute_readings('600519')     # 只算读数，不生成报告；当天缓存
```

---

## 📊 技术面条件（6 个）

| id | 名称 | 参数 |
|----|------|------|
| `structure` | 多头结构 | 价格高于慢线%、快线斜率下限%、斜率窗口、**快慢线最小间距%**（原「均线多头排列」已并入） |
| `golden_cross` | 金叉确认 | 回看根数、距金叉最小/最大根数 |
| `pullback` | 回踩买点 | 回踩距离区间、确认窗口、下影线穿越区间、中线破位容差 |
| `volume_shrink` | 缩量（软条件） | 回看根数、量比上限 |
| `ma_slope` | 快线斜率下限 | 窗口、斜率下限% |
| `bias_band` | 乖离带 | 哪条均线、乖离下限/上限% |

## 📊 估值面条件（7 个）

`val_pr`（市赚率 PR·日频隐含ROE）、`val_pr_adj`（修正市赚率 N×PR）、
`val_pb_adj_b`（盈利调节市净率·季报口径·主）、`val_pb_adj`（v1 日频）、
`val_pb`（市净率）、`val_pe_ttm`（市盈率 TTM）、`val_price_cycle`（价格周期位置）。

每个条件都有 `basis`（口径：`value` 绝对值 / `pct` 历史位置 0~1，**默认 `value`**）+ `threshold`。
多个条件之间是 **AND**（同时满足）。

---

## 🔗 相关文档

- [数据获取](../data_fetchers/README.md)
- [Stock Monitor 架构](../../../docs/stock_monitor.md)

---

**最后更新**: 2026-09-29
