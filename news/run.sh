#!/bin/bash
# News crawler execution script

set -euo pipefail

SCRIPT_DIR="/root/news"
PYTHON_SCRIPT="crawl_save_news.py"
DATA_DIR="/data/news"
LOG_FILE="/var/log/news_crawler.log"
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
    log "Starting Python crawler..."
    
    cd "$SCRIPT_DIR" || {
        error "Cannot change to directory: $SCRIPT_DIR"
        return 1
    }
    
    if ! command -v python3 >/dev/null 2>&1; then
        error "python3 command not found"
        return 1
    fi
    
    if python3 "$PYTHON_SCRIPT" 2>&1 | tee -a "$LOG_FILE"; then
        log "Python crawler executed successfully"
        return 0
    else
        error "Python crawler execution failed"
        return 1
    fi
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
    log "=== News crawler task started ==="
    
    if ! check_prerequisites; then
        error "Prerequisites check failed, exiting"
        exit 1
    fi
    
    if ! run_python_crawler; then
        error "Python crawler execution failed, skipping permission setting"
        exit 1
    fi
    
    if ! set_file_permissions; then
        error "File permission setting failed"
        exit 1
    fi
    
    log "=== News crawler task completed ==="
}

trap 'error "Script interrupted"; cleanup; exit 1' INT TERM

main "$@"
