# Stock Monitor 模块概览

本文件提供 `apps/stock_monitor` 的快速架构分析和实现说明，方便快速了解当前代码结构、运行流程、配置方式和核心模块。

---

## 1. 总体架构

`apps/stock_monitor` 是一个金融监控与分析模块，包含：

- `start_app.py`：启动入口，负责启动 Web 服务、股票监控主循环和缓存预热线程。
- `core/`：核心运行时模块，包含配置管理、监控逻辑、通知、Web API 和缓存。
- `data_fetchers/`：数据获取模块，负责从多个外部数据源拉取股票、基金、指数、行业、分析师数据。
- `analyzers/`：分析模块，包含回测、趋势分析、资金轮动、LPPL 等策略分析工具。
- `scripts/`：运维与辅助脚本，如消息推送、价格采集、报表生成、数据库查看等。

---

## 2. 启动流程

`start_app.py` 是主入口：

1. 读取基础配置并初始化日志。
2. 启动 `Flask` Web 服务，监听 `0.0.0.0:5001`。
3. 启动 `StockMonitor` 实例，进入股票监控循环。
4. 启动缓存预热线程，定期预加载分析师、行业、指数和基金数据。
5. 使用 `atexit` 注册清理函数，退出时同步配置管理器状态到文件。

---

## 3. 核心模块说明

### 3.1 `core/config_manager.py`

负责统一配置管理：

- 将股票配置、通知开关等**可变**状态保存在 SQLite 数据库 `config.db`。
- **检查间隔 / 开市时段**等极少变动的参数改由 `config.ini [stock_monitor]` 提供（页面不再提供修改入口）。
- 支持将配置异步同步到文件 `settings.json` 和 `stocks.json`。
- 提供观察者通知机制，`StockMonitor` 会订阅配置变更。
- 提供接口：
  - `get_check_interval()`（读 `config.ini`）
  - `get_market_times()`（读 `config.ini`）
  - `get_global_notification_enabled()`
  - `get_all_stocks()`
  - `add_stock()` / `update_stock()` / `delete_stock()`
  - `set_stock_notification_enabled()`

关键实现点：

- 配置数据库表：`system_settings` 和 `stock_config`。
- `_sync_to_file_loop()` 线程每 60 秒将变更写回 JSON 文件。
- `pending_changes` 队列用于缓存和合并变更。

### 3.2 `core/stock_monitor.py`

股票监控主逻辑：

- 初始化时读取配置管理器中的股票列表和检查间隔。
- 持续循环：
  - 判断当前是否为开市时间；
  - 在开市期间逐只检查股票；
  - 支持收盘后继续检查报告时间并清除报警状态。
- 单只股票检查逻辑 `check_single_stock()`。

主要报警类型：

- 低价警报
- 高价警报
- 关键价位警报
- 涨跌幅阈值警报
- 涨停 / 跌停警报

报警控制：

- 按 `alert_key` 防止重复通知；
- 使用指数级延迟重发：1h, 2h, 4h...
- 依赖全局开关 `global_notification_enabled` 和股票级 `notification_enabled`。

### 3.3 `core/notification.py`

统一消息推送模块：

- 使用统一消息服务 `SERVER`（默认 `https://your-message-server:5555`）。
- 支持：
  - `send_system_notification()`
  - `send_stock_alert()`
- 对不同警报类型构建富文本内容。
- `send_message()` 使用 GET 请求调用外部推送服务。

配置项来源：

- `message_server`
- `message_username`
- `message_token`
- `message_channel`

### 3.4 `core/web_app.py`

Web 管理界面 API：

- 管理监控股票：`GET /api/stocks`, `POST /api/stocks`, `PUT /api/stocks/<code>`, `DELETE /api/stocks/<code>`
- 获取实时股票数据：`GET /api/stocks/<code>/current_data`, `GET /api/stocks/current_data`
- 分析师数据接口：`GET /api/analyst/{focus_stocks,latest_tracking,updated_stocks,history_tracking}`

