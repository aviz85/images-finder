#!/bin/bash
#
# Backup local database to external drive
# DISABLED: Automatic backups disabled to prevent disk space issues
# Manual: ./backup_local_db.sh (run manually when needed)
#

LOCAL_DB="/Users/aviz/images-finder/data/metadata.db"
LOCAL_BACKUP_DIR="/Users/aviz/images-finder/data/backups"
EXTERNAL_BACKUP_DIR="/Volumes/My Book/images-finder-data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create local backup directory
mkdir -p "$LOCAL_BACKUP_DIR"

# Check if database exists
if [ ! -f "$LOCAL_DB" ]; then
    echo "$(date): ❌ Database not found: $LOCAL_DB"
    exit 1
fi

echo ""
echo "=========================================="
echo "  Database Backup - $(date)"
echo "=========================================="

# Get counts for backup name
REGISTERED=$(sqlite3 "$LOCAL_DB" "SELECT COUNT(*) FROM images;" 2>/dev/null || echo "unknown")
EMBEDDINGS=$(sqlite3 "$LOCAL_DB" "SELECT COUNT(embedding_index) FROM images;" 2>/dev/null || echo "unknown")

LOCAL_BACKUP_FILE="$LOCAL_BACKUP_DIR/metadata_backup_${TIMESTAMP}_${REGISTERED}reg_${EMBEDDINGS}emb.db"

echo "📦 Backing up database..."
echo "   Source: $LOCAL_DB"
echo "   Destination: $LOCAL_BACKUP_FILE"

# Checkpoint WAL first
sqlite3 "$LOCAL_DB" "PRAGMA wal_checkpoint(TRUNCATE);" 2>/dev/null

# Copy database to local backup
cp "$LOCAL_DB" "$LOCAL_BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Local backup complete!"
    echo "   Registered: $REGISTERED"
    echo "   Embeddings: $EMBEDDINGS"
    ls -lh "$LOCAL_BACKUP_FILE"
    
    # Clean up old local backups (keep only last 1 to save disk space)
    echo ""
    echo "🧹 Cleaning old local backups (keeping only last 1 to save disk space)..."
    ls -t "$LOCAL_BACKUP_DIR"/metadata_backup_*.db 2>/dev/null | tail -n +2 | xargs rm -f 2>/dev/null
    
    # Try to sync to external drive if mounted
    if [ -d "/Volumes/My Book" ]; then
        echo ""
        echo "📤 Syncing to external drive..."
        cp "$LOCAL_BACKUP_FILE" "$EXTERNAL_BACKUP_DIR/" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "✅ External backup synced!"
            # Clean up old external backups (keep last 10)
            ls -t "$EXTERNAL_BACKUP_DIR"/metadata_backup_*.db 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null
        else
            echo "⚠️  Could not sync to external drive (permissions)"
        fi
    else
        echo "⚠️  External drive not mounted, skipping external sync"
    fi
    
    echo ""
    echo "📋 Current local backups:"
    ls -lht "$LOCAL_BACKUP_DIR"/metadata_backup_*.db 2>/dev/null | head -3
else
    echo "❌ Backup failed!"
    exit 1
fi

