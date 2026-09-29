# stockdb 重要 API 说明（Python 调用）

> 本文档基于**本机实测**整理（2026-09-13，运行目录 `E:\work\code\stockdb`），覆盖常用/重要接口，
> 每个接口都附真实返回示例。更详尽的官方文档见 `调用方式/python/AI策略python开发接口文档.md`。

## 0. 运行前提与环境

1. 双击 `stockdb.exe` 启动本地服务（默认 `127.0.0.1:7899`）；数据用 `数据更新.exe` 同步。
2. Python 侧把 `pybao` 目录加入 `sys.path`，然后一行导入：

```python
import sys
sys.path.insert(0, r"E:/work/code/stockdb/pybao")
from stock_sdk import *      # 导出 rd / zb / bk / init / set_init 及各接口
```

3. 接口分两类：

| 类别 | 接口 | 说明 |
|---|---|---|
| **本地接口**（始终可用） | `rd.get / rd.vals / rd.keys`、`rd.get_data`、`rd.pipe`、`zb.get`、`bk.get` | 走本机数据，无额度限制 |
| **在线补充接口**（额度受限） | `get_index_stocks`、`get_all_securities`、`get_trade_days`、`get_security_info`、`get_fundamentals`、`get_price`、`get_bars`、`get_ticks`、`get_last_tick` 等 | 需在线服务（测试期/授权）。受限时返回**提示文本**或 `500`，务必做错误判断 |

> 实测提示文本（`get_index_stocks`）：`测试期超2000次，正式版将移除次数。批量无限制请求应使用本地stockdb。本接口是全量补充行情，不应被用于批量拉取，会影响他人使用。`

## 1. 初始化

```python
# 本地数据端点（默认即可，通常无需调用）
init(host="127.0.0.1", port=7899, socket_timeout=None, password=None, warm=True)

# 在线 API 返回模式（与 rd 本地连接无关）
set_init(df=False)   # 在线接口返回 list/dict（默认，推荐）
set_init(df=True)    # 在线接口返回 pandas.DataFrame（日期在索引）
```

## 2. rd：底层分层 K-V

`table:key:key2 -> value`，日K表 `日k`、分钟表 `分钟k`、私有数据在 `mydb/`。

| 调用 | 语义 | 返回 |
|---|---|---|
| `rd.get("日k", "600633", "20260625")` | 精确键 | `dict`（一条记录） |
| `rd.get("日k", "600633", "20260622<20260626")` | 范围（多键） | `QueryResult`；`r.vals()` 得 `[[key, [字段值...]], ...]` |
| `rd.vals("日k", "600633", "202606*")` | 匹配取值 | value 列表（`[...]` / `dict`） |
| `rd.keys("日k", "600633", "202606*")` | 只取键 | key 列表 |
| `rd.get("股票代码")` | 全市场代码 | `QueryResult`，按首位分组：`d['0'] d['1'] d['3'] d['5'] d['6'] d['9']` |

**实测：精确键返回完整字段 dict**

```python
rd.get("日k", "600633", "20260625")
# {'date': 20260625, 'code': '600633', 'name': '浙数文化', 'open': 10.45, 'high': 10.62,
#  'low': 10.37, 'close': 10.45, 'pre_close': 10.52, 'volume': 18031500, 'amount': 189010000,
#  'turnover': 1.42, 'pct_chg': -0.67, 'amplitude': 2.38, 'is_st': False, 'vol_ratio': 0.9,
#  'total_share': 1268074472, 'float_share': 1268074472, 'total_mv': 13251000000,
#  'float_mv': 13251000000, 'pe_ttm': 22.5, 'pb': 1.3}
```

**实测：区间查询返回 `QueryResult`（含取值方式）**

```python
r = rd.get("日k", "600633", "20260622<20260626")
r          # QueryResult [['日k:600633:20260626', {...}], ['日k:600633:20260625', {...}], ...]
r.vals()   # 位置数组：[['日k:600633:20260624', [20260624, '600633', '浙数文化', 10.79, ...]], ...]
r[0] / r[:1]   # QueryResult 为 list-like，可按整数索引 / 切片
```

**实测：全市场代码（按分组键取值）**

```python
d = rd.get("股票代码")
d['6'][:4]   # ['600000', '600004', '600006', '600007']   沪市
d['0'][:4]   # ['000001', '000002', '000004', '000006']   深市主板
# 分组键实测：['0', '1', '3', '5', '6', '9']
```

**实测：分钟K（精确到分钟键）**

```python
rd.get("分钟k", "600633", "20260626093*")
# [['分钟k:600633:20260626093100', {'code': '600633', 'date': 20260626093100, 'open': 10.33,
#   'close': 10.21, 'high': 10.33, 'low': 10.21, 'volume': 311600, 'amount': 3190073}], ...]
```

> 私有数据写入：`rd.set("我的数据", "600633", "20270101", {...})`（落 `mydb/`）；批量读写用 `rd.pipe()`。

