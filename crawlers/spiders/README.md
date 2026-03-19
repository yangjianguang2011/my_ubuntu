# 🕷️ Crawlers - 爬虫和数据采集模块

独立的数据爬虫模块，与 stock_monitor 解耦。

---

## 📁 目录结构

```
crawlers/
├── 📄 README.md                 # 本文档
│
├── 📁 spiders/                  # 🕸️ 股票相关爬虫
│   ├── xueqiu_scraper.py        # 雪球大 V 文章抓取
│   ├── xueqiu_utils.py          # 雪球爬虫工具
│   ├── eastmoney_analyst.py     # 东方财富分析师数据
│   ├── generate_html_reports.py # HTML 报告生成
│   ├── run_xueqiu.sh            # 雪球爬虫脚本
│   └── run_eastmoney.sh         # 东方财富爬虫脚本
│
├── 📁 iptv/                     # 📺 IPTV 频道管理
│   ├── download_m3u.py          # M3U 频道下载
│   ├── channel_check_fileter.py # 频道过滤
│   ├── channel_check_thread.py  # 频道检测（多线程）
│   └── config.txt               # 配置文件
│
└── 📁 news/                     # 📰 新闻爬虫
    ├── crawl_save_news.py       # 新闻抓取保存
    ├── requirements.txt         # Python 依赖
    ├── run.sh                   # 运行脚本
    └── config/                  # 配置目录
```

---

## 🚀 快速开始

### 雪球爬虫

```bash
cd crawlers/spiders

# 运行雪球爬虫
bash run_xueqiu.sh

# 或直接运行
python3 xueqiu_scraper.py
```

**功能**:
- ✅ 自动登录雪球（保存 Cookies）
- ✅ 获取关注的大 V 文章
- ✅ 按作者分目录保存 HTML
- ✅ 自动去重

**输出**: `output/xueqiu/YYYYMMDD_HHMMSS/`

---

### 东方财富分析师爬虫

```bash
cd crawlers/spiders

# 运行分析师爬虫
bash run_eastmoney.sh

# 或直接运行
python3 eastmoney_analyst.py
```

**功能**:
- ✅ 采集分析师排名数据
- ✅ 按行业分类抓取
- ✅ 生成 Excel 报告

**输出**: `output/eastmoney/processed_YYYYMMDD_HHMMSS/`

---

### IPTV 频道下载

```bash
cd crawlers/iptv

# 下载频道列表
python3 download_m3u.py
```

**功能**:
- ✅ 下载 M3U 格式频道
- ✅ 频道分类整理
- ✅ 生成索引文件

---

### 新闻爬虫

```bash
cd crawlers/news

# 运行新闻爬虫
bash run.sh

# 或直接运行
python3 crawl_save_news.py
```

**功能**:
- ✅ 自动抓取新闻
- ✅ 保存为 HTML/Markdown
- ✅ 定期更新

---

## ⚙️ 配置说明

### 雪球 Cookies

首次运行需要登录雪球获取 Cookies：

```bash
cd crawlers/spiders
# 手动登录雪球网，Cookies 会自动保存
python3 xueqiu_scraper.py
```

### 运行增强版系统

系统已升级为具有先进Cookies管理机制的版本：

```bash
# 标准运行
bash run_xueqiu.sh

# 或直接运行
python3 xueqiu_scraper.py --mode=full
```

新系统特性：
- 智能Cookies验证和恢复
- 安全的Cookies保存机制（只在验证通过时保存）
- 多重验证确保登录状态准确性
- 自动处理Cookies过期问题

### 定时任务

```bash
# 添加到 crontab
# 每天凌晨 5 点运行雪球爬虫
0 5 * * * cd /root/crawlers/spiders && bash run_xueqiu.sh

# 每天晚上 11 点运行分析师爬虫
0 23 * * * cd /root/crawlers/spiders && bash run_eastmoney.sh

# 每天晚上 11 点下载 IPTV
0 23 * * * cd /root/crawlers/iptv && python3 download_m3u.py

# 每 8 小时运行新闻爬虫
0 */8 * * * cd /root/crawlers/news && bash run.sh
```

---

## 📊 数据流向

```
crawlers/
├── spiders/        → 输出到 → output/xueqiu/, output/eastmoney/
├── iptv/          → 输出到 → /data/iptv/
└── news/          → 输出到 → /data/news/
```

---

## 🔧 故障排除

### 问题 1: Cookies 失效

```bash
# 删除旧 Cookies
rm crawlers/spiders/xueqiu_cookies.json

# 重新登录
python3 crawlers/spiders/xueqiu_scraper.py
```

### 问题 2: ChromeDriver 版本不匹配

```bash
# 更新 ChromeDriver
pip3 install webdriver-manager
python3 -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager().install()"
```

### 问题 3: 爬虫被反爬

- 增加延时：修改 `human_like_delay()` 参数
- 使用代理：添加代理配置
- 降低频率：减少并发数

---

## 📝 依赖安装

```bash
# 雪球/东方财富爬虫
pip3 install selenium webdriver-manager beautifulsoup4 lxml

# IPTV
pip3 install requests

# 新闻爬虫
pip3 install requests beautifulsoup4
```

---

## 🔗 相关项目

- [Stock Monitor](../stock_monitor/) - 股票监控系统（使用爬虫数据）
- [文档中心](../docs/) - 项目文档

---

## 📄 许可证

See [LICENSE](../LICENSE) for details.

---

**最后更新**: 2026-03-15  
**维护人**: icode
