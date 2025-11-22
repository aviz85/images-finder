#!/bin/bash
# Quick start script - Resume all processing

echo "======================================================================"
echo "  🚀 Starting Image Processing"
echo "======================================================================"
echo ""

cd /Users/aviz/images-finder

# Check drive is mounted
if [ ! -d "/Volumes/My Book" ]; then
    echo "❌ ERROR: External drive 'My Book' not mounted!"
    echo "   Please mount the drive and try again."
    exit 1
fi

echo "✓ External drive found"
echo ""

# Start hash computation
echo "1. Starting SHA-256 hash computation..."
./restart_hash_computation.sh
echo ""

# Start image processing
echo "2. Starting image processing (registration + embedding)..."
nohup ./run_parallel_optimized.sh > parallel_startup.log 2>&1 &
sleep 3
echo "✓ Registration processes started"
echo ""

# Start dashboard
echo "3. Starting dashboard..."
python3 live_dashboard.py > dashboard.log 2>&1 &
sleep 3

if ps aux | grep -q "[l]ive_dashboard"; then
    echo "✓ Dashboard started"
else
    echo "⚠ Dashboard may have issues, check dashboard.log"
fi

echo ""
echo "======================================================================"
echo "  ✅ All Processes Started!"
echo "======================================================================"
echo ""
echo "📊 Dashboard:       http://localhost:8888"
echo "📈 Check progress:  ./check_parallel_progress.sh"
echo "🔍 Check duplicates: ./check_sha256_duplicates.sh"
echo ""
echo "📝 View logs:"
echo "   tail -f logs/process_D.log"
echo "   tail -f hash_computation.log"
echo ""
echo "🛑 To stop: pkill -f 'cli.py' && pkill -f 'compute_hashes'"
echo ""
echo "======================================================================"