## 3. rd.get_data：加工后的行情接口（最常用）

```python
data = rd.get_data(
    code,                 # 必须：'600633' 或 ['600633', '600422']
    start=None,           # 可选：8位(YYYYMMDD) 或 14位 或 'N'(至今)
    end=None,             # 可选：同上；不要只给 end
    frequency="1d",       # 1d / 1m / 5m / 15m / 30m / 60m / 1w / 1M
    fields=None,          # None=全字段；或 "date,code,close" / ["date","close"]
    limit=None,           # 每条最大记录数
    desc=False,           # True=时间降序
    as_df=False,          # True 返回 pandas.DataFrame
    fq="qfq",             # qfq 前复权 / hfq 后复权 / None 不复权
)
```

**实测：`fields` + `as_df=True`**

```python
g = rd.get_data(["600633"], start="20260622", end="20260624", frequency="1d",
                fq="qfq", fields="date,code,name,close,pb,pe_ttm,turnover", as_df=True)
# shape=(3, 7)  cols=['code','date','name','close','pb','pe_ttm','turnover']
# [{'code': '600633', 'date': 20260622, 'name': '浙数文化', 'close': 11.07, 'pb': 1.3488, 'pe_ttm': 23.8377, 'turnover': 1.8827},
#  {'code': '600633', 'date': 20260623, 'name': '浙数文化', 'close': 10.74, 'pb': 1.3086, 'pe_ttm': 23.1271, 'turnover': 1.5473},
#  {'code': '600633', 'date': 20260624, 'name': '浙数文化', 'close': 10.52, 'pb': 1.31,   'pe_ttm': 22.65,   'turnover': 1.74}]
```

**实测：多代码、不传 `fields` → `dict{code: [dict, ...]}`**

```python
rd.get_data(["600633", "600422"], start="20260624", end="20260624", fq=None)
# {'600633': [{'date': 20260624, 'code': '600633', 'name': '浙数文化', 'open': 10.79, 'high': 10.83,
#              'low': 10.33, 'close': 10.52, 'pre_close': 10.74, 'volume': 22115000, 'amount': 233130000,
#              'turnover': 1.74, 'pct_chg': -2.05, 'amplitude': 4.66, 'is_st': False, 'vol_ratio': 1.16,
#              'total_share': 1268074472, 'float_share': 1268074472, 'total_mv': 13340000000,
#              'float_mv': 13340000000, 'pe_ttm': 22.65, 'pb': 1.31}],
#  '600422': [ {...} ]}
```

> 注意：传了 `fields` 时返回**位置数组**（单字段也是 `[[v], ...]`）；多代码 + `as_df=True` 返回**合并的一张表**（含 `code` 列），不是 `{code: DataFrame}`；`fields` 的列顺序按库内字段，不保证与传入顺序一致。

### 3.1 日K字段（21 个，实测）

```text
date, code, name, open, high, low, close, pre_close,
volume, amount, turnover, pct_chg, amplitude, is_st, vol_ratio,
total_share, float_share, total_mv, float_mv, pe_ttm, pb
```

- `date` 为 `int`（如 `20260625`）；`pe_ttm`、`pb`、`turnover`、`total_mv` 等估值/规模字段**本地可得**，适合估值类因子。

### 3.2 查询语法（Key 表达式）

```text
精确      rd.get("日k", "600633", "20260625")
范围      rd.get("日k", "600633", "20260620<20260626")   # 顺序用 < 或 >
前缀/通配 rd.vals("日k", "600633", "202606*")
至今      rd.get_data("600633", start="20260625", end="N")
截取      rd.vals("日k", "600633", "*")[-3:]
```

## 6. zb.get：批量技术指标（39 指标 + 5 指数）

```python
zb.get(name, codes=None, original=None, start=None, end=None, frequency="day",
       method=1, base=1000.0, fq="qfq", fields=None, n=None, cross=False)
```

**实测：MACD**

```python
zb.get("macd", ["600633"], start="20260601", end="20260610", frequency="1d", fq="qfq")
# {'600633': [{'date': 20260601, 'dif': 0.0, 'dea': 0.0, 'macd': 0.0},
#             {'date': 20260602, 'dif': -0.013, 'dea': -0.003, 'macd': -0.02},
#             {'date': 20260603, 'dif': -0.031, 'dea': -0.008, 'macd': -0.046}, ...]}
```

