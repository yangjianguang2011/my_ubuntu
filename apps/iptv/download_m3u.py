import os
import sys
import time
from pathlib import Path

import requests

# 允许直接运行本脚本（python apps/iptv/download_m3u.py）：
# 把 apps/ 加入 sys.path，才能 import config
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from config import get_path  # noqa: E402


def download_m3u_files(config_file, output_dir):
    """读取配置文件并下载 .m3u 文件"""
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
                response = requests.get(url, timeout=10)
                response.raise_for_status()  # 检查 HTTP 状态码
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(response.text)
                print(f"Saved: {filepath}")
                downloaded_files.append(filename)
            except requests.RequestException as e:
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