> **分析师页口径**：数据源为东方财富（经 akshare），口径为**年度收益率排行**
> （当前年前 100 名，与东财页面「最新排行」一致）。
> akshare 只有 `stock_analyst_rank_em(year)`（仅 year 参数）与 `stock_analyst_detail_em(...)`
> 两个接口，**没有 3/6/12 个月榜**，故页面只提供年度口径；
> 3/6/12 个月收益率仅作展示、不参与排序。

Web 应用静态文件和模板目录：

- `web_templates/`
- `web_static/`

前端可通过这些 API 管理股票配置并获取实时展示数据。

### 3.5 `core/cache_with_database.py`

多级缓存实现：

- 支持 `sqlite` 或 `hybrid` 缓存模式。
- `HybridCache` 包含：
  - 内存缓存
  - 二级 SQLite 缓存
- `LongTermStorage` 用于持久化缓存数据，表 `long_term_storage`。

缓存类型与默认时长：

- `stock`：3 分钟
- `industry`：24 小时
- `analyst`：24 小时
- `index`：24 小时
- `fund`：24 小时

---

## 4. 数据获取模块

`data_fetchers/` 负责从外部数据源获取金融数据，并返回给监控或 Web 接口使用。

### 4.1 核心文件

- `stock_data_fetcher.py`：实时股票数据，使用 `easyquotation` + `akshare`。
- `fund_data_fetcher.py`：基金数据。
- `index_data_fetcher.py`：指数数据。
- `analyst_data_fetcher.py`：分析师相关数据（口径为**年度排行**，详见上文说明）。

### 4.2 `stock_data_fetcher.py` 实现要点

- `determine_market_type(stock_code)`：根据代码长度判断是否为港股。
- A 股使用 `easyquotation.use("sina")` 获取行情；港股使用 `easyquotation.use("hkquote")`。
- 支持历史行情拉取，尝试多种数据源：
  - `akshare.stock_zh_a_hist`
  - `akshare.stock_zh_a_daily`
  - `akshare.stock_zh_a_hist_tx`
  - `easyquotation` daykline
- 使用缓存避免频繁重复请求。

### 4.3 现有文档

模块内已有文档：

- `apps/stock_monitor/data_fetchers/README.md`
- `apps/stock_monitor/analyzers/README.md`

---

## 5. 配置与运行

### 5.1 配置机制

统一配置模块为 `apps/config.py`：

- 支持环境变量 `CONFIG_FILE` 指向配置文件。
- 默认配置路径：容器/Linux 为 `/root/apps/config.ini`，Windows 为 `apps/config.ini`。
- 通过 `get_path(section, key, fallback)` 读取配置项。
- 支持 `STOCK_MONITOR_<SECTION>_<KEY>` 环境变量覆盖。
- **路径按平台解析**：`config.ini` 里写的是「容器内视角」绝对路径
  （`/data`、`/root/apps`、`/var/log`）。容器/Linux 原样使用；
  Windows 本机开发按 `[mount_point]` 映射到项目内
  （`/data` → `<项目根>/run`、`/var/log` → `<项目根>/logs`、`/root/apps` → `<项目根>`）。
- 支持 `${key}` 变量展开（引用同一段内的键），如 `[stockdb] pybao_dir = ${dir}/pybao`。

### 5.2 重要配置项

`apps/config.ini.example` 中的 `[stock_monitor]` 段：

- `database_dir`、`settings_file`、`stocks_file`、`cache_dir`
- 缓存时长：`stock_cache_timeout` / `default_cache_timeout` /
  `analyst_cache_timeout` / `index_cache_timeout` / `fund_cache_timeout`

`apps/config.py` 还提供：

- `stock_monitor_dir`、`stock_monitor_data_dir`
- 通用目录 `root_dir`、`data_dir`、`log_dir`

数据源 `[stockdb]` 段（stockdb 跑在宿主机，容器/Windows 统一走局域网 IP）：

