# apps/xueqiu_api —— 雪球大V文章抓取（接口版）

纯接口重写版，与 `apps/xueqiu/`（Selenium + DOM 解析版）**功能相同、数据目录相同**，
但抓取路径完全不同。

## 为什么还需要 Chrome

雪球主要接口（`user_timeline` / `show` / `original/show`）挂在**阿里云 WAF** 后面：

| 客户端 | `user_timeline` | `show.json` | `friends.json` |
|---|---|---|---|
| `requests` | ❌ WAF 挑战页 | ❌ WAF | ✅ |
| `curl_cffi`（模拟 Chrome TLS） | ❌ WAF | ❌ WAF | ⚠️ |
| 浏览器页面上下文 `fetch` | ✅ | ✅ | ✅ |

WAF 要用浏览器 JS 算出的指纹 cookie 才放行，纯 HTTP 拿不到。所以本模块用
**Chrome 打开一次首页过 WAF**，然后在页面上下文 `fetch` 同源接口拿 JSON。
Chrome 只当"通行证 + 传输通道"，**不解析任何 DOM**——页面改版、选择器失效都影响不到它。

好处：每页 1 次请求拿 20 条（旧版要逐条解析 DOM、长文再开标签页），彻底根除
选择器脆弱问题；需要自带正文时才补 1 次 `show.json`。

## 数据布局（与旧版一致，可直接接手旧数据）

```
<data_dir>/                         # 默认 /data/xueqiu_data（本机 → run/xueqiu_data）
├── all_authors.json                # 作者列表
├── scraped_authors.json            # 抓取记录
├── author_id_map.json              # slug → 数字 uid 缓存（新增）
├── update_latest.html              # 当天更新汇总
├── log_api.txt                     # 本模块日志
└── <作者ID>_<作者名>/
    └── <作者ID>_<年月>.html        # 按月归档（含标题 + data-status-id 去重标记）
```

与旧版的差异（都是修 bug）：

* 去重改用 status **id**（旧版按链接字符串匹配，链接一坏就失效）；
* 归档 HTML **写入了标题**（旧版只有正文）；
* 文章链接是**真实地址** `https://xueqiu.com/<uid>/<id>`（旧版因 `www.` 域名解析 bug
  退化成作者主页）；
* 正文去掉 `//@…查看对话`、视频播放器、`来源：雪球App` 等噪声；
* 时间用 `created_at`（毫秒时间戳）直接过滤，不再解析"3小时前/修改于07-30"；
* **只抓"原发"**（接口 `type=0`，排除回复/转发）；
* `--refresh-authors` **不会覆盖丢失**：新结果与旧列表合并，变小只告警。

## 已知限制

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

## 用法

```bash
# 当天更新（默认，生产用）
python3 xueqiu_scraper.py --mode=full

# 全量历史
python3 xueqiu_scraper.py --all-history

# 只处理前 2 个作者（测试）
python3 xueqiu_scraper.py --mode=test

# 连通性自检（不写数据）
python3 xueqiu_scraper.py --check

# 刷新关注列表（需要登录态）
python3 xueqiu_scraper.py --refresh-authors

# 手动登录并保存 cookies（会打开可见浏览器；容器里首次使用"我的关注"时用）
python3 xueqiu_scraper.py --login --no-headless

# 指定 cookies 文件（默认 <数据目录>/xueqiu_cookies.txt）
python3 xueqiu_scraper.py --refresh-authors --cookies /data/xueqiu_data/xueqiu_cookies.txt

# 显示浏览器窗口（调试）
python3 xueqiu_scraper.py --no-headless

# 加大请求间隔（后台跑、时间不敏感时推荐 2~3 秒）
python3 xueqiu_scraper.py --request-delay 2

# shell 入口（容器/定时任务）
bash run_xueqiu.sh
```

本机运行（Windows）请用统一 venv：

```powershell
& "E:\work\code\.venv\Scripts\python.exe" apps\xueqiu_api\xueqiu_scraper.py --check
```

## 依赖

* `selenium` + Chrome（沿用旧版已有环境，无新增第三方依赖）。
* 公开数据（帖子/详情/任意用户的关注列表）**无需登录**；
  只有 `--refresh-authors`（拉"我的关注"）需要登录态。
