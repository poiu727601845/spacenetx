#!/bin/bash
# monitor_index.sh
# 监控 /home/ubuntu/wechat-publisher/site/index.html 的修改
# 找出是什么进程在修改这个文件

WATCH_FILE="/home/ubuntu/wechat-publisher/site/index.html"
LOG="/home/ubuntu/wechat-publisher/logs/file_monitor.log"

echo "[$(date)] 文件监控启动" >> "$LOG"
echo "监控文件: $WATCH_FILE" >> "$LOG"

# 使用 inotifywait 监控修改事件
while inotifywait -e modify,move_to,create "$WATCH_FILE" 2>/dev/null; do
    echo "[$(date)] $WATCH_FILE 被修改" >> "$LOG"
    # 记录当前的进程列表（尝试找出谁修改了文件）
    echo "  进程列表:" >> "$LOG"
    ps aux | grep -v "grep\|ps aux" | grep -E "python|node|git|deploy|vercel" | head -10 >> "$LOG" 2>&1 || true
    echo "  ---" >> "$LOG"
done
