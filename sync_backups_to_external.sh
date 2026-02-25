#!/bin/bash
#
# Sync local backups to external drive
# Run this manually when you want to ensure backups are on external drive
#

LOCAL_BACKUP_DIR="/Users/aviz/images-finder/data/backups"
EXTERNAL_BACKUP_DIR="/Volumes/My Book/images-finder-data/backups"

echo "📤 Syncing backups to external drive..."

if [ ! -d "/Volumes/My Book" ]; then
    echo "❌ External drive not mounted!"
    exit 1
fi

# Copy all local backups to external
cp "$LOCAL_BACKUP_DIR"/metadata_backup_*.db "$EXTERNAL_BACKUP_DIR/" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Backups synced to external drive!"
    echo ""
    echo "📋 External backups:"
    ls -lht "$EXTERNAL_BACKUP_DIR"/metadata_backup_*.db | head -5
    
    # Clean up old external backups (keep last 10)
    ls -t "$EXTERNAL_BACKUP_DIR"/metadata_backup_*.db 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null
else
    echo "❌ Sync failed!"
    exit 1
fi


