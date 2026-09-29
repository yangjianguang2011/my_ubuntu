# 📊 Data Fetchers - 数据获取模块

从各外部数据源/本地库获取金融数据，供监控、估值、选股与 Web 接口使用。

---

## 📁 文件列表

| 文件 | 功能 | 数据源 |
|------|------|--------|
| `stock_data_fetcher.py` | 股票实时行情 + 历史日K 编排 | `easyquotation`（实时）+ `stockdb_data_fetcher`（历史） |
| `stockdb_data_fetcher.py` | stockdb 本地引擎接入层（SDK 加载/连接、日K读取） | stockdb（宿主机 `:7899`） |
| `pool_data_fetcher.py` | 股票池 / 指数成分股（hs300 / zz500） | akshare 双源 + `cache.db`（3 天） |
| `fundamental_data_fetcher.py` | 财务数据：季报 ROE / 分红送配 / 营业收入 | akshare → `long_term_storage`（30 天） |
| `index_data_fetcher.py` | 指数数据 | akshare（中证/新浪） |
| `index_web.py` | 指数数据页 REST API（Blueprint） | — |
| `fund_data_fetcher.py` | 基金（场内 ETF/LOF）数据 | akshare（东方财富） |
| `fund_web.py` | 基金数据统计页 REST API（Blueprint） | — |
| `analyst_data_fetcher.py` | 分析师数据（口径为**年度排行**） | akshare（东方财富） |
| `analyst_web.py` | 分析师数据页 REST API（Blueprint） | — |

> 行业板块数据（`industry_data_fetcher.py`）与行业页**已下线**（akshare 行业接口失效）。

---

## 🔧 使用方法

### 股票数据

```python
from data_fetchers.stock_data_fetcher import get_stock_info

stock = {'code': '000001', 'name': '平安银行'}
info = get_stock_info(stock)
print(info)
```

### 历史日K（批量，推荐）

```python
from data_fetchers.stockdb_data_fetcher import get_raw

df = get_raw(['600519', '000001'], start='20250101', fq='qfq',
             fields='date,code,open,high,low,close,volume')
```

> 大批量取数**一次批量**，不要逐只调用。

### 指数成分股（统一入口）

```python
from data_fetchers.pool_data_fetcher import get_index_constituents

codes = get_index_constituents('hs300')     # 3 天缓存
```

### 基金数据

```python
from data_fetchers.fund_data_fetcher import get_fund_history

history = get_fund_history('510300', period='12M')
print(history)
```

### 指数数据

```python
from data_fetchers.index_data_fetcher import get_enhanced_index_data

data = get_enhanced_index_data('sh000300')
print(f"PE: {data['pe']}, PB: {data['pb']}")
```

---

## 📊 支持的数据类型

- **股票**：实时价格 / 涨跌幅 / 成交量额 / PE / PB / 总市值；历史日K（A股前复权）
- **基金**：单位净值 / 累计净值 / 历史净值 / 收益率
- **指数**：指数点位 / 涨跌幅 / PE·PB 估值 / 百分位
- **财务**：季报 ROE / 分红送配 / 营业收入（`long_term_storage`，30 天）
- **分析师**：年度排行数据

---

## ⚙️ 缓存策略

缓存**统一存 `cache.db`**（`core/cache_with_database.py`）：

- 短时缓存 → `stock_cache` / `index_cache` / `fund_cache` / `analyst_cache` 表
  （`stock` 3 分钟，其余 24 小时）
- 计算产物与低频数据 → `long_term_storage` 表（按 `module_type` 分组，`fetched_at` 自管 TTL）

**不再产生散落的 CSV/JSON 缓存文件。**

---

## ⚠️ 关键约定

- **指数成分股**统一走 `pool_data_fetcher.get_index_constituents()`：
  中证/上证系用 `index_stock_cons_csindex`，深交所系用 `index_stock_cons_sina`。
  ⚠️ 不要用 `index_stock_cons`（含重复行、去重后缺成员）。
- **历史日K**统一走 `stockdb_data_fetcher`（本地库）；**港股 stockdb 取不到，必须回退 akshare**。
- `HybridCache` 优先命中**进程内内存层**：手工删 SQLite 行不清内存，复测需换新进程。

---

## 🔗 相关文档

- [分析模块](../analyzers/README.md)
- [Stock Monitor 架构](../../../docs/stock_monitor.md)
- [NAS 部署说明](../../../docs/NAS部署说明.md)

---

**最后更新**: 2026-09-29
