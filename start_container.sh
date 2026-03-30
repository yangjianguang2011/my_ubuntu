#!/bin/bash

# 创建必要的目录
mkdir -p /var/run/sshd
mkdir -p /var/log/nginx
mkdir -p /var/log/cron
mkdir -p /var/log/openclaw
mkdir -p /root/.openclaw/workspace

# 启动 SSH
/usr/sbin/sshd -D -e &
SSH_PID=$!

# 启动 Nginx
/usr/sbin/nginx -g "daemon off;" &
NGINX_PID=$!

# 启动 Cron
/usr/sbin/cron -f &
CRON_PID=$!


cd /root/apps/stock_monitor && python3 start_app.py 2>&1 &
SMD_PID=$!

# 启动 OpenClaw（在后台运行）
if command -v openclaw &> /dev/null; then
    # 初始化 OpenClaw 工作空间
    cd /root/.openclaw/workspace
    # 启动 OpenClaw 网关
    #openclaw gateway start > /var/log/openclaw/gateway.log 2>&1 &
    openclaw gateway run > /var/log/openclaw/gateway.log 2>&1 &
    OPENCLAW_PID=$!
    echo "OpenClaw started with PID: $OPENCLAW_PID"
else
    echo "OpenClaw not found, skipping startup"
fi

# 等待所有进程
wait $SSH_PID $NGINX_PID $CRON_PID ${OPENCLAW_PID:-""}
