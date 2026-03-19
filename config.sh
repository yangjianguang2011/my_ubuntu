#!/bin/bash
# 配置加载脚本 - 从 config.ini 读取配置

CONFIG_FILE="${CONFIG_FILE:-/root/config.ini}"

# INI 解析函数
get_ini_value() {
    local section=$1
    local key=$2
    local file=$3
    
    awk -F '=' -v section="$section" -v key="$key" '
    /^\[/ { current_section = $1; gsub(/[\[\]]/, "", current_section) }
    current_section == section && $1 ~ key { 
        gsub(/^[ \t]+|[ \t]+$/, "", $2)
        print $2 
    }
    ' "$file"
}

# 加载基础配置
ROOT_DIR=$(get_ini_value "paths" "root_dir" "$CONFIG_FILE")
DATA_DIR=$(get_ini_value "paths" "data_dir" "$CONFIG_FILE")
LOG_DIR=$(get_ini_value "paths" "log_dir" "$CONFIG_FILE")

# 处理相对路径，转换为绝对路径
if [ "$ROOT_DIR" = "." ]; then
    # 如果 ROOT_DIR 是 "."，则使用脚本所在的根目录
    ROOT_DIR="/root"
elif [ "${ROOT_DIR#/}" = "$ROOT_DIR" ] && [ "$ROOT_DIR" != "." ]; then
    # 如果 ROOT_DIR 是相对路径（不以 / 开头），则将其转换为绝对路径
    # 基于当前脚本的位置来确定绝对路径
    SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)/$ROOT_DIR
fi

# 如果 DATA_DIR 和 LOG_DIR 是相对路径，也需要处理
if [ "${DATA_DIR#/}" = "$DATA_DIR" ] && [ "$DATA_DIR" != "." ]; then
    # DATA_DIR 是相对路径，相对于 ROOT_DIR
    DATA_DIR="$ROOT_DIR/$DATA_DIR"
fi

if [ "${LOG_DIR#/}" = "$LOG_DIR" ] && [ "$LOG_DIR" != "." ]; then
    # LOG_DIR 是相对路径，相对于 ROOT_DIR
    LOG_DIR="$ROOT_DIR/$LOG_DIR"
fi

# 导出所有路径变量
export CRAWLERS_SPIDERS_DIR="$ROOT_DIR/crawlers/spiders"
export IPTV_DIR="$ROOT_DIR/iptv"
export NEWS_DIR="$ROOT_DIR/news"
export STOCK_MONITOR_DIR="$ROOT_DIR/stock_monitor"

export XUEQIU_DATA_DIR="$DATA_DIR/xueqiu_data"
export ANALYST_DATA_DIR="$DATA_DIR/analyst_data"
export DATABASE_DIR="$DATA_DIR/database"

export CRON_LOG="$LOG_DIR/cron"
export SSH_LOG="$LOG_DIR/ssh"
export NGINX_LOG="$LOG_DIR/nginx"
export SUPERVISOR_LOG="$LOG_DIR/supervisor"
