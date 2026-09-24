#!/bin/bash
# 雪球爬虫（接口版）执行脚本
#
# 与 apps/xueqiu/run_xueqiu.sh 的区别：
#   新版用 Chrome 过 WAF + JSON 接口，cookie 由浏览器自动维护，
#   不再需要"下载远程 cookies 文件"那套失败重试逻辑。
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

LOG_FILE="$OUTPUT_DIR/run_log.txt"
FAIL_FILE="$OUTPUT_DIR/run_fail.txt"

echo "$(date '+%Y-%m-%d %H:%M:%S') - 开始运行雪球爬虫（接口版）" >> "$LOG_FILE"

cd "$SCRIPT_DIR" || { echo "无法进入脚本目录 $SCRIPT_DIR" >> "$LOG_FILE"; exit 1; }

python3 xueqiu_scraper.py --mode=full --request-delay "$REQUEST_DELAY" >> "$LOG_FILE" 2>&1
RUN_RESULT=$?

if [ $RUN_RESULT -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 运行成功" >> "$LOG_FILE"
    [ -f "$FAIL_FILE" ] && rm -f "$FAIL_FILE"

    chown -R 1000:1001 "$OUTPUT_DIR" 2>/dev/null || true
    chmod -R 777 "$OUTPUT_DIR" 2>/dev/null || true
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 运行失败，错误码：$RUN_RESULT" >> "$LOG_FILE"
    {
        echo ""
        echo "运行失败，错误码：$RUN_RESULT"
        tail -30 "$LOG_FILE"
    } >> "$FAIL_FILE"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - 脚本执行完成" >> "$LOG_FILE"
exit $RUN_RESULT
