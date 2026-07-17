#!/bin/bash

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$HOOK_DIR/hook.log"
PID_FILE="$HOOK_DIR/.hook.pid"
HOOK_PORT=9000

# 顏色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

is_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

get_status() {
    if is_running; then
        echo -e "${GREEN}● 運行中${NC} (PID: $(cat "$PID_FILE"), Port: $HOOK_PORT)"
    else
        echo -e "${RED}● 已停止${NC}"
    fi
}

print_header() {
    clear
    echo ""
    local BOX_W=50
    local BORDER
    BORDER=$(printf '═%.0s' $(seq 1 $BOX_W))

    local title="Hook Service Manager"
    local tlen=${#title}
    local tlpad=$(( (BOX_W - tlen) / 2 ))
    local trpad=$(( BOX_W - tlen - tlpad ))

    echo -e "${CYAN}${BOLD}╔${BORDER}╗${NC}"
    echo -e "${CYAN}${BOLD}║$(printf '%*s' $tlpad '')${title}$(printf '%*s' $trpad '')║${NC}"
    echo -e "${CYAN}${BOLD}╠${BORDER}╣${NC}"

    local status_text
    if is_running; then
        status_text="${GREEN}● 運行中${NC} (PID: $(cat "$PID_FILE"), Port: $HOOK_PORT)"
    else
        status_text="${RED}● 已停止${NC}"
    fi
    local clean_status
    clean_status=$(echo -e "$status_text" | sed $'s/\033\\[[0-9;]*m//g')
    local slen
    slen=$(printf '%s' "$clean_status" | wc -L)
    local spad=$(( BOX_W - 8 - slen ))
    [ $spad -lt 0 ] && spad=0

    echo -e "${CYAN}${BOLD}║${NC}  狀態: $(echo -e "$status_text")$(printf '%*s' $spad '')${CYAN}${BOLD}║${NC}"

    echo -e "${CYAN}${BOLD}╚${BORDER}╝${NC}"
    echo ""
}

start_service() {
    if is_running; then
        echo -e "${YELLOW}⚠ 服務已在運行中 (PID: $(cat "$PID_FILE"))${NC}"
        return
    fi
    nohup "$HOOK_DIR/bin/uvicorn" main:app --port $HOOK_PORT >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 0.5
    if is_running; then
        echo -e "${GREEN}✓ 服務已啟動 (PID: $!)${NC}"
    else
        echo -e "${RED}✗ 服務啟動失敗，請查看 log${NC}"
    fi
}

stop_service() {
    if ! is_running; then
        echo -e "${YELLOW}⚠ 服務未在運行${NC}"
        rm -f "$PID_FILE" 2>/dev/null
        return
    fi
    PID=$(cat "$PID_FILE")
    kill "$PID" 2>/dev/null
    # 等待最多 5 秒讓進程結束
    for i in $(seq 1 10); do
        kill -0 "$PID" 2>/dev/null || break
        sleep 0.5
    done
    if kill -0 "$PID" 2>/dev/null; then
        kill -9 "$PID" 2>/dev/null
        echo -e "${YELLOW}⚠ 強制結束進程 (PID: $PID)${NC}"
    else
        echo -e "${GREEN}✓ 服務已停止 (PID: $PID)${NC}"
    fi
    rm -f "$PID_FILE"
}

restart_service() {
    echo -e "${YELLOW}⟳ 重啟中...${NC}"
    stop_service
    sleep 1
    start_service
}

show_log() {
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}⚠ Log 檔案不存在${NC}"
        return
    fi
    local lines=$(wc -l < "$LOG_FILE")
    echo -e "${CYAN}──── 最後 50 行 Log (共 $lines 行) ────${NC}"
    tail -50 "$LOG_FILE"
}

show_log_follow() {
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}⚠ Log 檔案不存在${NC}"
        return
    fi
    echo -e "${CYAN}──── 即時 Log (按 Ctrl+C 退出) ────${NC}"
    tail -f "$LOG_FILE"
}

clean_log() {
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}⚠ Log 檔案不存在${NC}"
        return
    fi
    local size=$(du -h "$LOG_FILE" | cut -f1)
    read -r -p "確定要清除 log？($size) [y/N]: " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        > "$LOG_FILE"
        echo -e "${GREEN}✓ Log 已清除${NC}"
    else
        echo -e "${YELLOW}⚠ 已取消${NC}"
    fi
}

while true; do
    print_header
    echo "  1) 啟動服務"
    echo "  2) 停止服務"
    echo "  3) 重啟服務"
    echo "  4) 查看 Log"
    echo "  5) 即時 Log (tail -f)"
    echo "  6) 清除 Log"
    echo "  7) 離開"
    echo ""
    read -r -p "  請選擇 [1-7]: " choice

    case $choice in
        1) start_service ;;
        2) stop_service  ;;
        3) restart_service ;;
        4) show_log ;;
        5) show_log_follow ;;
        6) clean_log ;;
        7) echo -e "\n  ${GREEN}再見！${NC}"; exit 0 ;;
        *) echo -e "  ${RED}無效選項，請輸入 1-7${NC}" ;;
    esac
    echo ""
    read -r -p "  按 Enter 繼續..." _
done
