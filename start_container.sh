#!/bin/bash

# 创建必要的系统目录
mkdir -p /var/run/sshd
mkdir -p /var/log/nginx
mkdir -p /var/log/cron
mkdir -p /root/.openclaw/workspace

# 数据卷目录（/data 若是空挂载，保证各应用子目录存在）
mkdir -p /data/logs/cron
mkdir -p /data/news
mkdir -p /data/iptv
mkdir -p /data/xueqiu_data
mkdir -p /data/analyst_data
mkdir -p /data/stock_monitor_data/database
mkdir -p /data/blog

# 启动 SSH
/usr/sbin/sshd -D -e &
SSH_PID=$!

# 启动 Nginx
/usr/sbin/nginx -g "daemon off;" &
NGINX_PID=$!

# 启动 Cron
/usr/sbin/cron -f &
CRON_PID=$!

# 启动 Stock Monitor（带自动重启：进程退出后 5 秒重新拉起）
run_stock_monitor() {
    while true; do
        echo "[stock_monitor] starting..."
        cd /root/apps/stock_monitor && python3 start_app.py 2>&1
        echo "[stock_monitor] exited (code $?), restart in 5s..."
        sleep 5
    done
}
run_stock_monitor &
SMD_PID=$!

# 启动 OpenClaw（可选，默认关闭；ENABLE_OPENCLAW=1 且已安装时才启动）
OPENCLAW_PID=""
if [ "${ENABLE_OPENCLAW:-0}" = "1" ] && command -v openclaw &> /dev/null; then
    # 初始化 OpenClaw 工作空间
    mkdir -p /var/log/openclaw
    cd /root/.openclaw/workspace
    # 启动 OpenClaw 网关
    #openclaw gateway start > /var/log/openclaw/gateway.log 2>&1 &
    openclaw gateway run > /var/log/openclaw/gateway.log 2>&1 &
    OPENCLAW_PID=$!
    echo "OpenClaw started with PID: $OPENCLAW_PID"
else
    echo "OpenClaw disabled or not found, skipping startup"
fi

# 等待所有进程（$SMD_PID 是重启循环，正常情况下不会退出）
trap 'echo "Received SIGTERM, shutting down..."; pkill -f start_app.py 2>/dev/null; kill $SSH_PID $NGINX_PID $CRON_PID $SMD_PID ${OPENCLAW_PID:+"$OPENCLAW_PID"} 2>/dev/null; exit 0' TERM INT
wait $SSH_PID $NGINX_PID $CRON_PID $SMD_PID ${OPENCLAW_PID:+"$OPENCLAW_PID"}
