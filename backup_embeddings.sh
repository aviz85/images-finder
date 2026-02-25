#!/bin/bash
#
# Backup embeddings to external drive
# Run this periodically to ensure embeddings are backed up
#

LOCAL_EMBEDDINGS="/Users/aviz/images-finder/data/embeddings.npy"
EXTERNAL_EMBEDDINGS="/Volumes/My Book/images-finder-data/embeddings.npy"
EXTERNAL_BACKUP_DIR="/Volumes/My Book/images-finder-data/backups"

echo "======================================================================"
echo "  📦 Embedding Backup"
echo "======================================================================"
echo ""

# Check if external drive is mounted
if [ ! -d "/Volumes/My Book" ]; then
    echo "❌ ERROR: External drive 'My Book' not mounted!"
    echo "   Please mount the drive and try again."
    exit 1
fi

# Check if local embeddings exist
if [ ! -f "$LOCAL_EMBEDDINGS" ]; then
    echo "⚠️  Local embeddings file not found: $LOCAL_EMBEDDINGS"
    echo "   Embeddings may still be generating..."
    exit 0
fi

# Get file size
EMBEDDING_SIZE=$(du -h "$LOCAL_EMBEDDINGS" | cut -f1)
EMBEDDING_COUNT=$(python3 -c "import numpy as np; arr = np.load('$LOCAL_EMBEDDINGS'); print(len(arr))" 2>/dev/null || echo "unknown")

echo "Source:  $LOCAL_EMBEDDINGS"
echo "Size:    $EMBEDDING_SIZE"
echo "Count:   $EMBEDDING_COUNT embeddings"
echo ""
echo "Destination: $EXTERNAL_EMBEDDINGS"
echo ""

# Create backup directory if needed
mkdir -p "$EXTERNAL_BACKUP_DIR"

# Copy embeddings to external drive
echo "📤 Copying embeddings to external drive..."
cp "$LOCAL_EMBEDDINGS" "$EXTERNAL_EMBEDDINGS"

if [ $? -eq 0 ]; then
    echo "✅ Embeddings backed up successfully!"
    echo ""
    
    # Verify backup
    if [ -f "$EXTERNAL_EMBEDDINGS" ]; then
        EXTERNAL_SIZE=$(du -h "$EXTERNAL_EMBEDDINGS" | cut -f1)
        echo "✅ Backup verified: $EXTERNAL_SIZE"
        echo ""
        
        # Also create timestamped backup
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        BACKUP_FILE="$EXTERNAL_BACKUP_DIR/embeddings_backup_${TIMESTAMP}_${EMBEDDING_COUNT}emb.npy"
        cp "$LOCAL_EMBEDDINGS" "$BACKUP_FILE"
        
        if [ $? -eq 0 ]; then
            echo "✅ Timestamped backup created:"
            echo "   $BACKUP_FILE"
            echo ""
            
            # Clean up old backups (keep last 5)
            echo "🧹 Cleaning old embedding backups (keeping last 5)..."
            ls -t "$EXTERNAL_BACKUP_DIR"/embeddings_backup_*.npy 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null
        fi
    else
        echo "⚠️  Backup file not found after copy!"
    fi
else
    echo "❌ Backup failed!"
    exit 1
fi

echo ""
echo "======================================================================"







