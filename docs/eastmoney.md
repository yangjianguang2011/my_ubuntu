# 东方财富分析师数据采集

位置：`apps/eastmoney/`

采集东方财富「分析师指数」排行数据（Selenium 驱动 Chrome 无头模式），
产出 HTML 报表 + Excel。

---

## 1. 文件

| 文件 | 作用 |
|------|------|
| `eastmoney_analyst.py` | 入口（参数解析 + 流程编排） |
| `em_config.py` | 常量：期间 / 行业 / 表头字段（以真实页面结构为准） |
| `em_scraper.py` | 采集层（Selenium：列表页 → 选期间/行业 → 存详情页） |
| `em_report.py` | 后处理层（读 `manifest.json` → 解析详情页 → HTML/Excel） |
| `run_eastmoney.sh` | shell 入口（容器 / 定时任务用） |

采集与后处理之间用 **`manifest.json`** 关联（记录 rank / name / 详情页 URL 与文件路径），
后处理不再解析 HTML 文件名。

---

## 2. 用法

```bash
cd apps/eastmoney

bash run_eastmoney.sh                        # 内置采集组合（见脚本内 run_one 两行）
python3 eastmoney_analyst.py --list          # 列出可选的 slug（含中文对照）
python3 eastmoney_analyst.py -c electronics -p 2026_latest   # 命名参数（推荐）
python3 eastmoney_analyst.py -c all -p 12m
python3 eastmoney_analyst.py 0 0             # 兼容旧写法：<行业序号> <期间序号>
python3 eastmoney_analyst.py                 # 不带参数 → 交互式菜单
```

**参数一律用英文 slug**（便于在 shell 里书写，避免中文）：

- `-c/--category`：行业 slug，如 `electronics`、`nonferrous_metals`、`beauty_care`；默认 `all`
- `-p/--period`：期间 slug，见下表
- 也兼容中文名（`-c 电子`）与页面编码（`-c 270000`），但不推荐

**可选期间**（slug ↔ 中文 ↔ 页面按钮属性，取自真实页面 `#chart_type > li`）：

| slug | 中文（输出文件名用） | year | sort |
|---|---|---|---|
| `2026_latest` | 2026 最新排行 | 2026 | YEAR_YIELD |
| `latest_total` | 最新总排行 | 1 | INDEX_VALUE |
| `3m` | 3个月排行 | 3 | YIELD_3 |
| `6m` | 6个月排行 | 6 | YIELD_6 |
| `12m` | 12个月排行 | 12 | YIELD_12 |
| `2025_yearly` | 2025年度排行 | 2025 | YEAR_YIELD |

`run_eastmoney.sh` 默认跑两个组合：`all 2026_latest` + `all 3m`。

---

## 3. 输出

```
<data_dir>/processed_YYYYMMDD_HHMMSS/     # 默认 /data/analyst_data（本机 → run/analyst_data）
├── manifest.json                         # 采集 ↔ 后处理的关联文件
├── ...（中间文件：列表页/详情页 HTML、CSV）
└── 最终产物（同级目录，文件名用中文便于阅读）：
    {类别}_{期间}_{YYYYMMDD}.xlsx         # 类别为「全部」时写作「全部类别」
    {类别}_{期间}_{YYYYMMDD}.html
```

---

## 4. 报告口径

HTML 报告的「数据摘要」区块已内嵌以下说明：

| 项 | 口径 |
|---|---|
| 数据来源 | 东方财富「分析师指数」列表页 → 逐个分析师详情页（Selenium 采集） |
| 记录范围 | 详情页两张表的全部数据行 —— `#news_table`（最新跟踪成分股）、`#history_table`（历史跟踪成分股） |
| 总记录数 | 两张表行数合计（每条 = 一位分析师 × 一只股票） |
| 分析师数量 | 本次成功提取到成份股的分析师**去重**计数 |
| 重点关注股票 | 只统计「最新跟踪」表；按被多少位**不同**分析师持有排序（同一分析师对同一股票只计一次），取前 20 |
| 价格列 | 平均/最高/最低成交价取自各分析师记录的「成交价格(前复权)」；「最新价格」取该股票第一条非空值 |

Excel 含「最新跟踪」/「历史跟踪」双工作表。

---

## 5. 配置

`apps/config.ini`：

```ini
[eastmoney]
dir = /root/apps/eastmoney
data_dir = /data/analyst_data
```

`run_eastmoney.sh` 自算脚本目录、直读 ini（原 `apps/config.sh` 已删除），
日志写入 `[paths] log_dir`（`/data/logs`）。

> ⚠️ 容器内需保证 `PYTHONPATH` 含 `/root/apps`（`docker-compose.yml` 已设）。
> 各脚本自身也做了 `sys.path` 引导，脱离 `PYTHONPATH` 直接
> `python apps/eastmoney/eastmoney_analyst.py` 也能 import `config`。

---

## 6. 依赖

```bash
pip3 install selenium webdriver-manager beautifulsoup4 lxml pandas openpyxl requests
```
