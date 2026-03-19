#!/bin/bash
# 简单的容器启动脚本

# 启动 cron（后台运行）
service cron start

# 启动 nginx（后台运行）
service nginx start

cd /root/stock_monitor && python3 start_app.py &

# 启动 sshd（前台运行，这样容器不会退出）
exec /usr/sbin/sshd -D -e
