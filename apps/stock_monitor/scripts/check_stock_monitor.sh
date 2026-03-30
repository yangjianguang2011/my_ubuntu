#!/bin/bash

# 检查并启动股票监控应用
# 该脚本用于检查股票监控应用是否正在运行，如果没有运行则启动它

# 定义变量
APP_DIR="/root/apps/stock_monitor"
LOG_FILE="/data/stock_monitor/log.txt"

# 记录日志的函数
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# 检查应用是否正在运行
check_and_start_app() {
    # 检查是否有 python3 start_app.py 进程在运行
    if ! pgrep -f "python3 start_app.py" > /dev/null; then
        log_message "股票监控应用未运行，正在启动..."

        # 进入应用目录
        cd "$APP_DIR" || {
            log_message "错误: 无法进入目录 $APP_DIR"
            return 1
        }

        # 启动应用（在后台运行）
        nohup python3 start_app.py > /dev/null 2>&1 &
        APP_PID=$!

        if [ $? -eq 0 ]; then
            log_message "股票监控应用已启动，PID: $APP_PID"
        else
            log_message "错误: 启动股票监控应用失败"
        fi
    else
        log_message "股票监控应用正在运行"
    fi
}

# 执行检查和启动
check_and_start_app
