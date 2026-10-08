"""IPTV m3u 播放列表下载。

要点（2026-10-08 修复）：
  * **GitHub 链接自动纠偏**：配置里写 `github.com/.../blob/...` 会返回 **HTML 网页**，
    历史上因此产出过"假 m3u"（usa/china/samsungtv）。现在按
    **jsdelivr CDN → raw.githubusercontent.com** 依次尝试（CDN 快，raw 兜底最新）。
  * **内容校验**：响应必须含 `#EXTM3U` 头，否则视为失败（不写文件、保留旧产物），
    避免把 HTML/错误页静默写成 .m3u。
  * **超长 EPG 头精简**：`#EXTM3U x-tvg-url="...(上百个节目单地址)..."` → 精简回 `#EXTM3U`。
"""
import os
import re
import sys
import time
from pathlib import Path

import requests

# 允许直接运行本脚本（python apps/iptv/download_m3u.py）：
# 把 apps/ 加入 sys.path，才能 import config
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from config import get_path  # noqa: E402

TIMEOUT = 25          # 单次请求超时（秒）；jsdelivr 实测 ~1s，raw 偶发 60s+ 超时
M3U_HEAD = "#EXTM3U"  # 内容校验标记
# 头部行超过该长度 → 视为"塞了一大堆 EPG 地址"，精简回纯 `#EXTM3U`
# （usa/china 的 EPG 列表长达 6295 字符、含上百个 xml.gz，播放器会逐个去拉，很慢且多半失败）
EPG_STRIP_MIN_LEN = 500

# github.com|raw.githubusercontent.com /OWNER/REPO/[blob/|raw/|refs/heads/]BRANCH/PATH
_GH_RE = re.compile(
    r"^https?://(?:github\.com|raw\.githubusercontent\.com)/([^/]+)/([^/]+)/"
    r"(?:blob/|raw/|refs/heads/)?(.+)$")


def candidate_urls(url):
    """一个 GitHub 链接 → 依次尝试的候选 URL（**jsdelivr CDN 优先，raw 兜底**）。

    * `github.com/.../blob/...` 是**网页地址**，返回 HTML → 直接跳过，不试。
    * **CDN 优先**的原因：NAS 上 `raw.githubusercontent.com` 实测 14~60s+ 且偶发超时，
      而 jsdelivr 约 0.6~1.3s；CDN 对分支有 ~12h 缓存，而本任务是**每天跑一次**，
      最长也就多 12h，代价可接受；raw 作为兜底保证"CDN 挂了还能拿到最新"。

    非 GitHub 链接原样返回。
    """
    m = _GH_RE.match(url)
    if not m:
        return [url]
    owner, repo, path = m.groups()
    out = [f"https://cdn.jsdelivr.net/gh/{owner}/{repo}@{path}",
           f"https://raw.githubusercontent.com/{owner}/{repo}/{path}"]
    if "/blob/" not in url and url not in out:      # blob 页是 HTML，不浪费时间
        out.append(url)
    return out


def strip_long_epg_header(text):
    """把**过长的** `#EXTM3U ...` 头部精简为纯 `#EXTM3U`。

    `#EXTM3U` 头可带 `x-tvg-url="..."` / `url-tvg="..."` —— 那是 **EPG（节目单）**地址、
    **不是频道**。某些源会塞上百个（usa/china 那行 6295 字符），播放器会逐个去拉
    xml.gz，又慢又多半失败。

    只处理 **超过 `EPG_STRIP_MIN_LEN`** 的头部行（短的、只带 1 个 EPG 的保持原样）。
    返回 (文本, 是否精简)。
    """
    lines = text.split("\n")
    for i, ln in enumerate(lines[:3]):          # 头只可能在前几行
        if ln.lstrip().startswith(M3U_HEAD):
            if len(ln) > EPG_STRIP_MIN_LEN:
                lines[i] = ln.lstrip()[:len(M3U_HEAD)]
                return "\n".join(lines), True
            return text, False
    return text, False


def fetch_m3u(url):
    """按候选顺序下载并**校验内容**。返回 (text, 实际URL)；全部失败抛 RuntimeError。"""
    errors = []
    for u in candidate_urls(url):
        try:
            resp = requests.get(u, timeout=TIMEOUT)
            resp.raise_for_status()
            text = resp.text
            if M3U_HEAD not in text[:1000]:
                raise ValueError(f"内容不含 {M3U_HEAD}（疑似 HTML/错误页），"
                                 f"前 60 字符: {text[:60]!r}")
            return text, u
        except (requests.RequestException, ValueError) as e:
            errors.append(f"{u} -> {type(e).__name__}: {e}")
    raise RuntimeError(" ; ".join(errors))


def download_m3u_files(config_file, output_dir):
    """读取配置文件并下载 .m3u 文件（校验失败的条目跳过，保留已有旧文件）。"""
    os.makedirs(output_dir, exist_ok=True)
    downloaded_files = ["adult.m3u"]
    with open(config_file, "r", encoding="utf-8") as file:
        next(file)  # 跳过标题行
        for line in file:
            parts = line.strip().split()
            if len(parts) != 3:
                continue  # 跳过格式不正确的行

            category, channels, url = parts
            filename = f"{category.lower()}.m3u"
            filepath = os.path.join(output_dir, filename)

            print(f"Downloading {url} -> {filepath}")
            try:
                text, used = fetch_m3u(url)
                text, stripped = strip_long_epg_header(text)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(text)
                print(f"Saved: {filepath} ({len(text)} 字符, 来自 {used}"
                      + ("，已精简超长 EPG 头)" if stripped else ")"))
                downloaded_files.append(filename)
            except RuntimeError as e:
                print(f"Failed to download {url}: {e}")

    # 将所有下载的文件名写入 list.txt
    list_filepath = os.path.join(output_dir, "list.txt")
    with open(list_filepath, "w", encoding="utf-8") as list_file:
        for filename in downloaded_files:
            list_file.write(f"{filename}\n")
    print(f"File list saved to: {list_filepath}\n\n\n")


if __name__ == "__main__":
    format_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"Run script at {format_time}....")

    # 配置文件：优先 /data/iptv/config.txt（可覆盖），其次项目内 apps/iptv/config.txt
    candidates = [
        os.path.join(get_path("iptv", "data_dir", "/data/iptv"), "config.txt"),
        os.path.join(get_path("iptv", "dir", "/root/apps/iptv"), "config.txt"),
    ]
    config_file = next((c for c in candidates if Path(c).exists()), None)
    if not config_file:
        raise FileNotFoundError(f"config file not found, tried: {candidates}")
    print(f"start download m3u files from {config_file} ...\n")

    output_dir = get_path("iptv", "data_dir", "/data/iptv")  # 下载文件存储目录
    download_m3u_files(config_file, output_dir)
