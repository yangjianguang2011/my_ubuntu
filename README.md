# Ubuntu 自动化运维容器项目

这是一个基于 Ubuntu 22.04 的 Docker 容器项目，集成了多个自动化任务模块。

！这不是一个标准项目，一容器内整合多个服务，代码质量卑劣，仅个人使用。

---

## 🎯 核心模块

### 1. Crawlers - 爬虫模块

**位置**: `apps/crawlers/`

独立的爬虫模块，与 stock_monitor 解耦。

**子模块**:
- **xueqiu/** - 雪球大 V 文章抓取
- **eastmoney/** - 东方财富分析师数据采集


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

### 单独运行模块

#### 运行爬虫

```bash
# 雪球爬虫
cd apps/crawlers/xueqiu
bash run_xueqiu.sh

# 东方财富爬虫
cd apps/crawlers/eastmoney
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
| 每 8 小时 | 新闻爬虫 | apps/news |
| 每天 23:05 | IPTV 频道下载 | apps/iptv |
| 每天 23:10 | 雪球爬虫 | apps/crawlers/xueqiu |
| 每天 23:40 | 东方财富分析师 | apps/crawlers/eastmoney |

---

## 🌐 端口映射

| 端口 | 服务 | 说明 |
|------|------|------|
| 4400 | Nginx Web | 静态资源/报告 |
| 4401 | Stock Monitor | 股票监控 Web 界面 |
| 4422 | SSH | 远程管理 |
| 38789 | OpenClaw | 浏览器自动化 |

---

## 📁 数据持久化

| 挂载点 | 用途 |
|--------|------|
| `/data` | 主要数据存储 |
| `/paddle` | PaddleOCR 模型 |
| `/openclaw` | openclaw 持久化目录 |

---

## ⚠️ 安全说明

- SSH 服务允许 root 登录，密码为 `rootpassword`
- Ubuntu 用户密码为 `ubuntupass`
- 建议修改默认密码
- 建议限制 SSH 访问 IP
