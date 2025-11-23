#!/bin/bash
#
# Run 3 Parallel Embedding Workers
# Uses modulo partitioning to prevent overlap
#

set -e

CONFIG="config_optimized.yaml"
BASE_DIR="/Users/aviz/images-finder"
LOG_DIR="$BASE_DIR/logs"

mkdir -p "$LOG_DIR"

echo "======================================================================"
echo "  🚀 Starting Parallel Embedding Generation"
echo "======================================================================"
echo ""

# Check if registration is complete
cd "$BASE_DIR"
UNPROCESSED=$(sqlite3 "/Volumes/My Book/images-finder-data/metadata.db" \
    "SELECT COUNT(*) FROM images WHERE embedding_index IS NULL")

echo "Images waiting for embeddings: $UNPROCESSED"
echo ""

if [ $UNPROCESSED -eq 0 ]; then
    echo "✅ All images already have embeddings!"
    exit 0
fi

# Start 3 workers with different modulo values
echo "Starting 3 embedding workers..."
echo ""

# Worker 1 - processes images where id % 3 = 0
echo "Starting Worker 1 (id % 3 = 0)..."
nohup python3 -c "
import sys
sys.path.insert(0, '$BASE_DIR')
from src.config import Config
from src.pipeline import IndexingPipeline

config = Config.from_yaml('$CONFIG')
pipeline = IndexingPipeline(config)
pipeline.generate_embeddings_parallel(worker_id=0, num_workers=3, resume=True)
" > "$LOG_DIR/embed_worker_0.log" 2>&1 &
PID1=$!
echo "  Worker 1 started (PID: $PID1)"
sleep 2

# Worker 2 - processes images where id % 3 = 1
echo "Starting Worker 2 (id % 3 = 1)..."
nohup python3 -c "
import sys
sys.path.insert(0, '$BASE_DIR')
from src.config import Config
from src.pipeline import IndexingPipeline

config = Config.from_yaml('$CONFIG')
pipeline = IndexingPipeline(config)
pipeline.generate_embeddings_parallel(worker_id=1, num_workers=3, resume=True)
" > "$LOG_DIR/embed_worker_1.log" 2>&1 &
PID2=$!
echo "  Worker 2 started (PID: $PID2)"
sleep 2

# Worker 3 - processes images where id % 3 = 2
echo "Starting Worker 3 (id % 3 = 2)..."
nohup python3 -c "
import sys
sys.path.insert(0, '$BASE_DIR')
from src.config import Config
from src.pipeline import IndexingPipeline

config = Config.from_yaml('$CONFIG')
pipeline = IndexingPipeline(config)
pipeline.generate_embeddings_parallel(worker_id=2, num_workers=3, resume=True)
" > "$LOG_DIR/embed_worker_2.log" 2>&1 &
PID3=$!
echo "  Worker 3 started (PID: $PID3)"

echo ""
echo "======================================================================"
echo "  ✅ All 3 Workers Started!"
echo "======================================================================"
echo ""
echo "PIDs: $PID1, $PID2, $PID3"
echo ""
echo "📊 Monitor progress:"
echo "   tail -f $LOG_DIR/embed_worker_0.log"
echo "   tail -f $LOG_DIR/embed_worker_1.log"
echo "   tail -f $LOG_DIR/embed_worker_2.log"
echo ""
echo "📈 Check status:"
echo "   ./check_parallel_progress.sh"
echo ""
echo "🛑 To stop:"
echo "   kill $PID1 $PID2 $PID3"
echo ""
echo "======================================================================"

