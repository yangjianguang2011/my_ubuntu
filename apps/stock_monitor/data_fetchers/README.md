# 📊 Data Fetchers - 数据获取模块

负责从各种数据源获取金融数据。

---

## 📁 文件列表

| 文件 | 功能 | 数据源 |
|------|------|--------|
| `stock_data_fetcher.py` | 股票实时数据 | 新浪/腾讯 API |
| `fund_data_fetcher.py` | 基金数据 | 东方财富 |
| `index_data_fetcher.py` | 指数数据 | 中证指数/新浪 |
| `industry_data_fetcher.py` | 行业板块数据 | 东方财富 |
| `analyst_data_fetcher.py` | 分析师数据 | 内部整合 |
| `analyst_integration_service.py` | 分析师数据整合 | - |

---

## 🔧 使用方法

### 获取股票数据

```python
from data_fetchers.stock_data_fetcher import get_stock_info

stock = {'code': '000001', 'name': '平安银行'}
info = get_stock_info(stock)
print(info)
```

### 获取基金数据

```python
from data_fetchers.fund_data_fetcher import get_fund_history

history = get_fund_history('510300', period='12M')
print(history)
```

### 获取指数数据

```python
from data_fetchers.index_data_fetcher import get_enhanced_index_data

data = get_enhanced_index_data('sh000300')
print(f"PE: {data['pe']}, PB: {data['pb']}")
```

---

## 📊 支持的数据类型

### 股票数据
- ✅ 实时价格
- ✅ 涨跌幅
- ✅ 成交量/额
- ✅ 市盈率 (PE)
- ✅ 市净率 (PB)
- ✅ 总市值

### 基金数据
- ✅ 单位净值
- ✅ 累计净值
- ✅ 历史净值
- ✅ 收益率

### 指数数据
- ✅ 指数点位
- ✅ 涨跌幅
- ✅ PE/PB 估值
- ✅ 百分位

### 行业数据
- ✅ 行业排名
- ✅ 涨跌幅排行
- ✅ 成分股

---

## ⚙️ 缓存策略

```python
# 缓存时长配置
STOCK_CACHE_DURATION = 3 * 60      # 股票：3 分钟
FUND_CACHE_DURATION = 24 * 60 * 60  # 基金：24 小时
INDEX_CACHE_DURATION = 24 * 60 * 60 # 指数：24 小时
```

---

## 🔗 相关文档

- [爬虫模块](../spiders/)
- [分析模块](../analyzers/)
- [工具模块](../utils/)

---

**最后更新**: 2026-03-15  
**维护人**: icode
