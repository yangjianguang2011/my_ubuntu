#!/bin/bash

# 雪球爬虫自动化运行脚本
# 功能：运行爬虫程序，无论任何原因失败都尝试更新 cookies 并重试

# 获取配置文件中的 output_dir
OUTPUT_DIR=$(python3 -c "
import json
try:
    with open('settings.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
        print(config.get('xueqiu_data_dir', '/data/stock_monitor/xueqiu_data'))
except:
    print('/data/stock_monitor/xueqiu_data')
")

# 创建 output_dir 目录（如果不存在）
mkdir -p "$OUTPUT_DIR"

# 日志文件路径
LOG_FILE="$OUTPUT_DIR/run_log.txt"
FAIL_FILE="$OUTPUT_DIR/run_fail.txt"

# 临时 cookies 文件路径
TEMP_COOKIES_FILE="$OUTPUT_DIR/temp_cookies.json"
BACKUP_COOKIES_FILE="$OUTPUT_DIR/backup_cookies.json"

# 远程 cookies URL
COOKIES_URL="https://blog.jgyang.cn/stocks/xueqiu_data/xueqiu_cookies.json"

echo "$(date '+%Y-%m-%d %H:%M:%S') - 开始运行雪球爬虫脚本" >> "$LOG_FILE"

# 运行爬虫程序
echo "$(date '+%Y-%m-%d %H:%M:%S') - 正在运行爬虫程序..." >> "$LOG_FILE"
python3 xueqiu_scraper.py --mode=full 2>&1 | tee -a "$LOG_FILE"

# 检查运行结果
RUN_RESULT=${PIPESTATUS[0]}

if [ $RUN_RESULT -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 爬虫程序运行成功" >> "$LOG_FILE"

    # 如果之前有失败记录，删除它
    if [ -f "$FAIL_FILE" ]; then
        rm "$FAIL_FILE"
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 删除之前的失败记录文件" >> "$LOG_FILE"
    fi

    chown -R 1000:1001 "$OUTPUT_DIR"
    chmod -R 777 "$OUTPUT_DIR"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 爬虫程序运行失败，错误码：$RUN_RESULT" >> "$LOG_FILE"

    # 记录失败原因
    echo "运行时间：$(date '+%Y-%m-%d %H:%M:%S')" > "$FAIL_FILE"
    echo "错误码：$RUN_RESULT" >> "$FAIL_FILE"
    echo "运行日志摘要:" >> "$FAIL_FILE"

    # 获取最近的错误信息
    tail -20 "$LOG_FILE" >> "$FAIL_FILE"

    echo "$(date '+%Y-%m-%d %H:%M:%S') - 无论任何原因失败，开始尝试更新 cookies 并重试..." >> "$LOG_FILE"

    # 备份当前 cookies 文件
    if [ -f "xueqiu_cookies.json" ]; then
        cp "xueqiu_cookies.json" "$BACKUP_COOKIES_FILE"
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 已备份当前 cookies 文件到 $BACKUP_COOKIES_FILE" >> "$LOG_FILE"
    fi

    # 尝试从远程下载最新 cookies
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 尝试从 $COOKIES_URL 下载最新 cookies 文件" >> "$LOG_FILE"

    # 使用 curl 下载 cookies 文件
    chmod 777 /data/stock_monitor/xueqiu_data/xueqiu_cookies.json
    if curl -s -o "$TEMP_COOKIES_FILE" "$COOKIES_URL"; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - cookies 文件下载成功" >> "$LOG_FILE"

        # 检查文件是否为空
        if [ -s "$TEMP_COOKIES_FILE" ]; then
            # 检查新旧文件是否不同
            if [ -f "xueqiu_cookies.json" ]; then
                if cmp -s "xueqiu_cookies.json" "$TEMP_COOKIES_FILE"; then
                    echo "$(date '+%Y-%m-%d %H:%M:%S') - 新旧 cookies 文件相同，但仍将重试爬虫" >> "$LOG_FILE"
                else
                    echo "$(date '+%Y-%m-%d %H:%M:%S') - 新旧 cookies 文件不同，更新 cookies 文件" >> "$LOG_FILE"
                fi
            else
                echo "$(date '+%Y-%m-%d %H:%M:%S') - 没有旧 cookies 文件，将使用新文件" >> "$LOG_FILE"
            fi

            # 总是更新 cookies 文件（无论是否相同）
            cp "$TEMP_COOKIES_FILE" "xueqiu_cookies.json"
            echo "$(date '+%Y-%m-%d %H:%M:%S') - cookies 文件已更新" >> "$LOG_FILE"

            # 重新运行爬虫程序
            echo "$(date '+%Y-%m-%d %H:%M:%S') - 重新运行爬虫程序..." >> "$LOG_FILE"
            python3 xueqiu_scraper.py --mode=full 2>&1 | tee -a "$LOG_FILE"
            RUN_RESULT2=${PIPESTATUS[0]}

            if [ $RUN_RESULT2 -eq 0 ]; then
                echo "$(date '+%Y-%m-%d %H:%M:%S') - 重新运行成功" >> "$LOG_FILE"
                # 删除失败记录
                if [ -f "$FAIL_FILE" ]; then
                    rm "$FAIL_FILE"
                    echo "$(date '+%Y-%m-%d %H:%M:%S') - 删除失败记录文件" >> "$LOG_FILE"
                fi
            else
                echo "$(date '+%Y-%m-%d %H:%M:%S') - 重新运行仍然失败，错误码：$RUN_RESULT2" >> "$LOG_FILE"
                echo "" >> "$FAIL_FILE"
                echo "第二次运行失败，错误码：$RUN_RESULT2" >> "$FAIL_FILE"
                tail -20 "$LOG_FILE" >> "$FAIL_FILE"
            fi
        else
            echo "$(date '+%Y-%m-%d %H:%M:%S') - 下载的 cookies 文件为空" >> "$LOG_FILE"
            echo "下载的 cookies 文件为空" >> "$FAIL_FILE"
        fi
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') - cookies 文件下载失败" >> "$LOG_FILE"
        echo "cookies 文件下载失败" >> "$FAIL_FILE"
    fi
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - 脚本执行完成" >> "$LOG_FILE"
