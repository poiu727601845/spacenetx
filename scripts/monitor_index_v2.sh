#!/bin/bash
# monitor_index_v2.sh
# 使用 fuser + lsof 找出谁在占用/修改 index.html

WATCH_FILE="/home/ubuntu/wechat-publisher/site/index.html"
LOG="/home/ubuntu/wechat-publisher/logs/file_monitor.log"

echo "[$(date)] 精准监控启动" >> "$LOG"
echo "监控文件: $WATCH_FILE" >> "$LOG"

# 使用 inotifywait 的 --format 选项记录事件
inotifywait -m -e modify,move_to,create,delete \
    --format '%e %T' \
    "$WATCH_FILE" 2>/dev/null | while read EVENT TIME; do
    echo "[$(date)] 事件: $EVENT" >> "$LOG"
    
    # 记录当前正在写入该文件的进程
    FUSER=$(fuser "$WATCH_FILE" 2>/dev/null | tr ' ' '\n' | grep -v "^$" | head -5)
    if [ -n "$FUSER" ]; then
        echo "  占用进程 (fuser): $FUSER" >> "$LOG"
        ps -p $FUSER -o pid,user,cmd >> "$LOG" 2>/dev/null || true
    fi
    
    # 记录当前 Python/Node 进程
    echo "  当前进程列表:" >> "$LOG"
    ps aux | grep -E "python|node|git|deploy|vercel" | grep -v "grep\|monitor" | head -10 >> "$LOG" 2>/dev/null || true
    echo "  ---" >> "$LOG"
done
