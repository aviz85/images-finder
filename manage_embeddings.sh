#!/bin/bash
#
# Embedding Generation Manager
# - Start/Stop/Status of embedding generation
# - Runs in background, can be resumed after stop
#

set -e

BASE_DIR="/Users/aviz/images-finder"
CONFIG="config_optimized.yaml"
LOG_DIR="$BASE_DIR/logs"
VENV_PYTHON="$BASE_DIR/venv/bin/python"
PID_FILE="$LOG_DIR/embedding_workers.pid"

cd "$BASE_DIR"

# Function to check if workers are running
check_workers() {
    pkill -0 -f "generate_embeddings_parallel" 2>/dev/null && return 0 || return 1
}

# Function to stop workers
stop_workers() {
    echo "Stopping embedding workers..."
    if check_workers; then
        pkill -f "generate_embeddings_parallel"
        sleep 2
        
        # Force kill if still running
        if check_workers; then
            echo "Force stopping..."
            pkill -9 -f "generate_embeddings_parallel"
            sleep 1
        fi
        
        rm -f "$PID_FILE"
        echo "✅ Workers stopped"
    else
        echo "No workers running"
    fi
}

# Function to show status
show_status() {
    echo "=========================================="
    echo "  📊 Embedding Generation Status"
    echo "=========================================="
    echo ""
    
    if check_workers; then
        echo "Status: 🟢 RUNNING"
        echo ""
        echo "Active Workers:"
        ps aux | grep "generate_embeddings_parallel" | grep -v grep | awk '{print "  PID " $2 ": " $11 " " $12 " " $13}'
        echo ""
        echo "Recent Logs:"
        if [ -d "$LOG_DIR" ]; then
            for log in "$LOG_DIR"/embed_worker_*.log; do
                if [ -f "$log" ]; then
                    worker_num=$(basename "$log" | sed 's/embed_worker_\([0-9]*\)\.log/\1/')
                    last_line=$(tail -1 "$log" 2>/dev/null | head -c 80)
                    echo "  Worker $worker_num: $last_line"
                fi
            done
        fi
    else
        echo "Status: 🔴 STOPPED"
    fi
    
    echo ""
    
    # Check database status
    DB_PATH=$(python3 -c "
from pathlib import Path
from src.config import load_config
config = load_config(Path('$CONFIG'))
print(config.db_path)
" 2>/dev/null || echo "data/metadata.db")
    
    if [ -f "$DB_PATH" ]; then
        UNPROCESSED=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM images WHERE embedding_index IS NULL" 2>/dev/null || echo "0")
        WITH_EMBEDDINGS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM images WHERE embedding_index IS NOT NULL" 2>/dev/null || echo "0")
        TOTAL=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM images" 2>/dev/null || echo "0")
        
        echo "Database Status:"
        echo "  Total images: $TOTAL"
        echo "  With embeddings: $WITH_EMBEDDINGS"
        echo "  Remaining: $UNPROCESSED"
        
        if [ "$UNPROCESSED" -gt 0 ] && [ "$TOTAL" -gt 0 ]; then
            PERCENT=$((WITH_EMBEDDINGS * 100 / TOTAL))
            echo "  Progress: $PERCENT%"
        fi
    fi
    
    echo ""
}

# Function to start workers
start_workers() {
    NUM_WORKERS=${1:-}
    
    if check_workers; then
        echo "⚠️  Workers are already running!"
        echo "Use './manage_embeddings.sh stop' to stop them first"
        return 1
    fi
    
    echo "Starting embedding generation..."
    
    # Calculate optimal workers if not specified
    if [ -z "$NUM_WORKERS" ]; then
        CPU_CORES=$(sysctl -n hw.ncpu 2>/dev/null || python3 -c "import os; print(os.cpu_count())")
        NUM_WORKERS=$(python3 -c "import math; print(max(1, int($CPU_CORES * 0.8)))")
        echo "Auto-calculated: $NUM_WORKERS workers (80% of $CPU_CORES CPU cores)"
    else
        echo "Using: $NUM_WORKERS workers"
    fi
    
    # Start the optimized script in background
    nohup "$BASE_DIR/generate_embeddings_optimized.sh" "$NUM_WORKERS" --background > "$LOG_DIR/embedding_manager.log" 2>&1 &
    MANAGER_PID=$!
    
    # Save PID
    mkdir -p "$LOG_DIR"
    echo "$MANAGER_PID" > "$PID_FILE"
    
    echo "✅ Started embedding generation (Manager PID: $MANAGER_PID)"
    echo ""
    echo "Monitor with:"
    echo "  ./manage_embeddings.sh status"
    echo "  tail -f $LOG_DIR/embed_worker_*.log"
    echo ""
    sleep 3
    
    # Check if workers started
    if check_workers; then
        echo "✅ Workers are running!"
    else
        echo "⚠️  Workers may still be starting... check logs:"
        echo "  tail -f $LOG_DIR/embedding_manager.log"
    fi
}

# Function to show logs
show_logs() {
    WORKER_NUM=${1:-}
    
    if [ -n "$WORKER_NUM" ]; then
        LOG_FILE="$LOG_DIR/embed_worker_${WORKER_NUM}.log"
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            echo "Log file not found: $LOG_FILE"
        fi
    else
        echo "Showing all worker logs (Ctrl+C to exit)..."
        echo ""
        tail -f "$LOG_DIR"/embed_worker_*.log 2>/dev/null || echo "No log files found"
    fi
}

# Main command handling
case "${1:-status}" in
    start)
        start_workers "${2:-}"
        ;;
    stop)
        stop_workers
        ;;
    restart)
        stop_workers
        sleep 2
        start_workers "${2:-}"
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "${2:-}"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs} [options]"
        echo ""
        echo "Commands:"
        echo "  start [workers]  - Start embedding generation (auto-calc workers if not specified)"
        echo "  stop             - Stop all embedding workers"
        echo "  restart [workers]- Restart embedding generation"
        echo "  status           - Show current status"
        echo "  logs [worker_id] - Show logs (all workers or specific worker)"
        echo ""
        echo "Examples:"
        echo "  $0 start          # Start with auto-calculated workers"
        echo "  $0 start 6        # Start with 6 workers"
        echo "  $0 stop           # Stop all workers"
        echo "  $0 status         # Check status"
        echo "  $0 logs           # Show all logs"
        echo "  $0 logs 0         # Show worker 0 logs"
        exit 1
        ;;
esac

