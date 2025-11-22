#!/bin/bash
# Open a specific duplicate group in Preview to visually inspect

DB_PATH="/Volumes/My Book/images-finder-data/metadata.db"

if [ -z "$1" ]; then
    echo "Usage: $0 <group_number>"
    echo ""
    echo "Example: $0 1     (opens the largest duplicate group)"
    echo "         $0 5     (opens the 5th largest duplicate group)"
    echo ""
    echo "Available groups: 1-100"
    echo ""
    echo "Top 10 groups:"
    sqlite3 "$DB_PATH" << 'SQL'
.mode column
.headers on
SELECT 
    ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) as 'Group#',
    COUNT(*) as 'Copies',
    SUBSTR(perceptual_hash, 1, 16) as 'Hash',
    SUBSTR(GROUP_CONCAT(file_name, ', '), 1, 60) || '...' as 'Example Files'
FROM images 
WHERE perceptual_hash IS NOT NULL 
GROUP BY perceptual_hash 
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC
LIMIT 10;
SQL
    exit 1
fi

GROUP_NUM=$1

echo "======================================================================"
echo "  🔍 OPENING DUPLICATE GROUP #$GROUP_NUM"
echo "======================================================================"
echo ""

# Get the Nth duplicate group hash
HASH=$(sqlite3 "$DB_PATH" "
SELECT perceptual_hash 
FROM images 
WHERE perceptual_hash IS NOT NULL 
GROUP BY perceptual_hash 
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC
LIMIT 1 OFFSET $((GROUP_NUM - 1))
")

if [ -z "$HASH" ]; then
    echo "❌ Group #$GROUP_NUM not found"
    exit 1
fi

# Get all images in this group
echo "Hash: $HASH"
echo ""

# Count images
COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM images WHERE perceptual_hash = '$HASH'")
echo "Found $COUNT duplicate images"
echo ""

# Get image paths (limit to first 10 to avoid overwhelming Preview)
LIMIT=10
if [ $COUNT -gt $LIMIT ]; then
    echo "Opening first $LIMIT images (out of $COUNT total)..."
else
    echo "Opening all $COUNT images..."
fi
echo ""

# Create temporary file list
TEMP_LIST=$(mktemp)

sqlite3 "$DB_PATH" "
SELECT file_path 
FROM images 
WHERE perceptual_hash = '$HASH'
ORDER BY file_path
LIMIT $LIMIT
" > "$TEMP_LIST"

# Show the files we're opening
echo "Files:"
cat "$TEMP_LIST" | nl
echo ""

# Open in Preview
echo "Opening in Preview..."
cat "$TEMP_LIST" | while read -r filepath; do
    if [ -f "$filepath" ]; then
        open -a Preview "$filepath" 2>/dev/null
    else
        echo "⚠️  File not found: $filepath"
    fi
done

rm "$TEMP_LIST"

echo ""
echo "✅ Done! Check Preview app to see the images side by side"
echo ""
echo "💡 TIP: In Preview, use View > Thumbnails to see all images at once"
echo ""
echo "======================================================================"



