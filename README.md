# Ubuntu 自动化运维容器项目

这是一个基于 Ubuntu 22.04 的 Docker 容器项目，集成了多个自动化任务模块。

---

## 📁 项目结构

```
my-ubuntu/
├── 📄 Dockerfile              # Docker 镜像构建
├── 📄 docker-compose.yml      # Docker Compose 配置
├── 📄 start_container.sh      # 容器启动脚本
├── 📄 README.md               # 项目说明
│
├── 📁 apps/                   # 📦 应用模块目录
│   ├── 📄 config.ini          # 应用配置文件
│   ├── 📄 config.py           # Python 配置模块
│   ├── 📄 config.sh           # Shell 配置脚本
│   │
│   ├── 📁 crawlers/           # 🕷️ 爬虫模块
│   │   ├── 📁 xueqiu/         # 雪球爬虫项目
│   │   │   ├── xueqiu_scraper.py
│   │   │   ├── xueqiu_utils.py
│   │   │   └── run_xueqiu.sh
│   │   │
│   │   ├── 📁 eastmoney/      # 东方财富爬虫项目
│   │   │   ├── eastmoney_analyst.py
│   │   │   └── run_eastmoney.sh
│   │   │
│   │   └── 📄 README.md
│   │
│   ├── 📁 iptv/               # IPTV 频道管理
│   │   └── download_m3u.py    # M3U 播放列表下载
│   │
│   ├── 📁 news/               # 新闻爬虫
│   │   └── crawl_save_news.py # 新闻数据爬取
│   │
│   └── 📁 stock_monitor/      # 📈 股票监控系统（主项目）
│       ├── 📁 data_fetchers/  # 数据获取模块
│       ├── 📁 analyzers/      # 分析模块
│       ├── 📁 utils/          # 工具模块
│       ├── 📁 scripts/        # 辅助脚本
│       ├── 📁 web_templates/  # Web 模板
│       ├── 📁 web_static/     # 静态资源
│       └── start_app.py       # Web 应用入口
│
├── 📁 configs/                # ⚙️ 系统配置目录
│   ├── 📄 nginx.conf          # Nginx 配置文件
│   ├── 📄 default             # Nginx 站点配置
│   ├── 📄 default.conf        # Nginx 默认配置
│   └── 📄 supervisord.conf    # Supervisor 配置
│
├── 📁 docs/                   # 📚 文档中心
├── 📁 tests/                  # 🧪 测试用例
└── 📁 run/                    # 运行时目录（容器挂载为 /data）
```

---

## 🎯 核心模块

### 1. Crawlers - 爬虫模块

**位置**: `apps/crawlers/`

独立的爬虫模块，与 stock_monitor 解耦。

**子模块**:
- **xueqiu/** - 雪球大 V 文章抓取
- **eastmoney/** - 东方财富分析师数据采集

**文档**: [apps/crawlers/README.md](apps/crawlers/README.md)

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
- ✅ 回测引擎
- ✅ Web 管理界面
- ✅ 多渠道通知推送

**文档**: [apps/stock_monitor/README.md](apps/stock_monitor/README.md)

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

---

## 📚 相关文档

### 项目分析
- [项目结构分析报告](docs/PROJECT_STRUCTURE_ANALYSIS.md)
- [股票监控业务分析](docs/STOCK_MONITOR_BUSINESS_ANALYSIS.md)
- [项目全面分析](docs/PROJECT_ANALYSIS_REPORT.md)

### 技术文档
- [线程安全分析](docs/THREAD_SAFETY_ANALYSIS.md)
- [代码格式指南](docs/CODE_FORMAT_GUIDE.md)
- [清理报告](docs/CLEANUP_REPORT.md)

### 模块文档
- [Crawlers 说明](apps/crawlers/README.md)
- [Stock Monitor 说明](apps/stock_monitor/README.md)

---

## 🔧 维护指南

### 更新代码

```bash
# 进入容器
docker exec -it ubuntu_openclaw bash

# 更新代码
cd /root/apps/stock_monitor
git pull

# 重启服务
docker-compose restart
```

### 查看日志

```bash
# 应用日志
docker exec ubuntu_openclaw tail -f /var/log/stock_monitor/log.txt

# 爬虫日志
docker exec ubuntu_openclaw tail -f /var/log/cron/news.log
```

### 备份数据

```bash
# 备份配置
docker cp ubuntu_openclaw:/root/apps/config.ini ./backup/

# 备份数据
docker cp ubuntu_openclaw:/data ./backup/
```

---

## ⚠️ 安全说明

- SSH 服务允许 root 登录，密码为 `rootpassword`
- Ubuntu 用户密码为 `ubuntupass`
- 建议修改默认密码
- 建议限制 SSH 访问 IP

---

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 开启 Pull Request

---

## 📄 许可证

See [LICENSE](LICENSE) for details.

---

## 📞 联系方式

- 项目路径：`e:\work\code\my_ubuntu`
- 容器名称：`ubuntu_openclaw`

---

**最后更新**: 2026-03-30
**维护人**: icode
