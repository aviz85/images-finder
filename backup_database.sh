#!/bin/bash
set -e

# Database Backup Script for Images Finder
# Creates timestamped backups of the SQLite database

PROJECT_ROOT="/Users/aviz/images-finder"
DB_PATH="/Volumes/My Book/images-finder-data/metadata.db"
BACKUP_DIR="/Volumes/My Book/images-finder-data/backups"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Generate timestamp for backup filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/metadata_backup_$TIMESTAMP.db"

echo "======================================================================"
echo "  📦 Database Backup"
echo "======================================================================"
echo ""
echo "Source:  $DB_PATH"
echo "Backup:  $BACKUP_FILE"
echo ""

# Use SQLite's backup command for safe backup (works even while workers are running)
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

if [ $? -eq 0 ]; then
    # Get backup size
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    
    echo "✅ Backup completed successfully!"
    echo "   Size: $BACKUP_SIZE"
    echo ""
    
    # Show all backups
    echo "📚 Available backups:"
    ls -lh "$BACKUP_DIR" | grep ".db$" | awk '{print "   " $9 " (" $5 ")"}'
    echo ""
    
    # Count total backups
    BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/*.db 2>/dev/null | wc -l)
    echo "   Total backups: $BACKUP_COUNT"
    
    # Optional: Keep only last 10 backups (uncomment to enable)
    # cd "$BACKUP_DIR" && ls -t metadata_backup_*.db | tail -n +11 | xargs -I {} rm -- {}
    # echo "   (Keeping only the 10 most recent backups)"
    
else
    echo "❌ Backup failed!"
    exit 1
fi

echo ""
echo "======================================================================"



