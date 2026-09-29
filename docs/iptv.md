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
2. 每个源下载为 `<类别小写>.m3u`（`requests.get`，超时 10s，单条失败不影响其它）；
3. 全部文件名写入 `list.txt`（固定含 `adult.m3u`）。

**输出目录**：`/data/iptv`（本机开发 → `run/iptv`）。

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
