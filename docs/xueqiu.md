# 雪球大V文章抓取（接口版）

位置：`apps/xueqiu_api/`　（旧 `apps/xueqiu/`（Selenium + DOM 解析版）已删除，本模块是唯一实现）

纯接口实现：**Chrome 只当"通行证 + 传输通道"，不解析任何 DOM**，页面改版/选择器失效都影响不到它。

---

## 1. 为什么还需要 Chrome

雪球主要接口（`user_timeline` / `show` / `original/show`）挂在**阿里云 WAF** 后面：

| 客户端 | `user_timeline` | `show.json` | `friends.json` |
|---|---|---|---|
| `requests` | ❌ WAF 挑战页 | ❌ WAF | ✅ |
| `curl_cffi`（模拟 Chrome TLS） | ❌ WAF | ❌ WAF | ⚠️ |
| 浏览器页面上下文 `fetch` | ✅ | ✅ | ✅ |

WAF 要用浏览器 JS 算出的指纹 cookie 才放行，纯 HTTP 拿不到。所以本模块用
**Chrome 打开一次首页过 WAF**，然后在页面上下文 `fetch` 同源接口拿 JSON。

好处：每页 1 次请求拿 20 条（旧版要逐条解析 DOM、长文再开标签页），彻底根除
选择器脆弱问题；需要自带正文时才补 1 次 `show.json`。

---

## 2. 文件

| 文件 | 作用 |
|------|------|
| `xueqiu_api.py` | 接口层（`fetch` 同源接口、WAF 兜底、退避重试） |
| `xueqiu_scraper.py` | 主程序（作者列表、翻页、去重、归档、命令行） |
| `run_xueqiu.sh` | shell 入口（容器 / 定时任务用） |

---

## 3. 用法

```bash
cd apps/xueqiu_api

python3 xueqiu_scraper.py --mode=full        # 当天更新（默认，生产用）
python3 xueqiu_scraper.py --all-history      # 全量历史（需登录）
python3 xueqiu_scraper.py --mode=test        # 只处理前 2 个作者（测试）
python3 xueqiu_scraper.py --check            # 连通性自检（不写数据）
python3 xueqiu_scraper.py --refresh-authors  # 刷新关注列表（需登录）
python3 xueqiu_scraper.py --login --no-headless   # 手动登录并保存 cookies
python3 xueqiu_scraper.py --no-headless      # 显示浏览器窗口（调试）
python3 xueqiu_scraper.py --request-delay 2  # 加大请求间隔（后台跑推荐 2~3 秒）

bash run_xueqiu.sh                           # shell 入口（自动重试/换 cookies）
```

指定 cookies 文件（默认 `<数据目录>/xueqiu_cookies.txt`）：

```bash
python3 xueqiu_scraper.py --refresh-authors --cookies /data/xueqiu_data/xueqiu_cookies.txt
```

本机（Windows）运行请用统一 venv：

```powershell
& "E:\work\code\.venv\Scripts\python.exe" apps\xueqiu_api\xueqiu_scraper.py --check
```

---

## 4. 输出

```
<data_dir>/                         # 默认 /data/xueqiu_data（本机 → run/xueqiu_data）
├── all_authors.json                # 作者列表
├── scraped_authors.json            # 抓取记录
├── author_id_map.json              # slug → 数字 uid 缓存
├── update_latest.html              # 当天更新汇总
├── log_api.txt                     # 本模块日志
└── <作者ID>_<作者名>/
    └── <作者ID>_<年月>.html        # 按月归档（含标题 + data-status-id 去重标记）
```

---

## 5. 已知限制

* **翻页需要登录**。未登录时只有第 1 页可用，第 2 页会返回
  `10022 请登录雪球查看更多内容`；`/friendships/friends.json` 的 `page`
  参数在未登录时会被忽略（把第 1 页重复返回）。因此：
  - 日常「当天更新」只需第 1 页，**不需要登录**；
  - `--all-history`、`--refresh-authors` **需要登录**（先 `--login`）。
* 请求过密会触发 `31005 访问频率太快了`，模块会退避重试；
  仍建议保持默认间隔（0.8s），必要时用 `--request-delay` 调大。
* 偶发 `EdgeOne` / 阿里云 WAF 挑战页：模块会**自动改用导航方式**让浏览器执行
  挑战 JS（`fetch` 拿到挑战脚本时不执行，故必须导航兜底），再读回 JSON，
  并按 4s/9s/14s/19s 退避重试（限流为 20s/40s/60s/80s）。

---

## 6. 配置与依赖

`apps/config.ini`：

```ini
[xueqiu]
dir = /root/apps/xueqiu_api
data_dir = /data/xueqiu_data
```

`run_xueqiu.sh` 额外识别环境变量 `XUEQIU_DATA_DIR`（优先级高于配置文件）。
脚本自算目录，不依赖调用时的 cwd；日志写入 `[paths] log_dir`（`/data/logs`）。

依赖：`selenium` + Chrome（沿用旧版环境，**无新增第三方依赖**）。
公开数据（帖子/详情/任意用户的关注列表）**无需登录**；只有 `--refresh-authors`
（拉"我的关注"）需要登录态。

---

## 7. 故障排除

### Cookies 失效

```bash
# 删除旧 Cookies 后重新登录（文件名是 .txt，不是 .json）
rm <数据目录>/xueqiu_cookies.txt
python3 apps/xueqiu_api/xueqiu_scraper.py --login --no-headless
```

`run_xueqiu.sh` 在检测到 Cookies 失效时会自动从远端拉取并重试一次。

### ChromeDriver 版本不匹配

```bash
pip3 install webdriver-manager
python3 -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager().install()"
```

### 被反爬

- 增大延时：`--request-delay 2`（或调整 `xueqiu_utils.human_like_delay()`）
- 降低频率：减少单次抓取量
