#!/bin/bash
# Check SHA-256 duplicate statistics

DB_PATH="/Volumes/My Book/images-finder-data/metadata.db"

echo "======================================================================"
echo "  📊 SHA-256 Duplicate Detection Report"
echo "======================================================================"
echo ""

# Check if hash computation is running
if ps aux | grep -q "[c]ompute_hashes"; then
    echo "⏳ Hash computation is RUNNING..."
    echo ""
fi

# Get current progress
echo "📈 PROGRESS:"
echo ""
sqlite3 "$DB_PATH" << 'SQL'
.mode column
.headers on
SELECT 
    COUNT(*) as 'Total Images',
    SUM(CASE WHEN sha256_hash IS NOT NULL THEN 1 ELSE 0 END) as 'With SHA-256',
    PRINTF('%.1f%%', 
        CAST(SUM(CASE WHEN sha256_hash IS NOT NULL THEN 1 ELSE 0 END) AS FLOAT) / 
        COUNT(*) * 100
    ) as 'Progress'
FROM images;
SQL

echo ""
echo "🔍 SHA-256 DUPLICATES (from processed images):"
echo ""

# Count duplicates
sqlite3 "$DB_PATH" << 'SQL'
.mode column
.headers on
SELECT 
    COUNT(DISTINCT sha256_hash) as 'Unique Hashes',
    COUNT(*) as 'Total Processed',
    COUNT(*) - COUNT(DISTINCT sha256_hash) as 'Duplicates Found'
FROM images 
WHERE sha256_hash IS NOT NULL;
SQL

echo ""
echo "🔝 TOP 10 SHA-256 DUPLICATE GROUPS:"
echo ""

sqlite3 "$DB_PATH" << 'SQL'
.mode column
.headers on
SELECT 
    SUBSTR(sha256_hash, 1, 12) || '...' as 'Hash',
    COUNT(*) as 'Copies',
    SUBSTR(GROUP_CONCAT(file_name, ', '), 1, 60) || '...' as 'Example Files'
FROM images 
WHERE sha256_hash IS NOT NULL
GROUP BY sha256_hash 
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC
LIMIT 10;
SQL

echo ""
echo "======================================================================"
echo ""
echo "💡 NOTES:"
echo "   • SHA-256 finds EXACT byte-for-byte copies"
echo "   • Different from perceptual hash (visual duplicates)"
echo "   • Both types of duplicates are tracked separately"
echo ""
echo "⏰ Estimated time to complete: ~2-3 hours for all 194K images"
echo ""
echo "🔄 Run this script again to see updated progress:"
echo "   ./check_sha256_duplicates.sh"
echo ""
echo "======================================================================"



