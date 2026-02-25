#!/bin/bash
#
# Optimized Parallel Embedding Generation
# - Calculates optimal workers based on CPU cores (80% usage, 20% reserved)
# - Saves embeddings correctly to prevent loss
# - Maximizes resource utilization
#

set -e

CONFIG="config_optimized.yaml"
BASE_DIR="/Users/aviz/images-finder"
LOG_DIR="$BASE_DIR/logs"
VENV_PYTHON="$BASE_DIR/venv/bin/python"

mkdir -p "$LOG_DIR"

# Calculate optimal number of workers (80% of CPU cores, 20% reserved)
CPU_CORES=$(sysctl -n hw.ncpu 2>/dev/null || python3 -c "import os; print(os.cpu_count())")
OPTIMAL_WORKERS=$(python3 -c "import math; print(max(1, int($CPU_CORES * 0.8)))")

NUM_WORKERS=${1:-$OPTIMAL_WORKERS}  # Use argument or calculated optimal

# Activate virtual environment
source "$BASE_DIR/venv/bin/activate"

echo "=========================================="
echo "  🚀 Optimized Parallel Embedding Generation"
echo "=========================================="
echo ""
echo "System Resources:"
echo "  CPU Cores: $CPU_CORES"
echo "  Optimal Workers (80% usage): $OPTIMAL_WORKERS"
echo "  Using Workers: $NUM_WORKERS"
echo ""

cd "$BASE_DIR"

# Check database
DB_PATH=$(python3 -c "
from pathlib import Path
from src.config import load_config
config = load_config(Path('$CONFIG'))
print(config.db_path)
" 2>/dev/null || echo "data/metadata.db")

if [ ! -f "$DB_PATH" ]; then
    echo "❌ Database not found at $DB_PATH"
    exit 1
fi

UNPROCESSED=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM images WHERE embedding_index IS NULL" 2>/dev/null || echo "0")
TOTAL=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM images" 2>/dev/null || echo "0")

echo "Images Status:"
echo "  Total images: $TOTAL"
echo "  Waiting for embeddings: $UNPROCESSED"
echo ""

if [ "$UNPROCESSED" -eq 0 ]; then
    echo "✅ All images already have embeddings!"
    exit 0
fi

# Stop existing workers
echo "Stopping existing embedding workers..."
pkill -f "generate_embeddings_parallel" 2>/dev/null || true
sleep 2

# Start workers
echo "Starting $NUM_WORKERS parallel workers..."
echo ""

PIDS=()

for ((i=0; i<$NUM_WORKERS; i++)); do
    echo "Starting Worker $((i+1))/$NUM_WORKERS (id % $NUM_WORKERS = $i)..."
    nohup "$VENV_PYTHON" -c "
import sys
sys.path.insert(0, '$BASE_DIR')
from pathlib import Path
from src.config import load_config
from src.pipeline import IndexingPipeline

config = load_config(Path('$CONFIG'))
pipeline = IndexingPipeline(config)
pipeline.generate_embeddings_parallel(worker_id=$i, num_workers=$NUM_WORKERS, resume=True)
" > "$LOG_DIR/embed_worker_${i}.log" 2>&1 &
    
    PID=$!
    PIDS+=($PID)
    echo "  Worker $((i+1)) started (PID: $PID)"
    sleep 2
done

echo ""
echo "✅ All $NUM_WORKERS workers started!"
echo ""
echo "Monitor progress:"
echo "  tail -f $LOG_DIR/embed_worker_*.log"
echo "  ./check_status.sh"
echo ""
echo "Stop all workers:"
echo "  pkill -f 'generate_embeddings_parallel'"
echo ""

# Wait for user to stop (or run in background)
if [ "${2:-}" != "--background" ]; then
    echo "Workers are running in background. Press Ctrl+C to exit (workers will continue)."
    echo ""
    read -p "Press Enter to continue monitoring or Ctrl+C to exit..."
fi

