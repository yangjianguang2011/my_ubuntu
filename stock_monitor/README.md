# 📈 Stock Monitor - 股票监控系统

**主应用程序目录**

---

## 📁 目录结构

```
stock_monitor/
├── 📄 web_app.py              # ⭐ Web 应用入口 (Flask)
├── 📄 stock_monitor.py        # ⭐ 监控引擎主程序
├── 📄 start_app.py            # ⭐ 应用启动脚本
├── 📄 requirements.txt        # Python 依赖
├── 📄 requirements-dev.txt    # 开发依赖
├── 📄 settings.json           # 配置文件
│
├── 🕷️ 爬虫已移至: /crawlers/spiders/                # 🕷️ 爬虫模块
│   ├── xueqiu_scraper.py      # 雪球大 V 文章抓取
│   ├── xueqiu_utils.py        # 雪球爬虫工具
│   ├── eastmoney_analyst.py   # 东方财富分析师数据
│   ├── run_xueqiu.sh          # 雪球爬虫运行脚本
│   └── run_eastmoney.sh       # 东方财富爬虫运行脚本
│
├── 📁 data_fetchers/          # 📊 数据获取模块
│   ├── stock_data_fetcher.py  # 股票数据获取
│   ├── fund_data_fetcher.py   # 基金数据获取
│   ├── index_data_fetcher.py  # 指数数据获取
│   ├── industry_data_fetcher.py # 行业数据获取
│   ├── analyst_data_fetcher.py # 分析师数据获取
│   └── analyst_integration_service.py # 分析师数据整合
│
├── 📁 analyzers/              # 📈 分析模块
│   ├── trend_trading_analyzer.py # 趋势交易分析
│   ├── trend_analysis_visualizer.py # 趋势可视化
│   └── backtesting_engine.py  # 回测引擎
│
├── 📋 报告生成已移至: /crawlers/spiders/                # 📋 报告生成
│   └── generate_html_reports.py # HTML 报告生成
│
├── 📁 utils/                  # 🛠️ 工具模块
│   ├── cache_with_database.py # 缓存系统
│   ├── config_manager.py      # 配置管理
│   ├── logger_config.py       # 日志配置
│   └── notification.py        # 通知发送
│
├── 📁 scripts/                # 📜 辅助脚本
│   ├── check_stock_monitor.sh # 监控检查脚本
│   ├── format.sh              # 代码格式化脚本
│   └── view_database.py       # 数据库查看工具
│
├── 📁 web_templates/          # 🎨 HTML 模板
│   └── index.html             # 主页面模板
│
├── 📁 web_static/             # 🖼️ 静态资源
│   ├── css/
│   └── js/
│
└── 📁 config/                 # ⚙️ 配置文件
    ├── settings.json          # 系统设置
    └── stocks.json            # 股票配置
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd /home/jgyang/.openclaw/workspace/my-ubuntu/stock_monitor

# 安装生产依赖
pip3 install -r requirements.txt

# 安装开发依赖（可选）
pip3 install -r requirements-dev.txt
```

### 2. 配置

```bash
# 编辑配置文件
vim config/settings.json

# 添加监控股票
vim config/stocks.json
```

### 3. 运行

```bash
# 方式 1: 直接启动 Web 应用
python3 web_app.py

# 方式 2: 使用启动脚本
python3 start_app.py

# 方式 3: 仅运行监控（无 Web 界面）
python3 stock_monitor.py
```

### 4. 访问 Web 界面

打开浏览器访问：`http://localhost:5001`

---

## 📊 核心功能

### 股票监控
- ✅ 实时股价监控（A 股/港股）
- ✅ 价格报警（高价/低价/涨跌停）
- ✅ 关键价位报警
- ✅ 涨跌幅报警
- ✅ 通知推送（微信/邮件/短信）

### 数据获取
- ✅ 股票实时数据（新浪/腾讯 API）
- ✅ 基金数据（东方财富）
- ✅ 指数数据（中证指数）
- ✅ 行业板块数据
- ✅ 分析师评级数据

### 智能分析
- ✅ 趋势交易分析
- ✅ 技术指标计算
- ✅ 支撑位/压力位识别
- ✅ 买卖信号生成
- ✅ 回测引擎

### 数据爬虫
- ✅ 雪球大 V 文章抓取
- ✅ 东方财富分析师数据
- ✅ 自动 Cookies 管理
- ✅ 反爬虫策略绕过

### 报告生成
- ✅ HTML 报告自动生成
- ✅ 分析师重点关注股票
- ✅ 行业板块统计
- ✅ 指数数据对比

---

## 🔧 常用命令

### 运行爬虫

```bash
# 雪球爬虫
cd spiders
bash run_xueqiu.sh

# 东方财富分析师爬虫
cd spiders
bash run_eastmoney.sh
```

### 代码格式化

```bash
# 格式化所有代码
bash scripts/format.sh

# 或手动格式化
black *.py spiders/*.py data_fetchers/*.py
```

### 运行测试

```bash
# 运行所有测试
cd ../tests
python3 -m pytest -v

# 运行单个测试
python3 test_cache_sync.py
```

### 查看日志

```bash
# 应用日志
tail -f /var/log/stock_monitor.log

# 爬虫日志
tail -f /var/log/spider_xueqiu.log
```

---

## 📝 配置文件说明

### settings.json

```json
{
    "check_interval": 300,        // 监控检查间隔（秒）
    "market_open_start": "09:30", // 开市时间
    "market_open_end": "16:30",   // 收市时间
    "global_notification_enabled": true,  // 全局通知开关
    "ai_analysis": { ... }        // AI 分析配置（已废弃）
}
```

### stocks.json

```json
[
    {
        "code": "000001",
        "name": "平安银行",
        "low_alert_price": 10.5,
        "high_alert_price": 12.0,
        "limit_alert": true,
        "notification_enabled": true
    }
]
```

---

## 🐳 Docker 部署

```bash
# 从项目根目录构建
cd /home/jgyang/.openclaw/workspace/my-ubuntu
docker-compose up -d

# 查看日志
docker-compose logs -f stock_monitor

# 重启服务
docker-compose restart stock_monitor
```

---

## 📚 相关文档

- [项目结构分析](../docs/PROJECT_STRUCTURE_ANALYSIS.md)
- [业务分析报告](../docs/STOCK_MONITOR_BUSINESS_ANALYSIS.md)
- [代码格式指南](../docs/CODE_FORMAT_GUIDE.md)
- [测试用例说明](../tests/README.md)

---

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

See [LICENSE](../LICENSE) for details.

---

## 📞 联系方式

- 项目地址：`/home/jgyang/.openclaw/workspace/my-ubuntu/stock_monitor`
- 问题反馈：查看 [Issues](../.git/)

---

**最后更新**: 2026-03-15  
**维护人**: icode
