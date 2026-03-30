import os
import time
from pathlib import Path

import requests


def download_m3u_files(config_file, output_dir):
    """读取配置文件并下载 .m3u 文件"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    downloaded_files = []
    downloaded_files.append('adult.m3u')
    with open(config_file, 'r', encoding='utf-8') as file:
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
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(f"Saved: {filepath}")
                downloaded_files.append(filename)
            except requests.RequestException as e:
                print(f"Failed to download {url}: {e}")

    # ½«ËùÓÐÏÂÔØµÄÎÄ¼þÃûÐ´Èë list.txt ÎÄ¼þ
    list_filepath = os.path.join(output_dir, "list.txt")
    with open(list_filepath, 'w', encoding='utf-8') as list_file:
        for filename in downloaded_files:
            list_file.write(f"{filename}\n")
    print(f"File list saved to: {list_filepath}\n\n\n")

if __name__ == "__main__":
    ts = time.time()
    format_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"Run script at {format_time}....")

    default_config_file = "/root/apps/iptv/config.txt"
    config_file = "/data/iptv_config/config.txt"
    if not Path(config_file).exists() and not Path(default_config_file).exists():
        raise FileNotFoundError(f"config file not found")
    config_file = config_file if Path(config_file).exists() else default_config_file
    print(f"start download m3u files from {config_file} ...\n");

    output_dir = "/data/iptv/"  # 下载文件存储目录

    download_m3u_files(config_file, output_dir)