- 支持的指标：`ma, ema, sma, wma, dma, std, sum, hhv, llv, ref, macd, kdj, rsi, wr, bias, boll, psy, cci, atr, bbi, dmi, taq, ktn, trix, vr, cr, emv, dpo, brar, dfma, mtm, mass, roc, expma, obv, mfi, asi, xsii, zhishu`
- 参数 `n`：`ma`→`5` 或 `'5,10,20'`；`macd`→默认 12/26/9；`kdj`→默认 9/3/3；`rsi`→`24`；`boll`→`'20,2'`；`bias`→`'6,12,24'`。
- 指数：`zb.get("zhishu", codes, ..., method=1, base=1000)`；`method`：1 等权 / 2 流通市值 / 3 成交额 / 4 成交量 / 5 总市值（`method=2/5` 仅 `1d`）。
- 直接数组函数（不读库）：`zb.MACD(close, 12, 26, 9)`、`zb.KDJ(close, high, low, 9, 3, 3)`、`zb.CROSS(dif, dea)`。

## 7. bk.get：板块与股票双向映射

```python
bk.get(x=None, category=None, fields=None)
# category: 0 概念 / 1 申万一级 / 2 申万二级 / 3 申万三级
```

**实测**

```python
bk.get("600633", 1)
# [{'code': '801760.SL', 'name': '传媒', 'source': 'sw', 'type': 'sw_1',
#   'group': '申万行业指数列表', 'category': '申万一级'}]

bk.get("600633", 0, "name")[:5]          # ['AIGC概念', 'AI应用', 'AI智能体', 'AI视频', 'DeepSeek概念']
bk.get("5G", 0, "symbols")               # ['000016', '000049', '000063', ...]  板块→成分
bk.get(category=1, fields="name,code")   # [['交通运输','801170.SL'], ['休闲服务','801210.SL'], ['传媒','801760.SL'], ...]
```

- 允许字段：`code, name, source, type, group, category, symbols`；多字段按顺序返回**位置数组**。

## 8. 在线补充接口（需额度/授权，务必容错）

```python
from stock_sdk import set_init, get_index_stocks, get_all_securities, get_trade_days, get_fundamentals, query, cash_flow

# 统一错误检查（在线接口失败时可能返回 {'error': ...} 或抛异常）
def require(r):
    if isinstance(r, dict) and r.get("error"):
        raise RuntimeError(r["error"])
    return r

# 指数成分（实测：当前受限，返回提示文本 str）
get_index_stocks("000300.SH")

# 交易日历 / 证券信息（实测：当前 500）
require(get_trade_days(end_date="2026-08-06", count=20))
require(get_security_info("600633"))

# 全市场证券表（df=True 时代码在索引）
set_init(df=True)
require(get_all_securities(types=["stock"], date="2026-08-06"))

# 财务（代码带后缀；statDate 为财报期）
q = query(cash_flow).filter(cash_flow.code == "000001.XSHE")
require(get_fundamentals(q, statDate="2024q4"))

# 在线行情/Tick（单代码、小 count）
require(get_price("000001", end_date="2026-08-06", count=20, frequency="daily",
                  fields=["open", "high", "low", "close", "volume", "money"]))
require(get_bars("000001", count=20, unit="1d",
                 fields=["date", "open", "high", "low", "close", "volume"], end_dt="2026-08-06"))
require(get_last_tick("000001", count=10))
```

**当前实测状态（2026-09-13）**

| 接口 | 结果 |
|---|---|
| `get_index_stocks("000300.SH")` | 返回提示文本 `str`：`测试期超2000次，正式版将移除次数。批量无限制请求应使用本地stockdb。…` |
| `get_trade_days(...)` / `get_security_info(...)` | `RuntimeError: Server returned status error: 500 Internal Server Error` |
| 本地 `rd.*` / `zb.get` / `bk.get` | **正常**（不受影响） |

其余已导出在线接口（签名不可靠反射，按需小查询）：`get_all_trade_days, get_industry, get_concepts, get_industries, get_concept_stocks, get_industry_stocks, get_index_weights, get_extras, get_money_flow, get_mtss, get_margincash_stocks, get_marginsec_stocks, get_fundamentals_continuously, get_fund_info, get_valuation, get_billboard_list, get_locked_shares, get_factor_values, get_factor_kanban_values, get_index_style_exposure, get_dominant_future, get_future_contracts`。

## 9. 使用红线（官方文档强调）

1. **大批量历史行情用本地 `rd`**，不要用在线接口逐股拉取（远程体验服务禁止大批量分钟数据，否则封禁设备）。
2. 全市场查询用**前缀/服务端筛选**（如 `rd.vals("日k", "6*", "20260625")`），不要数千次独立请求。
3. 批量写入私有数据用 `rd.pipe()`；不要逐条写。
4. `all` 不是通配符；匹配用 `*`。
5. 不要只传 `end`（不会被当作"从最早到 end"）。
6. 单字段 `fields` 返回 `[[v], ...]`，不是 `[v, ...]`。

## 10. 附：HTTP 接口（浏览器 / Excel / JS）

```text
http://127.0.0.1:7899/?cmd=vals&t=日k&k1=key:600633&k2=fwd:20260620,20260626
```

详见 `调用方式/http/`、`调用方式/excel/`、`调用方式/ai_mcp/`（MCP 服务）。
