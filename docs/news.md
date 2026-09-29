# 新闻聚合爬虫

位置：`apps/news/`

抓取多个平台的热榜/新闻，按**频率词**过滤出自己关心的内容，生成 HTML/TXT 汇总，
并按需推送到飞书/钉钉/企业微信/Telegram/邮件/ntfy。

> 本模块基于开源项目 [TrendRadar](https://github.com/sansan0/TrendRadar)（脚本内 `VERSION = 3.0.5`），
> 针对本仓库做了**路径配置化**（去掉硬编码 `/data/...`，改走 `apps/config.py::get_path`）等改动。

---

## 1. 文件

| 文件 | 作用 |
|------|------|
| `crawl_save_news.py` | 主程序（抓取 → 频率词过滤 → 生成报告 → 推送） |
| `run.sh` | shell 入口（容器 / 定时任务用；自算目录、直读 ini、写日志） |
| `config/config.yaml` | 主配置：抓取间隔、报告模式、通知 webhook、权重、平台清单 |
| `config/frequency_words.txt` | 频率词表（关心/过滤的词组） |
| `requirements.txt` | 依赖清单 |

---

## 2. 用法

```bash
cd apps/news
bash run.sh                                   # 生产入口（定时任务用）
python3 crawl_save_news.py                    # 直接运行（需先 cd 到本目录）
```

本机（Windows）运行：

```powershell
& "E:\work\code\.venv\Scripts\python.exe" apps\news\crawl_save_news.py
```

> ⚠️ 必须在 `apps/news/` 目录下运行（默认配置路径是相对的 `config/config.yaml`），
> 或用 `CONFIG_PATH` 指定绝对路径。

---

## 3. 输出

```
<data_dir>/                          # 默认 /data/news（本机 → run/news）
└── <日期文件夹>/
    ├── 当日汇总.html                # daily 模式的当日汇总
    ├── 当前榜单汇总.html            # current 模式
    ├── 当日增量.html                # incremental 模式
    ├── <时间戳>.html                # 每次运行的报告
    ├── txt/<时间戳>.txt             # 纯文本版
    └── push_record_*.json           # 推送时间窗口的记录（用于 once_per_day）
```

---

## 4. 报告模式（`config.yaml` → `report.mode`）

| 模式 | 推送时机 | 显示内容 | 适用场景 |
|---|---|---|---|
| `daily` | 按时推送（默认每小时一次） | 当日所有匹配新闻 + 新增新闻区域 | 日报总结、全面了解当日热点 |
| `current` | 按时推送 | 当前榜单匹配新闻 + 新增新闻区域 | 实时热点追踪 |
| `incremental` | **有新增才推送** | 新出现的匹配频率词新闻 | 避免重复信息干扰 |

---

## 5. 配置

### 5.1 主配置 `apps/news/config/config.yaml`

- `crawler.request_interval`：请求间隔（毫秒，默认 2000）
- `crawler.enable_crawler`：`false` 直接停止程序
- `crawler.use_proxy` / `default_proxy`
- `report.mode` / `report.rank_threshold`（排名高亮阈值）
- `notification.*`：通知开关、分批大小、`push_window`（推送时间窗口）、各平台 webhook
- `weight.*`：`rank_weight` / `frequency_weight` / `hotness_weight`（合计 1）
- `platforms`：平台清单（`id` + `name`，注释掉的即未启用）

> ⚠️ **webhook 是敏感信息**，请勿提交到版本库。本项目 `config.yaml` 中 webhook 均为空，
> 生产上的真实值请通过环境变量注入（见下）或在 NAS 上单独维护。

### 5.2 环境变量覆盖

| 环境变量 | 作用 |
|---|---|
| `CONFIG_PATH` | 指定配置文件路径（默认 `config/config.yaml`） |
| `REPORT_MODE` | 覆盖 `report.mode` |
| `ENABLE_CRAWLER` | 覆盖 `crawler.enable_crawler`（`true`/`1`） |
| `ENABLE_NOTIFICATION` | 覆盖 `notification.enable_notification` |
| `FREQUENCY_WORDS_PATH` | 频率词表路径（默认 `config/frequency_words.txt`） |
| `PUSH_WINDOW_ENABLED` / `PUSH_WINDOW_START` / `PUSH_WINDOW_END` / `PUSH_WINDOW_ONCE_PER_DAY` / `PUSH_WINDOW_RETENTION_DAYS` | 推送时间窗口 |
| `FEISHU_WEBHOOK_URL` / `DINGTALK_WEBHOOK_URL` / `WEWORK_WEBHOOK_URL` / `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` / `EMAIL_FROM` / `EMAIL_PASSWORD` / `EMAIL_TO` 等 | 各通知渠道凭据 |

### 5.3 路径配置 `apps/config.ini`

```ini
[news]
dir = /root/apps/news
data_dir = /data/news
```

`run.sh` 自算脚本目录、直读 ini（不依赖 cwd），日志写入 `[paths] log_dir`
（`/data/logs`，实际文件 `/data/logs/cron/news.log`），运行结束后会把
`data_dir` 属主改为 `1000:1001`、权限 `777`。

---

## 6. 依赖

```bash
pip3 install requests pytz PyYAML fastmcp websockets
```

（见 `apps/news/requirements.txt`）

---

## 7. 定时任务

容器内 `/etc/cron.d/myjobs`（源文件 `configs/cron.d/myjobs`）：

```
0 */8 * * * root cd /root/apps/news && /bin/bash run.sh >> /data/logs/cron/news.log 2>&1
```

即**每 8 小时**运行一次。

---

## 8. 注意点

- `config/frequency_words.txt` 是本模块的**核心输入**（决定哪些新闻被选中）。
  仓库里的这份是空文件，生产环境请在 NAS 的 `apps/news/config/frequency_words.txt`
  维护实际词表，或用 `FREQUENCY_WORDS_PATH` 指向数据卷中的文件。
- 邮件推送的 SMTP 服务器按发件人域名自动识别（内置 gmail / qq / outlook / 163 / 126 / sina / sohu 等）。
