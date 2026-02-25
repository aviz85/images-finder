#!/bin/bash
#
# Watchdog script to monitor and restart embedding workers
# Runs hourly to ensure workers stay running
#

LOG_FILE="/Users/aviz/images-finder/logs/watchdog.log"
BASE_DIR="/Users/aviz/images-finder"
SCRIPT="$BASE_DIR/run_parallel_embeddings.sh"

# Create log directory if needed
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "Watchdog check starting..."

# Check if workers are running
WORKER_COUNT=$(ps aux | grep -E "generate_embeddings_parallel" | grep -v grep | wc -l | tr -d ' ')

log "Current worker count: $WORKER_COUNT"

# Expected: 2 workers
EXPECTED_WORKERS=2

if [ "$WORKER_COUNT" -lt "$EXPECTED_WORKERS" ]; then
    log "⚠️  WARNING: Only $WORKER_COUNT workers running (expected $EXPECTED_WORKERS)"
    log "Restarting workers..."
    
    # Stop any existing workers first
    pkill -f "generate_embeddings_parallel" 2>/dev/null
    sleep 2
    
    # Start workers
    cd "$BASE_DIR"
    bash "$SCRIPT" >> "$LOG_FILE" 2>&1
    
    sleep 5
    
    # Verify they started
    NEW_COUNT=$(ps aux | grep -E "generate_embeddings_parallel" | grep -v grep | wc -l | tr -d ' ')
    
    if [ "$NEW_COUNT" -ge "$EXPECTED_WORKERS" ]; then
        log "✅ Workers restarted successfully ($NEW_COUNT running)"
    else
        log "❌ ERROR: Failed to restart workers (only $NEW_COUNT running)"
    fi
else
    log "✅ All workers running ($WORKER_COUNT/$EXPECTED_WORKERS)"
fi

# Also check caffeinate
CAFFEINATE_COUNT=$(ps aux | grep caffeinate | grep -v grep | wc -l | tr -d ' ')

if [ "$CAFFEINATE_COUNT" -eq 0 ]; then
    log "⚠️  WARNING: Caffeinate not running! Starting it..."
    caffeinate -dims &
    sleep 1
    if ps aux | grep caffeinate | grep -v grep > /dev/null; then
        log "✅ Caffeinate started"
    else
        log "❌ ERROR: Failed to start caffeinate"
    fi
else
    log "✅ Caffeinate running"
fi

# Check disk space (check main disk, not just data directory)
DISK_INFO=$(df -h "/System/Volumes/Data" | tail -1)
DISK_PCT=$(echo "$DISK_INFO" | awk '{print $5}' | sed 's/%//')
DISK_FREE=$(echo "$DISK_INFO" | awk '{print $4}')

if [ "$DISK_PCT" -ge 98 ]; then
    log "⚠️  WARNING: Disk space critical (${DISK_PCT}% used, ${DISK_FREE} free)"
    log "Cleaning old backups and corrupted files..."
    
    # Keep only most recent backup
    ls -t "$BASE_DIR/data/backups"/metadata_backup_*.db 2>/dev/null | tail -n +2 | xargs rm -f 2>/dev/null
    
    # Remove old corrupted embeddings files
    find "$BASE_DIR/data" -name "embeddings.npy.corrupted*" -mtime +1 -delete 2>/dev/null
    
    log "✅ Cleanup complete"
else
    log "✅ Disk space OK (${DISK_PCT}% used, ${DISK_FREE} free)"
fi

log "Watchdog check complete"
log "=========================================="

