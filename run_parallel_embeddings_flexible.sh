#!/bin/bash
#
# Run N Parallel Embedding Workers (configurable)
# Uses modulo partitioning to prevent overlap
#
# Usage: ./run_parallel_embeddings_flexible.sh [NUM_WORKERS]
# Default: 6 workers (good for 8-core M1)

set -e

NUM_WORKERS=${1:-6}  # Default to 6 workers if not specified

CONFIG="config_optimized.yaml"
BASE_DIR="/Users/aviz/images-finder"
LOG_DIR="$BASE_DIR/logs"
VENV_PYTHON="$BASE_DIR/venv/bin/python"

mkdir -p "$LOG_DIR"

# Activate virtual environment
source "$BASE_DIR/venv/bin/activate"

echo "======================================================================"
echo "  🚀 Starting Parallel Embedding Generation"
echo "======================================================================"
echo ""
echo "Number of workers: $NUM_WORKERS"
echo ""

# Check if registration is complete
cd "$BASE_DIR"
UNPROCESSED=$(sqlite3 "/Volumes/My Book/images-finder-data/metadata.db" \
    "SELECT COUNT(*) FROM images WHERE embedding_index IS NULL" 2>/dev/null || \
    sqlite3 "/Users/aviz/images-finder/data/metadata.db" \
    "SELECT COUNT(*) FROM images WHERE embedding_index IS NULL")

echo "Images waiting for embeddings: $UNPROCESSED"
echo ""

if [ $UNPROCESSED -eq 0 ]; then
    echo "✅ All images already have embeddings!"
    exit 0
fi

# Stop existing workers first
echo "Stopping existing embedding workers..."
pkill -f "generate_embeddings_parallel" 2>/dev/null || true
sleep 2

# Start N workers with different modulo values
echo "Starting $NUM_WORKERS embedding workers..."
echo ""

PIDS=()

for ((i=0; i<$NUM_WORKERS; i++)); do
    echo "Starting Worker $((i+1)) (id % $NUM_WORKERS = $i)..."
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
echo "======================================================================"
echo "  ✅ All $NUM_WORKERS Workers Started!"
echo "======================================================================"
echo ""
echo "PIDs: ${PIDS[@]}"
echo ""
echo "📊 Monitor progress:"
for ((i=0; i<$NUM_WORKERS; i++)); do
    echo "   tail -f $LOG_DIR/embed_worker_${i}.log"
done
echo ""
echo "📈 Check status:"
echo "   ./check_parallel_progress.sh"
echo ""
echo "🛑 To stop:"
echo "   pkill -f 'generate_embeddings_parallel'"
echo "   # Or individually: kill ${PIDS[@]}"
echo ""
echo "======================================================================"







