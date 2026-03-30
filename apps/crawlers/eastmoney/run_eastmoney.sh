#!/bin/bash
# eastmoney crawler execution script

# 加载配置
source /root/apps/config.sh

# 设置配置文件路径环境变量，确保Python脚本能找到配置文件
export CONFIG_FILE="/root/apps/config.ini"

set -euo pipefail

SCRIPT_DIR="$EASTMONEY_DIR"
PYTHON_SCRIPT="eastmoney_analyst.py"
DATA_DIR="$ANALYST_DATA_DIR"
LOG_FILE="$CRON_LOG/eastmoney_analyst.log"
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

    # if python3 /root/apps/stock_monitor/scripts/generate_html_reports.py 2>&1 | tee -a "$LOG_FILE"; then
    #     log "Python crawler executed successfully"
    # else
    #     error "Python generate_html_reports execution failed"
    # fi

    if python3 "$PYTHON_SCRIPT" 0 0 2>&1 | tee -a "$LOG_FILE"; then
        log "Python crawler executed successfully"
    else
        error "Python crawler execution failed"
    fi

    if python3 "$PYTHON_SCRIPT" 0 2 2>&1 | tee -a "$LOG_FILE"; then
        log "Python crawler executed successfully"
    else
        error "Python crawler execution failed"
    fi

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
