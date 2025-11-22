#!/bin/bash
echo "🔄 Restarting Embedding Processes with Database Retry Logic..."
echo ""

# Start 2 embedding workers
echo "Starting embedding worker 1..."
nohup python cli.py --config config_optimized.yaml embed --resume > logs/embed_1.log 2>&1 &
PID1=$!
echo "  PID: $PID1"

sleep 2

echo "Starting embedding worker 2..."
nohup python cli.py --config config_optimized.yaml embed --resume > logs/embed_2.log 2>&1 &
PID2=$!
echo "  PID: $PID2"

echo ""
echo "✅ Embedding processes restarted!"
echo ""
echo "Monitor progress:"
echo "  tail -f logs/embed_1.log"
echo "  tail -f logs/embed_2.log"
echo "  http://localhost:8888"
echo ""
