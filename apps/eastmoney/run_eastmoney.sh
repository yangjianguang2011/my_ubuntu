#!/bin/bash
# eastmoney crawler execution script

set -euo pipefail

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

PYTHON_SCRIPT="eastmoney_analyst.py"
DATA_DIR="$(get_ini_value eastmoney data_dir "$CONFIG_FILE")"
DATA_DIR="${DATA_DIR:-/data/analyst_data}"
LOG_DIR="$(get_ini_value paths log_dir "$CONFIG_FILE")"
LOG_DIR="${LOG_DIR:-/data/logs}"
LOG_FILE="$LOG_DIR/cron/eastmoney_analyst.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

log() {
    echo "[$TIMESTAMP] INFO: $1" | tee -a "$LOG_FILE"
}

warn() {
    echo "[$TIMESTAMP] WARN: $1" | tee -a "$LOG_FILE"
}

error() {
    echo "[$TIMESTAMP] ERROR: $1" | tee -a "$LOG_FILE"
}

check_prerequisites() {
    if [ ! -d "$SCRIPT_DIR" ]; then
        error "Script directory does not exist: $SCRIPT_DIR"
        return 1
    fi

    if [ ! -f "$SCRIPT_DIR/$PYTHON_SCRIPT" ]; then
        error "Python script does not exist: $SCRIPT_DIR/$PYTHON_SCRIPT"
        return 1
    fi

    if [ ! -d "$DATA_DIR" ]; then
        warn "Data directory does not exist, creating: $DATA_DIR"
        mkdir -p "$DATA_DIR" || {
            error "Failed to create data directory: $DATA_DIR"
            return 1
        }
    fi

    local log_dir=$(dirname "$LOG_FILE")
    if [ ! -d "$log_dir" ]; then
        mkdir -p "$log_dir"
    fi
}

run_one() {
    local category="$1" period="$2"
    log "开始采集：类别=$category 期间=$period"
    if python3 "$PYTHON_SCRIPT" --category "$category" --period "$period" 2>&1 | tee -a "$LOG_FILE"; then
        log "采集成功：类别=$category 期间=$period"
    else
        error "采集失败：类别=$category 期间=$period"
    fi
}

run_python_crawler() {
    log "Starting PYTHON_SCRIPT..."

    cd "$SCRIPT_DIR" || {
        error "Cannot change to directory: $SCRIPT_DIR"
        return 1
    }

    if ! command -v python3 >/dev/null 2>&1; then
        error "python3 command not found"
        return 1
    fi

    # 采集组合（英文 slug，便于 shell 书写；用 --list 查看全部可选值）
    run_one all 2026_latest
    run_one all 3m

    return 0
}

set_file_permissions() {
    log "Setting file permissions..."

    if [ ! -d "$DATA_DIR" ]; then
        error "Data directory does not exist: $DATA_DIR"
        return 1
    fi

    if chown -R 1000:1001 "$DATA_DIR" 2>&1 | tee -a "$LOG_FILE"; then
        log "File ownership set successfully"
    else
        error "File ownership setting failed"
        return 1
    fi

    if chmod -R 777 "$DATA_DIR" 2>&1 | tee -a "$LOG_FILE"; then
        log "File permissions set successfully"
    else
        error "File permissions setting failed"
        return 1
    fi

}

cleanup() {
    log "Performing cleanup..."
}

main() {
    log "=== Eastmoney PYTHON_SCRIPT task started ==="

    if ! check_prerequisites; then
        error "Prerequisites check failed, exiting"
        exit 1
    fi

    if ! run_python_crawler; then
        error "Python PYTHON_SCRIPT execution failed, skipping permission setting"
        exit 1
    fi

    if ! set_file_permissions; then
        error "File permission setting failed"
        exit 1
    fi

    log "=== Eastmoney crawler task completed ==="
}

trap 'error "Script interrupted"; cleanup; exit 1' INT TERM

main "$@"
