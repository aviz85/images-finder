#!/bin/bash
#
# Parallel Optimized Processing Script
# Processes all 3 directories simultaneously with optimizations
# - No thumbnail generation (filesystem issues + performance)
# - Parallel execution (3 processes)
# - Full resumability
# - Comprehensive logging
#

set -e

CONFIG="config_optimized.yaml"
BASE_DIR="/Users/aviz/images-finder"
DATA_DIR="/Volumes/My Book/images-finder-data"

# Directories to process
DIR_D="/Volumes/My Book/D‏"
DIR_E="/Volumes/My Book/E"
DIR_F="/Volumes/My Book/F"

# Log files
LOG_DIR="$BASE_DIR/logs"
mkdir -p "$LOG_DIR"

LOG_D="$LOG_DIR/process_D.log"
LOG_E="$LOG_DIR/process_E.log"
LOG_F="$LOG_DIR/process_F.log"
LOG_MAIN="$LOG_DIR/parallel_main.log"

# PID files
PID_D="$LOG_DIR/process_D.pid"
PID_E="$LOG_DIR/process_E.pid"
PID_F="$LOG_DIR/process_F.pid"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_MAIN"
}

# Cleanup function
cleanup() {
    log "Cleaning up processes..."
    for pid_file in "$PID_D" "$PID_E" "$PID_F"; do
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            if ps -p $pid > /dev/null 2>&1; then
                log "Stopping process $pid..."
                kill $pid 2>/dev/null || true
            fi
            rm -f "$pid_file"
        fi
    done
}

trap cleanup EXIT INT TERM

# Prevent sleep
prevent_sleep() {
    log "Activating sleep prevention..."
    caffeinate -dimsu -w $$ &
    CAFFEINATE_PID=$!
    log "Sleep prevention active (PID: $CAFFEINATE_PID)"
}

# Check prerequisites
check_system() {
    log "Checking system prerequisites..."
    
    # Check drive
    if [ ! -d "/Volumes/My Book" ]; then
        log "ERROR: External drive not mounted!"
        exit 1
    fi
    
    # Check config
    if [ ! -f "$CONFIG" ]; then
        log "ERROR: Config file not found: $CONFIG"
        exit 1
    fi
    
    # Check data directory
    if [ ! -d "$DATA_DIR" ]; then
        log "Creating data directory..."
        mkdir -p "$DATA_DIR"
    fi
    
    log "✓ All checks passed"
}

# Start processing for one directory
start_directory() {
    local dir="$1"
    local log_file="$2"
    local pid_file="$3"
    local name="$4"
    
    log "Starting process for $name..."
    log "  Directory: $dir"
    log "  Log file: $log_file"
    
    # Run pipeline in background
    cd "$BASE_DIR"
    nohup python cli.py --config "$CONFIG" run-pipeline "$dir" --resume \
        > "$log_file" 2>&1 &
    
    local pid=$!
    echo $pid > "$pid_file"
    
    log "✓ $name started (PID: $pid)"
    sleep 2
    
    # Verify it's running
    if ps -p $pid > /dev/null 2>&1; then
        log "✓ $name confirmed running"
    else
        log "✗ $name failed to start! Check $log_file"
    fi
}

# Monitor progress
monitor_progress() {
    log "Monitoring parallel processes..."
    log "Press Ctrl+C to stop all processes"
    log ""
    
    while true; do
        sleep 60  # Check every minute
        
        # Check each process
        local running=0
        local stopped=0
        
        for pid_file in "$PID_D" "$PID_E" "$PID_F"; do
            if [ -f "$pid_file" ]; then
                pid=$(cat "$pid_file")
                if ps -p $pid > /dev/null 2>&1; then
                    ((running++))
                else
                    ((stopped++))
                fi
            fi
        done
        
        log "Status: $running running, $stopped stopped"
        
        # If all stopped, exit
        if [ $running -eq 0 ]; then
            log "All processes completed!"
            break
        fi
        
        # Show quick stats
        if command -v python3 &> /dev/null; then
            python3 << 'PYTHON_STATS'
import sqlite3
try:
    conn = sqlite3.connect('/Volumes/My Book/images-finder-data/metadata.db')
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM images')
    total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM images WHERE embedding_index IS NOT NULL')
    processed = cur.fetchone()[0]
    print(f"  Database: {total:,} registered, {processed:,} with embeddings")
    conn.close()
except:
    pass
PYTHON_STATS
        fi
    done
}

# Main execution
main() {
    cd "$BASE_DIR"
    
    log "=========================================="
    log "  Parallel Optimized Processing"
    log "=========================================="
    log ""
    log "Configuration: $CONFIG"
    log "Optimizations:"
    log "  ✓ Thumbnails DISABLED (performance + filesystem fix)"
    log "  ✓ Parallel processing (3 directories)"
    log "  ✓ Checkpoints every 500 images"
    log "  ✓ Full resumability"
    log ""
    
    # System check
    check_system
    
    # Prevent sleep
    prevent_sleep
    
    # Show system info
    log "System: Apple M1, 8 cores, 16 GB RAM"
    log "Load average: $(uptime | awk -F'load average:' '{print $2}')"
    log ""
    
    # Start all three directories in parallel
    log "Starting parallel processing..."
    log ""
    
    start_directory "$DIR_D" "$LOG_D" "$PID_D" "Directory D (6.0 TB)"
    sleep 5
    
    start_directory "$DIR_E" "$LOG_E" "$PID_E" "Directory E (7.1 TB)"
    sleep 5
    
    start_directory "$DIR_F" "$LOG_F" "$PID_F" "Directory F (2.6 TB)"
    sleep 5
    
    log ""
    log "All processes started!"
    log "=========================================="
    log ""
    log "Monitor individual logs:"
    log "  tail -f $LOG_D"
    log "  tail -f $LOG_E"
    log "  tail -f $LOG_F"
    log ""
    log "Monitor this log:"
    log "  tail -f $LOG_MAIN"
    log ""
    log "=========================================="
    log ""
    
    # Monitor
    monitor_progress
    
    log ""
    log "=========================================="
    log "  Processing Complete!"
    log "=========================================="
    log ""
    
    # Final stats
    log "Generating final statistics..."
    python3 << 'PYTHON_FINAL'
import sqlite3
import os

db_path = "/Volumes/My Book/images-finder-data/metadata.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM images')
total = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM images WHERE embedding_index IS NOT NULL')
processed = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM failed_images')
failed = cur.fetchone()[0]

print(f"\nFinal Statistics:")
print(f"  Total registered: {total:,} images")
print(f"  With embeddings: {processed:,} images")
print(f"  Failed: {failed:,} images")
print(f"  Success rate: {(total-failed)/total*100:.2f}%")

conn.close()
PYTHON_FINAL
    
    log ""
    log "Next step: Build FAISS index"
    log "  python cli.py --config $CONFIG build-index"
    log ""
}

# Run main
main



