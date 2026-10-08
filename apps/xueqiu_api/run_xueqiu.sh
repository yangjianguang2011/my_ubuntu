#!/bin/bash
# 雪球爬虫（接口版）执行脚本
#
# 日志（两处，各司其职）：
#   本脚本 + python 的输出 → stdout/stderr，由 cron 重定向到 /data/logs/cron/xueqiu.log
#   python 的模块日志       → $XUEQIU_DATA_DIR/log_api.txt（xueqiu_scraper 的 logger 写）
#
# 注：原先还额外写 run_log.txt（全量累积）与 run_fail.txt（失败摘要），与上面两处重复，
#     且 run_log.txt 会涨到 10MB+（混入页面内容），已移除。
set -uo pipefail

# 脚本目录自算（不依赖调用时的 cwd）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 配置文件：默认容器内路径；本机调试可用环境变量 CONFIG_FILE 覆盖
CONFIG_FILE="${CONFIG_FILE:-/root/apps/config.ini}"
export CONFIG_FILE

# 读取 ini（精确匹配段名与键名）
get_ini_value() {
    local section="$1" key="$2" file="$3"
    awk -F '=' -v section="$section" -v key="$key" '
        /^[[:space:]]*\[/ { s=$1; gsub(/[][[:space:]]/, "", s); next }
        s == section {
            k=$1; gsub(/^[ \t]+|[ \t]+$/, "", k)
            if (k == key) {
                v=substr($0, index($0,"=")+1); gsub(/^[ \t]+|[ \t]+$/, "", v); print v; exit
            }
        }
    ' "$file"
}

OUTPUT_DIR="$(get_ini_value xueqiu data_dir "$CONFIG_FILE")"
OUTPUT_DIR="${OUTPUT_DIR:-/data/xueqiu_data}"
export XUEQIU_DATA_DIR="$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# 请求间隔（秒）：后台运行时间不敏感，默认放大以降低风控概率
REQUEST_DELAY="${XUEQIU_REQUEST_DELAY:-2}"

cd "$SCRIPT_DIR" || { echo "无法进入脚本目录 $SCRIPT_DIR"; exit 1; }

echo "[$(date '+%F %T')] 开始运行雪球爬虫（接口版）"
python3 xueqiu_scraper.py --mode=full --request-delay "$REQUEST_DELAY"
RUN_RESULT=$?

if [ "$RUN_RESULT" -eq 0 ]; then
    echo "[$(date '+%F %T')] 运行成功"
    chown -R 1000:1001 "$OUTPUT_DIR" 2>/dev/null || true
    chmod -R 777 "$OUTPUT_DIR" 2>/dev/null || true
else
    echo "[$(date '+%F %T')] 运行失败，错误码：$RUN_RESULT"
fi

exit "$RUN_RESULT"
