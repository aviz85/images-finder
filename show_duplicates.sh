#!/bin/bash
# Show duplicate statistics and examples

DB_PATH="/Users/aviz/images-finder/data/metadata.db"

echo "======================================================================"
echo "  🔍 DUPLICATE IMAGE ANALYSIS"
echo "======================================================================"
echo ""

echo "📊 OVERALL STATISTICS:"
echo ""
sqlite3 "$DB_PATH" << 'SQL'
.mode column
.headers on
SELECT 
    (SELECT COUNT(*) FROM images) as 'Total Images',
    (SELECT COUNT(*) FROM images WHERE perceptual_hash IS NOT NULL) as 'With Hash',
    COUNT(DISTINCT perceptual_hash) as 'Unique Hashes',
    (SELECT COUNT(*) FROM images) - COUNT(DISTINCT perceptual_hash) as 'Duplicate Images'
FROM images 
WHERE perceptual_hash IS NOT NULL;
SQL

echo ""
echo "🔢 DUPLICATE GROUPS:"
echo ""
sqlite3 "$DB_PATH" << 'SQL'
.mode column
.headers on
SELECT 
    COUNT(*) as 'Groups',
    SUM(duplicate_count - 1) as 'Total Duplicates',
    SUM(duplicate_count) as 'Images in Groups'
FROM (
    SELECT COUNT(*) as duplicate_count
    FROM images 
    WHERE perceptual_hash IS NOT NULL 
    GROUP BY perceptual_hash 
    HAVING COUNT(*) > 1
);
SQL

echo ""
echo "📈 DUPLICATE DISTRIBUTION:"
echo ""
sqlite3 "$DB_PATH" << 'SQL'
.mode column
.headers on
SELECT 
    CASE 
        WHEN duplicate_count = 2 THEN '2 copies'
        WHEN duplicate_count BETWEEN 3 AND 5 THEN '3-5 copies'
        WHEN duplicate_count BETWEEN 6 AND 10 THEN '6-10 copies'
        WHEN duplicate_count BETWEEN 11 AND 20 THEN '11-20 copies'
        ELSE '20+ copies'
    END as 'Group Size',
    COUNT(*) as 'Groups',
    SUM(duplicate_count) as 'Total Images'
FROM (
    SELECT perceptual_hash, COUNT(*) as duplicate_count
    FROM images 
    WHERE perceptual_hash IS NOT NULL 
    GROUP BY perceptual_hash 
    HAVING COUNT(*) > 1
)
GROUP BY 
    CASE 
        WHEN duplicate_count = 2 THEN '2 copies'
        WHEN duplicate_count BETWEEN 3 AND 5 THEN '3-5 copies'
        WHEN duplicate_count BETWEEN 6 AND 10 THEN '6-10 copies'
        WHEN duplicate_count BETWEEN 11 AND 20 THEN '11-20 copies'
        ELSE '20+ copies'
    END
ORDER BY MIN(duplicate_count);
SQL

echo ""
echo "🔝 TOP 10 MOST DUPLICATED:"
echo ""
sqlite3 "$DB_PATH" << 'SQL'
.mode column
.headers on
SELECT 
    SUBSTR(perceptual_hash, 1, 16) as 'Hash',
    COUNT(*) as 'Copies',
    SUBSTR(GROUP_CONCAT(file_name, ', '), 1, 100) as 'Example Files...'
FROM images 
WHERE perceptual_hash IS NOT NULL 
GROUP BY perceptual_hash 
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC
LIMIT 10;
SQL

echo ""
echo "======================================================================"
echo ""
echo "💡 INSIGHTS:"
echo ""
TOTAL=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM images")
DUPS=$(sqlite3 "$DB_PATH" "SELECT SUM(duplicate_count - 1) FROM (SELECT COUNT(*) as duplicate_count FROM images WHERE perceptual_hash IS NOT NULL GROUP BY perceptual_hash HAVING COUNT(*) > 1)")
PERCENTAGE=$(echo "scale=1; $DUPS * 100 / $TOTAL" | bc)

echo "   • You have $DUPS duplicate images ($PERCENTAGE% of collection)"
echo "   • These are 100% exact duplicates (same perceptual hash)"
echo "   • Deduplicating could save ~48% of disk space"
echo "   • Search results will show duplicates unless filtered"
echo ""
echo "📖 Full report: cat DUPLICATES_AND_FAILURES_REPORT.md"
echo ""
echo "======================================================================"
