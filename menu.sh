#!/bin/bash

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$HOOK_DIR/hook.log"
PID_FILE="$HOOK_DIR/.hook.pid"

start_service() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "服務已在運行中 (PID: $(cat "$PID_FILE"))"
        return
    fi
    nohup "$HOOK_DIR/bin/uvicorn" main:app --port 5678 >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "服務已啟動 (PID: $!)"
}

stop_service() {
    if [ ! -f "$PID_FILE" ]; then
        echo "未找到 PID 檔案，嘗試以 pkill 結束..."
        pkill -f "uvicorn main:app"
        echo "已執行結束指令"
        return
    fi
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "服務已結束 (PID: $PID)"
    else
        echo "進程已不存在"
    fi
    rm -f "$PID_FILE"
}

show_log() {
    if [ ! -f "$LOG_FILE" ]; then
        echo "Log 檔案不存在"
        return
    fi
    echo "===== 最後 50 行 Log ($LOG_FILE) ====="
    tail -50 "$LOG_FILE"
}

while true; do
    echo ""
    echo "=============================="
    echo "   Hook Service Manager Menu  "
    echo "=============================="
    echo "1) 啟動服務 (start)"
    echo "2) 停止服務 (stop)"
    echo "3) 查看 Log 最後 50 行 (log)"
    echo "4) 離開 (exit)"
    echo "=============================="
    read -r -p "請選擇 [1-4]: " choice

    case $choice in
        1) start_service ;;
        2) stop_service  ;;
        3) show_log      ;;
        4) echo "再見！"; exit 0 ;;
        *) echo "無效選項，請輸入 1-4" ;;
    esac
done
