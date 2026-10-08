# Ubuntu 自动化运维容器项目

这是一个基于 Ubuntu 22.04 的 Docker 容器项目，集成了多个自动化任务模块。

！这不是一个标准项目，一容器内整合多个服务，代码质量卑劣，仅个人使用。

---

## 🎯 核心模块

### 1. 爬虫模块

**位置**: `apps/xueqiu_api/`、`apps/eastmoney/`（原 `apps/crawlers/` 已拆分到 apps 下）

独立的爬虫模块，与 stock_monitor 解耦。

**子模块**:
- **apps/xueqiu_api/** - 雪球大 V 文章抓取（接口版：Chrome + JSON 接口）
- **apps/eastmoney/** - 东方财富分析师数据采集


---

### 2. IPTV - IPTV 频道管理

**位置**: `apps/iptv/`

IPTV 播放列表下载和管理。

**功能**:
- ✅ M3U 播放列表下载
- ✅ 频道检查过滤

---

### 3. News - 新闻爬虫

**位置**: `apps/news/`

新闻数据爬取和存储。

---

### 4. Stock Monitor - 股票监控系统

**位置**: `apps/stock_monitor/`

主项目，提供股票监控、数据分析、报警通知等功能。

**功能**:
- ✅ 实时股价监控（A 股/港股）
- ✅ 价格/涨跌幅报警
- ✅ 趋势交易分析
- ✅ Web 管理界面
- ✅ 多渠道通知推送

---

## 🚀 快速开始

### 使用 Docker Compose

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

> 功能开关（默认关闭，代码保留）：`ENABLE_OPENCLAW`、`ENABLE_TELEGRAM`。
> 开启 OpenClaw 需重建镜像：`ENABLE_OPENCLAW=1 docker compose build && docker compose up -d`。

### 单独运行模块

#### 运行爬虫

```bash
# 雪球爬虫（接口版）
cd apps/xueqiu_api
bash run_xueqiu.sh

# 东方财富爬虫
cd apps/eastmoney
bash run_eastmoney.sh

# IPTV
cd apps/iptv
python3 download_m3u.py

# 新闻爬虫
cd apps/news
bash run.sh
```

#### 运行股票监控

```bash
cd apps/stock_monitor

# Web 界面
python3 start_app.py
```

---

## 📊 定时任务

系统预设了以下定时任务（通过 crontab）：

| 时间 | 任务 | 模块 |
|------|------|------|
| 每 8 小时（整点） | 新闻爬虫 | apps/news |
| 每天 23:00 | IPTV 频道下载 | apps/iptv |
| 每天 23:10 | 雪球爬虫 | apps/xueqiu_api |
| 每天 23:20 | 东方财富分析师 | apps/eastmoney |

> 实际定义见 `configs/cron.d/myjobs`（容器内 `/etc/cron.d/myjobs`）。

---

## 🌐 端口映射

| 端口 | 服务 | 说明 |
|------|------|------|
| 4400 | Nginx Web | 静态资源/报告 |
| 4401 | Stock Monitor | 股票监控 Web 界面 |
| 4422 | SSH | 远程管理 |

---

## 📁 数据持久化

| 挂载点 | 用途 |
|--------|------|
| `/data` | 主要数据存储 |
| `/paddle` | PaddleOCR 模型 |

---

## ⚠️ 安全说明

- SSH 服务允许 root 登录，**密码请通过部署环境自行设置**（不要写进仓库）
- 建议使用强密码并限制 SSH 访问 IP
- **私有值（推送凭据、私有域名）只住在 NAS 宿主目录**，git 与镜像里都只有脱敏版：

  | 私有文件（不入库、不进镜像） | 宿主位置 | 仓库里的脱敏模板 |
  |---|---|---|
  | `config.ini` | `/vol1/1000/docker/my-ubuntu/apps/config.ini` | `apps/config.ini.example` |
  | `index.html` | `…/apps/stock_monitor/web_templates/index.html` | `…/index.html.example` |

  运行时由 `docker-compose.yml` 的 `volumes` 把这两个宿主真文件**挂载覆盖**容器内的脱敏版。
  所以：**重建容器/镜像不需要手动改回**；改私有值只改宿主那份 + 重启。
  改了真 `index.html` 后请同步更新 `index.html.example`（私有域名 → `*.example.com`）。
- `core/notification.py` **不再是私有文件**：它只从 `config.ini` 的 `[messaging]` 读值，可以正常入库/同步。
- 部署与重建细节见 [`docs/NAS部署说明.md`](docs/NAS部署说明.md)。

---

## 📚 文档

| 文档 | 内容 |
|------|------|
| [`docs/stock_monitor.md`](docs/stock_monitor.md) | 股票监控系统架构、核心模块、配置、运行 |
| [`docs/NAS部署说明.md`](docs/NAS部署说明.md) | NAS 部署/更新/运维、网络与防火墙、stockdb 同步 |
| [`docs/爬虫与采集模块.md`](docs/爬虫与采集模块.md) | 爬虫模块总览、共享配置、定时任务 |
| [`docs/xueqiu.md`](docs/xueqiu.md) · [`docs/eastmoney.md`](docs/eastmoney.md) · [`docs/iptv.md`](docs/iptv.md) · [`docs/news.md`](docs/news.md) | 各采集模块用法 |
| [`docs/stockdb_API.md`](docs/stockdb_API.md) | stockdb 本地引擎接口说明 |

> `docs/dev/` 是**开发资料**（长期记忆、规格、排查记录），**不纳入版本库**。
