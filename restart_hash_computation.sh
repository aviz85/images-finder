#!/bin/bash
# Restart SHA-256 hash computation

echo "🔄 Restarting SHA-256 Hash Computation..."
echo ""

# Stop existing processes
pkill -f "compute_hashes" 2>/dev/null
sleep 2

# Start new process
cd /Users/aviz/images-finder
nohup python compute_hashes_simple.py > hash_computation.log 2>&1 &

sleep 3

# Check if started
if ps aux | grep -q "[c]ompute_hashes"; then
    echo "✅ Hash computation restarted!"
    echo ""
    echo "📊 Monitor progress:"
    echo "   ./check_sha256_duplicates.sh"
    echo ""
    echo "📋 View log:"
    echo "   tail -f hash_computation.log"
else
    echo "❌ Failed to start. Check hash_computation.log for errors."
fi



