#!/bin/bash
# 每日：停库 -> 同步数据 -> 起库（本机 stockdb，以 jgyang 非 root 运行）
#
# 部署位置（NAS 宿主机）: /vol1/1000/docker/my-ubuntu/apps/stockdb/sync_and_restart.sh
# crontab（用户 jgyang）:
#   @reboot sleep 30; cd /vol1/1000/docker/my-ubuntu/apps/stockdb && ./stockdb -d -s start ./stockdb.conf >> ./sync_cron.log 2>&1
#   0 16 * * * /vol1/1000/docker/my-ubuntu/apps/stockdb/sync_and_restart.sh
cd /vol1/1000/docker/my-ubuntu/apps/stockdb || exit 1
LOG=./sync_cron.log
ts() { date '+%F %T'; }

echo "[$(ts)] ===== sync task start =====" >> "$LOG"

echo "[$(ts)] stopping stockdb ..." >> "$LOG"
./stockdb -d -s stop ./stockdb.conf >> "$LOG" 2>&1
echo "[$(ts)] stop exit=$?" >> "$LOG"
sleep 3

echo "[$(ts)] running sync_data ..." >> "$LOG"
./sync_data >> "$LOG" 2>&1
rc=$?
echo "[$(ts)] sync_data exit=$rc" >> "$LOG"

echo "[$(ts)] starting stockdb ..." >> "$LOG"
./stockdb -d -s start ./stockdb.conf >> "$LOG" 2>&1
echo "[$(ts)] start exit=$?" >> "$LOG"

if [ "$rc" -eq 0 ]; then
    echo "[$(ts)] ===== done (sync OK) =====" >> "$LOG"
else
    echo "[$(ts)] ===== done (sync FAILED rc=$rc) =====" >> "$LOG"
fi
