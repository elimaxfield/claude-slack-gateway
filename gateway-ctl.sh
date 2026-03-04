#!/bin/bash
# Gateway control script
# Usage: gateway-ctl.sh [start|stop|status|logs]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/gateway.pid"
LOG_FILE="$SCRIPT_DIR/gateway.log"

case "$1" in
    start)
        if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "Gateway already running (PID: $(cat "$PID_FILE"))"
            exit 1
        fi
        echo "Starting gateway..."
        python3 "$SCRIPT_DIR/gateway.py" --daemon
        sleep 1
        if [ -f "$PID_FILE" ]; then
            echo "Gateway started (PID: $(cat "$PID_FILE"))"
        else
            echo "Failed to start gateway. Check logs: $LOG_FILE"
            exit 1
        fi
        ;;
    stop)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "Stopping gateway (PID: $PID)..."
                kill "$PID"
                rm -f "$PID_FILE"
                echo "Gateway stopped"
            else
                echo "Gateway not running (stale PID file)"
                rm -f "$PID_FILE"
            fi
        else
            echo "Gateway not running"
        fi
        ;;
    status)
        if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "Gateway running (PID: $(cat "$PID_FILE"))"
        else
            echo "Gateway not running"
        fi
        ;;
    logs)
        tail -f "$LOG_FILE"
        ;;
    *)
        echo "Usage: $0 {start|stop|status|logs}"
        exit 1
        ;;
esac
