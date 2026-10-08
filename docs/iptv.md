# IPTV 频道列表管理

位置：`apps/iptv/`

从配置里的各个源下载 `.m3u` 播放列表，并可对频道做可用性检查/过滤。

---

## 1. 文件

| 文件 | 作用 |
|------|------|
| `download_m3u.py` | 读 `config.txt` → 逐条下载 `.m3u` → 写 `list.txt` |
| `channel_check_thread.py` | 多线程检查频道可用性 |
| `channel_check_fileter.py` | 按检查结果过滤频道 |
| `config.txt` | 频道源清单（`类别 频道数 源URL`，Tab/空格分隔） |

---

## 2. 用法

```bash
cd apps/iptv
python3 download_m3u.py
```

下载逻辑：

1. 读取 `config.txt`（跳过标题行），每行 `类别 频道数 URL` 三段；
2. 每个源下载为 `<类别小写>.m3u`（`requests.get`，超时 25s，单条失败不影响其它）；
3. **超长 EPG 头精简**（见 2.2）；
4. 全部文件名写入 `list.txt`（固定含 `adult.m3u`）。

**输出目录**：`/data/iptv`（本机开发 → `run/iptv`）。

### 2.1 ⚠️ GitHub 源必须用 raw 链接（2026-10-08 修复）

**坑**：`https://github.com/<user>/<repo>/blob/<branch>/<path>` 是**网页地址**，
返回的是 **HTML**；脚本会把 HTML 原样写成 `.m3u`，产出"假 m3u"（播放器打不开）。
历史上 `usa.m3u` / `china.m3u` / `samsungtv.m3u` 就是这样坏掉的。

配置里写下面任一形式即可（脚本会自己纠偏）：

```
https://raw.githubusercontent.com/<user>/<repo>/refs/heads/<branch>/<path>
https://raw.githubusercontent.com/<user>/<repo>/<branch>/<path>
```

**脚本自动纠偏**：对任何 GitHub 链接依次尝试
**`cdn.jsdelivr.net`（快）→ `raw.githubusercontent.com`（兜底最新）**；
`blob/` 网页地址直接跳过（必然是 HTML）。
并且**校验响应必须含 `#EXTM3U` 头**，否则视为失败（**不写文件、保留旧产物**）。

> 实测（NAS）：`jsdelivr` 约 **0.6~1.3s**，`raw` 约 **14~60s 且偶发超时** ✗。
> 故 **CDN 优先**；CDN 对分支有 ~12h 缓存，而本任务**每天跑一次**，最长多 12h，可接受。
> 切换后全量跑从 **271s → 21s**。

### 2.2 超长 EPG 头精简（2026-10-08）

`#EXTM3U` 头可以带 `x-tvg-url="..."` / `url-tvg="..."` —— 那是 **EPG（节目单）**地址，
**不是频道**。某些源会塞**上百个**：

```
#EXTM3U x-tvg-url="https://epgshare01.online/...xml.gz, https://epgshare01.online/...xml.gz, ..."   ← 6295 字符
```

播放器会逐个去拉这些 xml.gz，又慢又多半失败；在编辑器里还会**自动折行**、
看起来像"一屏无效频道"。

**处理**：头部行**超过 `EPG_STRIP_MIN_LEN = 500`** 时，精简为纯 `#EXTM3U`
（只带 1 个 EPG 的短头保持原样，如 `samsungtv.m3u`）。

> 实测：`usa.m3u` / `china.m3u` 头长 **6295 → 8**，文件体积 -45%~-58%，
> **频道一个没丢**（usa 28、china 22 条 `#EXTINF` 均不变）。

---

## 3. 配置

`apps/config.ini`：

```ini
[iptv]
dir = /root/apps/iptv
data_dir = /data/iptv
```

脚本的配置文件查找顺序（第一个存在者胜出）：

1. `<data_dir>/config.txt` —— 即 `/data/iptv/config.txt`（**生产用，可覆盖**）
2. `<dir>/config.txt` —— 即项目内 `apps/iptv/config.txt`（**默认模板**）

因此生产上改源只需改数据卷里的 `config.txt`，不必改代码。

> ⚠️ **注意**：`/data/iptv/config.txt` **优先**。曾有改动只改了
> `/root/apps/iptv/config.txt`（模板），生产实际读的是 `/data/iptv/config.txt`，**改动未生效**。
> 改源时两份都改，或只改 `/data/iptv/config.txt`。

> 路径经 `apps/config.py::get_path` 解析：容器内原样使用，Windows 本机按
> `[mount_point]` 映射到项目内（`/data` → `<项目根>/run`）。

---

## 4. 依赖

```bash
pip3 install requests
```

---

## 5. 定时任务

容器内 `/etc/cron.d/myjobs`（源文件 `configs/cron.d/myjobs`）：

```
0 23 * * * root cd /root/apps/iptv && /usr/bin/python3 download_m3u.py >> /data/logs/cron/iptv.log 2>&1
```
