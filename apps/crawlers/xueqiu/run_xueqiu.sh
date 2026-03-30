#!/bin/bash

# 雪球爬虫自动化运行脚本 - 改进版
# 功能：运行爬虫程序，无论任何原因失败都尝试更新 cookies 并重试

# 设置输出目录
OUTPUT_DIR="${XUEQIU_DATA_DIR:-/data/xueqiu_data}"

# 创建 output_dir 目录（如果不存在）
mkdir -p "$OUTPUT_DIR"

# 日志文件路径
LOG_FILE="$OUTPUT_DIR/run_log.txt"
FAIL_FILE="$OUTPUT_DIR/run_fail.txt"

# 临时 cookies 文件路径
TEMP_COOKIES_FILE="$OUTPUT_DIR/temp_cookies.txt"
BACKUP_COOKIES_FILE="$OUTPUT_DIR/backup_cookies.txt"

# 远程 cookies URL
COOKIES_URL="https://blog.jgyang.cn/xueqiu/xueqiu_cookies.txt"

echo "$(date '+%Y-%m-%d %H:%M:%S') - 开始运行雪球爬虫脚本" >> "$LOG_FILE"

# 运行爬虫程序
echo "$(date '+%Y-%m-%d %H:%M:%S') - 正在运行爬虫程序..." >> "$LOG_FILE"
python3 xueqiu_scraper.py --mode=full >> "$LOG_FILE" 2>&1
RUN_RESULT=$?

if [ $RUN_RESULT -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 爬虫程序运行成功" >> "$LOG_FILE"

    # 如果之前有失败记录，删除它
    if [ -f "$FAIL_FILE" ]; then
        rm "$FAIL_FILE"
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 删除之前的失败记录文件" >> "$LOG_FILE"
    fi

    chown -R 1000:1001 "$OUTPUT_DIR"
    chmod -R 777 "$OUTPUT_DIR"

    echo "$(date '+%Y-%m-%d %H:%M:%S') - 文件权限已设置" >> "$LOG_FILE"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 脚本执行完成" >> "$LOG_FILE"

    exit 0
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 爬虫程序运行失败，错误码：$RUN_RESULT" >> "$LOG_FILE"
    echo "" >> "$FAIL_FILE"
    echo "运行失败，错误码：$RUN_RESULT" >> "$FAIL_FILE"
    tail -20 "$LOG_FILE" >> "$FAIL_FILE"

    # 检查失败原因是否与Cookies有关
    if grep -q "Cookies 已失效\|登录验证失败\|登录状态验证失败" "$LOG_FILE"; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 检测到Cookies失效，尝试更新cookies..." >> "$LOG_FILE"

        # 尝试下载远程 cookies 文件
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 尝试下载远程 cookies 文件..." >> "$LOG_FILE"

        if curl -k -o "$TEMP_COOKIES_FILE" "$COOKIES_URL" 2>/dev/null; then
            if [ -s "$TEMP_COOKIES_FILE" ]; then
                # 检查是否有旧的 cookies 文件
                if [ -f "xueqiu_cookies.txt" ]; then
                    # 比较文件内容
                    if cmp -s "$TEMP_COOKIES_FILE" "xueqiu_cookies.txt"; then
                        echo "$(date '+%Y-%m-%d %H:%M:%S') - 新旧 cookies 文件相同，但仍将重试爬虫" >> "$LOG_FILE"
                    else
                        echo "$(date '+%Y-%m-%d %H:%M:%S') - 新旧 cookies 文件不同，更新 cookies 文件" >> "$LOG_FILE"
                        cp "$TEMP_COOKIES_FILE" "xueqiu_cookies.txt"
                        echo "$(date '+%Y-%m-%d %H:%M:%S') - cookies 文件已更新" >> "$LOG_FILE"
                    fi
                else
                    echo "$(date '+%Y-%m-%d %H:%M:%S') - 没有旧 cookies 文件，将使用新文件" >> "$LOG_FILE"
                    cp "$TEMP_COOKIES_FILE" "xueqiu_cookies.txt"
                fi

                # 重新运行爬虫程序
                echo "$(date '+%Y-%m-%d %H:%M:%S') - 重新运行爬虫程序..." >> "$LOG_FILE"
                python3 xueqiu_scraper.py --mode=full 2>&1 | tee -a "$LOG_FILE"
                python3 xueqiu_scraper.py --mode=full >> "$LOG_FILE" 2>&1
                RUN_RESULT2=$?
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
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 失败原因不是Cookies问题，不进行重试" >> "$LOG_FILE"
    fi
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - 脚本执行完成" >> "$LOG_FILE"