- `host` / `port`（如 `<stockdb-host>:7899`）
- `dir` / `pybao_dir`（SDK 目录；`pybao` 内含 `stockdb.pyd`，非 pip 包）
- `api_url`（**可选**；stockdb 的「在线补充接口」需要它。当前留空 = 不可用，
  故指数成分股改走 akshare，见下）

### 5.3 缓存与数据源约定

- **缓存统一存 `cache.db`**（`core/cache_with_database.py`）：短时缓存用
  `stock_cache` / `index_cache` / `fund_cache` / `analyst_cache` 表，
  计算产物与低频数据用 `long_term_storage` 表（按 `module_type` 分组，
  `fetched_at` 自管 TTL）。**不再产生散落的 CSV/JSON 缓存文件。**
- **指数成分股**统一走 `data_fetchers/pool_data_fetcher.get_index_constituents()`：
  中证/上证系用 `index_stock_cons_csindex`（中证官网），深交所系用
  `index_stock_cons_sina`；结果缓存 3 天。⚠️ 不要用 `index_stock_cons`
  （新浪另一接口，含重复行、去重后缺成员）。
- **日K**统一走 `data_fetchers/stockdb_data_fetcher`（本地库）；大批量取数用
  `get_raw(codes, ...)` **一次批量**，不要逐只调用。

### 5.4 运行入口

在 `apps/stock_monitor` 目录下运行：

```bash
python start_app.py
```

程序会启动：

- `Flask` Web 服务：`http://0.0.0.0:5001`
- 股票监控主循环
- 缓存预热线程

---

## 6. 关键文件快速索引

| 文件 | 作用 |
|------|------|
| `start_app.py` | 启动入口，启动 Web 服务、监控和缓存预热 |
| `core/config_manager.py` | 配置管理、SQLite 持久化、JSON 同步 |
| `core/stock_monitor.py` | 股票监控主循环与报警逻辑 |
| `core/notification.py` | 消息推送与通知构建 |
| `core/web_app.py` | Web API 和前端管理接口 |
| `core/cache_with_database.py` | 缓存系统：内存 + SQLite |
| `data_fetchers/stock_data_fetcher.py` | 股票行情获取实现 |
| `data_fetchers/index_data_fetcher.py` | 指数数据获取 |
| `data_fetchers/fund_data_fetcher.py` | 基金数据获取 |
| `data_fetchers/pool_data_fetcher.py` | 指数成分股（akshare 双源 + cache.db） |
| `data_fetchers/fundamental_data_fetcher.py` | 财报 ROE / 分红 / 营收（cache.db 缓存） |
| `data_fetchers/analyst_data_fetcher.py` | 分析师数据获取 |
| `analyzers/picker_rules.py` | 选股指标 + 规则引擎（纯计算） |
| `analyzers/picker_runner.py` | 选股批量编排 + 快照（后台单例运行器） |
| `analyzers/picker_web.py` | 选股 REST API（`/api/picker/*`） |
| `web_templates/` | 前端页面模板 |
| `web_static/` | 前端静态资源 |

---

## 7. 注意点与改进建议

- `ConfigManager` 同时使用数据库和 JSON 文件，可能导致配置同步延迟。
- `StockMonitor` 以 `stock_code` 长度判断市场类型，存在特殊代码误判风险。
- 通知依赖外部 `your-message-server` 推送服务，外部可用性影响报警稳定性。
- 缓存策略默认以时长为主，未对实时行情波动时延进行更细粒度控制。
- 估值报告的「股票池」目前只覆盖沪深300/中证500；stockdb 本地库支持全 A 股，
  后续可考虑放开（见 `docs/` 与 `MEMORY.md` 的 backlog）。

---

## 8. 进一步阅读

- `apps/stock_monitor/data_fetchers/README.md`
- `apps/stock_monitor/analyzers/README.md`

---

文档生成于 2026-06-13；最近更新 2026-09-24（缓存统一入 `cache.db`、选股器并入 `analyzers/`）。
