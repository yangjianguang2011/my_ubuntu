# 📈 Analyzers - 分析模块

提供股票分析、趋势判断、回测等功能。

---

## 📁 文件列表

| 文件 | 功能 | 说明 |
|------|------|------|
| `trend_trading_analyzer.py` | 趋势交易分析 | 核心分析器 |
| `trend_analysis_visualizer.py` | 趋势可视化 | 图表生成 |
| `backtesting_engine.py` | 回测引擎 | 策略回测 |

---

## 🚀 使用方法

### 趋势分析

```python
from analyzers.trend_trading_analyzer import TrendTradingAnalyzer

analyzer = TrendTradingAnalyzer()
result = analyzer.analyze_stock_trend('000001', '平安银行')
print(result['report'])
```

### 回测

```python
from analyzers.backtesting_engine import BacktestingEngine

engine = BacktestingEngine()
result = engine.backtest('000001', start_date='2025-01-01')
print(f"收益率：{result['return_rate']}%")
```

---

## 📊 分析功能

### 趋势判断
- ✅ 均线排列分析
- ✅ 趋势方向识别
- ✅ 趋势强度评分
- ✅ 密集成交区识别

### 交易信号
- ✅ 突破信号
- ✅ 回踩信号
- ✅ 止损位计算
- ✅ 目标位计算

### 技术指标
- ✅ MA5/MA20/MA60/MA120
- ✅ 斜率计算
- ✅ 趋势稳定性
- ✅ 持续时间统计

---

## 🔗 相关文档

- [数据获取](../data_fetchers/)
- [报告生成](../reports/)
- [Web 应用](../web_app.py)

---

**最后更新**: 2026-03-15  
**维护人**: icode
