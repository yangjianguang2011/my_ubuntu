# Ubuntu 自动化运维容器项目

这是一个基于 Ubuntu 22.04 的 Docker 容器项目，集成了多个自动化任务模块。

---

## 📁 项目结构

```
my-ubuntu/
├── 📄 Dockerfile              # Docker 镜像构建
├── 📄 docker-compose.yml      # Docker Compose 配置
├── 📄 nginx.conf              # Nginx 配置文件
├── 📄 default                 # Nginx 站点配置
├── 📄 README.md               # 项目说明
│
├── 📁 crawlers/               # 🕷️ 爬虫模块（独立）
│   ├── 📁 spiders/            # 股票爬虫
│   │   ├── xueqiu_scraper.py      # 雪球大 V 文章抓取
│   │   ├── eastmoney_analyst.py   # 东方财富分析师数据
│   │   └── generate_html_reports.py # HTML 报告生成
│   ├── 📁 iptv/               # IPTV 频道管理
│   └── 📁 news/               # 新闻爬虫
│
├── 📁 stock_monitor/          # 📈 股票监控系统（主项目）
│   ├── 📁 data_fetchers/      # 数据获取模块
│   ├── 📁 analyzers/          # 分析模块
│   ├── 📁 utils/              # 工具模块
│   ├── 📁 scripts/            # 辅助脚本
│   ├── 📁 config/             # 配置文件
│   ├── web_app.py             # Web 应用入口
│   └── stock_monitor.py       # 监控引擎
│
├── 📁 tests/                  # 🧪 测试用例
├── 📁 docs/                   # 📚 文档中心
└── 📁 run/                    # 运行时目录
```

---

## 🎯 核心模块

### 1. Crawlers - 爬虫模块

**位置**: `crawlers/`

独立的爬虫模块，与 stock_monitor 解耦。

**功能**:
- ✅ 雪球大 V 文章抓取
- ✅ 东方财富分析师数据采集
- ✅ HTML 报告自动生成
- ✅ IPTV 频道下载管理
- ✅ 新闻爬虫

**文档**: [crawlers/README.md](crawlers/README.md)

---

### 2. Stock Monitor - 股票监控系统

**位置**: `stock_monitor/`

主项目，提供股票监控、数据分析、报警通知等功能。

**功能**:
- ✅ 实时股价监控（A 股/港股）
- ✅ 价格/涨跌幅报警
- ✅ 趋势交易分析
- ✅ 回测引擎
- ✅ Web 管理界面
- ✅ 多渠道通知推送

**文档**: [stock_monitor/README.md](stock_monitor/README.md)

---

### 3. Tests - 测试用例

**位置**: `tests/`

包含所有模块的测试用例。

**文档**: [tests/README.md](tests/README.md)

---

### 4. Docs - 文档中心

**位置**: `docs/`

包含项目分析报告、技术文档等。

**文档**: [docs/README.md](docs/README.md)

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
cd crawlers/spiders
bash run_xueqiu.sh

# 东方财富爬虫
cd crawlers/spiders
bash run_eastmoney.sh

# IPTV
cd crawlers/iptv
python3 download_m3u.py

# 新闻爬虫
cd crawlers/news
bash run.sh
```

#### 运行股票监控

```bash
cd stock_monitor

# Web 界面
python3 web_app.py

# 仅监控
python3 stock_monitor.py
```

---

## 📊 定时任务

系统预设了以下定时任务（通过 crontab）：

| 时间 | 任务 | 模块 |
|------|------|------|
| 每天 01:00 | 股票监控检查 | stock_monitor |
| 每天 05:00 | 雪球爬虫 | crawlers/spiders |
| 每天 23:00 | IPTV 频道下载 | crawlers/iptv |
| 每天 23:00 | 东方财富分析师 | crawlers/spiders |
| 每 8 小时 | 新闻爬虫 | crawlers/news |

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
- [Crawlers 说明](crawlers/README.md)
- [Stock Monitor 说明](stock_monitor/README.md)
- [测试用例说明](tests/README.md)

---

## 🔧 维护指南

### 更新代码

```bash
# 进入容器
docker exec -it my_ubuntu bash

# 更新代码
cd /root/stock_monitor
git pull

# 重启服务
docker-compose restart
```

### 查看日志

```bash
# 应用日志
docker exec my_ubuntu tail -f /var/log/stock_monitor.log

# 爬虫日志
docker exec my_ubuntu tail -f /var/log/cron.log
```

### 备份数据

```bash
# 备份配置
docker cp my_ubuntu:/root/stock_monitor/config ./backup/

# 备份数据
docker cp my_ubuntu:/data ./backup/
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

- 项目路径：`/home/jgyang/.openclaw/workspace/my-ubuntu`
- 容器名称：`my_ubuntu`

---

**最后更新**: 2026-03-15  
**维护人**: icode
