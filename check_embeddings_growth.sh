#!/bin/bash
# Quick check: Is embeddings.npy file growing?

echo "=== Embeddings File Growth Check ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

FILE="data/embeddings.npy"
if [ -f "$FILE" ]; then
    SIZE=$(ls -lh "$FILE" | awk '{print $5}')
    SIZE_BYTES=$(stat -f%z "$FILE" 2>/dev/null || stat -c%s "$FILE" 2>/dev/null)
    SIZE_MB=$(echo "scale=2; $SIZE_BYTES / 1024 / 1024" | bc)
    echo "File size: $SIZE ($SIZE_MB MB)"
else
    echo "File does not exist"
fi

echo ""
MAX_IDX=$(sqlite3 data/metadata.db "SELECT MAX(embedding_index) FROM images WHERE embedding_index IS NOT NULL;")
echo "Max embedding_index in DB: $MAX_IDX"

RECENT=$(sqlite3 data/metadata.db "SELECT COUNT(*) FROM images WHERE embedding_index IS NOT NULL AND datetime(updated_at) > datetime('now', '-10 minutes');")
echo "New assignments (last 10 min): $RECENT"

echo ""
echo "Run this again in a few minutes to compare!"
