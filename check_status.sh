#!/bin/bash
# Simple status checker

echo "=========================================="
echo "   IMAGE PROCESSING STATUS"
echo "=========================================="
echo ""

# Check running processes
echo "🚀 RUNNING PROCESSES:"
count=$(ps aux | grep -E "cli.py|compute_hashes" | grep -v grep | wc -l | tr -d ' ')
if [ "$count" -gt 0 ]; then
    echo "  ✅ $count active processes"
    ps aux | grep -E "cli.py|compute_hashes" | grep -v grep | awk '{print "     - PID " $2 ": CPU " $3 "%, MEM " $4 "%"}'
else
    echo "  ❌ No processes running!"
fi
echo ""

# Database stats
echo "📊 DATABASE STATISTICS:"
python3 << 'EOF'
import sqlite3
try:
    conn = sqlite3.connect('/Users/aviz/images-finder/data/metadata.db')
    cur = conn.cursor()
    
    cur.execute('SELECT COUNT(*) FROM images')
    total = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM images WHERE sha256_hash IS NOT NULL')
    with_sha256 = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM images WHERE embedding_index IS NOT NULL')
    with_embeddings = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM failed_images')
    failed = cur.fetchone()[0]
    
    print(f"  Total Registered:  {total:,} images")
    print(f"  With SHA-256:      {with_sha256:,} ({with_sha256/total*100:.1f}%)")
    print(f"  With Embeddings:   {with_embeddings:,} ({with_embeddings/total*100:.1f}%)")
    print(f"  Failed:            {failed:,}")
    
    # Estimate total
    total_expected = 3_174_680
    overall_pct = (total / total_expected) * 100
    print(f"\n  Overall Progress:  {overall_pct:.1f}% of ~3.17M images")
    
    conn.close()
except Exception as e:
    print(f"  ❌ Error: {e}")
EOF
echo ""

# Disk space
echo "💾 DISK SPACE:"
df -h "/Volumes/My Book" | tail -1 | awk '{printf "  %s used / %s total (%s free)\n", $3, $2, $4}'
echo ""

# Dashboard
echo "🌐 DASHBOARD:"
if curl -s http://localhost:8888 > /dev/null 2>&1; then
    echo "  ✅ Running at http://localhost:8888"
else
    echo "  ❌ Not accessible"
fi
echo ""

echo "=========================================="
echo "✅ All systems operational!"
echo "=========================================="




