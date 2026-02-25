#!/bin/bash
#
# Run 2 Parallel Embedding Workers (reduced from 3 for stability)
# Uses modulo partitioning to prevent overlap
#

set -e

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

# Check if registration is complete
cd "$BASE_DIR"
UNPROCESSED=$(sqlite3 "/Users/aviz/images-finder/data/metadata.db" \
    "SELECT COUNT(*) FROM images WHERE embedding_index IS NULL")

echo "Images waiting for embeddings: $UNPROCESSED"
echo ""

if [ $UNPROCESSED -eq 0 ]; then
    echo "✅ All images already have embeddings!"
    exit 0
fi

# Start 2 workers with different modulo values
echo "Starting 2 embedding workers..."
echo ""

# Worker 1 - processes images where id % 2 = 0
echo "Starting Worker 1 (id % 2 = 0)..."
nohup "$VENV_PYTHON" -c "
import sys
sys.path.insert(0, '$BASE_DIR')
from pathlib import Path
from src.config import load_config
from src.pipeline import IndexingPipeline

config = load_config(Path('$CONFIG'))
pipeline = IndexingPipeline(config)
pipeline.generate_embeddings_parallel(worker_id=0, num_workers=2, resume=True)
" > "$LOG_DIR/embed_worker_0.log" 2>&1 &
PID1=$!
echo "  Worker 1 started (PID: $PID1)"
sleep 2

# Worker 2 - processes images where id % 2 = 1
echo "Starting Worker 2 (id % 2 = 1)..."
nohup "$VENV_PYTHON" -c "
import sys
sys.path.insert(0, '$BASE_DIR')
from pathlib import Path
from src.config import load_config
from src.pipeline import IndexingPipeline

config = load_config(Path('$CONFIG'))
pipeline = IndexingPipeline(config)
pipeline.generate_embeddings_parallel(worker_id=1, num_workers=2, resume=True)
" > "$LOG_DIR/embed_worker_1.log" 2>&1 &
PID2=$!
echo "  Worker 2 started (PID: $PID2)"

echo ""
echo "======================================================================"
echo "  ✅ All 2 Workers Started!"
echo "======================================================================"
echo ""
echo "PIDs: $PID1, $PID2"
echo ""
echo "📊 Monitor progress:"
echo "   tail -f $LOG_DIR/embed_worker_0.log"
echo "   tail -f $LOG_DIR/embed_worker_1.log"
echo ""
echo "📈 Check status:"
echo "   ./check_parallel_progress.sh"
echo ""
echo "🛑 To stop:"
echo "   kill $PID1 $PID2"
echo ""
echo "======================================================================"

