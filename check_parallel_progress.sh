#!/bin/bash
# Quick parallel progress checker

LOG_DIR="/Users/aviz/images-finder/logs"

echo "=========================================="
echo "   Parallel Processing Progress"
echo "=========================================="
echo ""

# Check if processes are running
echo "Process Status:"
echo ""
echo "REGISTRATION (I/O bound, ~10% CPU each):"
for name in D E F; do
    pid_file="$LOG_DIR/pids/register_$name.pid"
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            cpu=$(ps -p $pid -o %cpu= | tr -d ' ')
            mem=$(ps -p $pid -o %mem= | tr -d ' ')
            time=$(ps -p $pid -o etime= | tr -d ' ')
            echo "  ✓ Register $name: RUNNING (PID $pid, CPU ${cpu}%, MEM ${mem}%, Time $time)"
        else
            echo "  ✗ Register $name: STOPPED"
        fi
    else
        echo "  - Register $name: NOT STARTED"
    fi
done
echo ""
echo "EMBEDDING (CPU bound, ~80% CPU each):"
for num in 1 2 3; do
    pid_file="$LOG_DIR/pids/embed_$num.pid"
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            cpu=$(ps -p $pid -o %cpu= | tr -d ' ')
            mem=$(ps -p $pid -o %mem= | tr -d ' ')
            time=$(ps -p $pid -o etime= | tr -d ' ')
            echo "  ✓ Embedding $num: RUNNING (PID $pid, CPU ${cpu}%, MEM ${mem}%, Time $time)"
        else
            echo "  ✗ Embedding $num: STOPPED"
        fi
    else
        echo "  - Embedding $num: NOT STARTED"
    fi
done
echo ""

# System load
echo "System Load:"
uptime | awk -F'load average:' '{print "  " $2}'
echo ""

# Database stats
echo "Database Statistics:"
python3 << 'EOF'
import sqlite3
try:
    conn = sqlite3.connect('/Volumes/My Book/images-finder-data/metadata.db')
    cur = conn.cursor()
    
    cur.execute('SELECT COUNT(*) FROM images')
    total = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM images WHERE embedding_index IS NOT NULL')
    processed = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM failed_images')
    failed = cur.fetchone()[0]
    
    print(f"  Registered: {total:,} images")
    print(f"  With embeddings: {processed:,} images")
    print(f"  Failed: {failed:,} images")
    
    if total > 0:
        pct = (processed / total) * 100 if total > 0 else 0
        print(f"  Embedding completion: {pct:.1f}%")
    
    # Estimate based on 3.17M total
    total_expected = 3_174_680
    overall_pct = (total / total_expected) * 100
    print(f"  Overall progress: {overall_pct:.1f}% ({total:,} / {total_expected:,})")
    
    conn.close()
except Exception as e:
    print(f"  Error: {e}")
EOF
echo ""

# Recent activity from each log
echo "Recent Activity (latest from each process):"
echo "Registration:"
for name in D E F; do
    log_file="$LOG_DIR/register_$name.log"
    if [ -f "$log_file" ]; then
        latest=$(tail -5 "$log_file" | grep -E "(INFO|Progress|img/s)" | tail -1)
        if [ -n "$latest" ]; then
            echo "  [$name] $latest"
        fi
    fi
done
echo ""
echo "Embedding:"
for num in 1 2 3; do
    log_file="$LOG_DIR/embed_$num.log"
    if [ -f "$log_file" ]; then
        latest=$(tail -5 "$log_file" | grep -E "(INFO|Progress|img/s)" | tail -1)
        if [ -n "$latest" ]; then
            echo "  [Worker $num] $latest"
        fi
    fi
done
echo ""

# Disk space
echo "Disk Space:"
df -h "/Volumes/My Book" | tail -1 | awk '{printf "  External: %s used / %s total (%s free)\n", $3, $2, $4}'
echo ""

echo "To view detailed logs:"
echo "  Registration: tail -f $LOG_DIR/register_{D,E,F}.log"
echo "  Embedding: tail -f $LOG_DIR/embed_{1,2,3}.log"
echo "  Main: tail -f $LOG_DIR/pipeline_main.log"
echo ""

