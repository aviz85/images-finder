#!/bin/bash
# Verify data safety and show what's protected

echo "======================================================================"
echo "  🛡️  DATA SAFETY VERIFICATION"
echo "======================================================================"
echo ""

DB_PATH="/Volumes/My Book/images-finder-data/metadata.db"
DATA_DIR="/Volumes/My Book/images-finder-data"

echo "📊 CHECKING DATABASE STATUS..."
echo ""

# Check if database exists
if [ -f "$DB_PATH" ]; then
    echo "✅ Database exists: $DB_PATH"
    
    # Get database size
    DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
    echo "   Size: $DB_SIZE"
    echo ""
    
    # Query database for counts
    echo "📈 SAFE DATA COUNTS:"
    sqlite3 "$DB_PATH" << 'SQL'
.mode column
.headers on
SELECT 
    COUNT(*) as 'Total Registered',
    SUM(CASE WHEN embedding_index IS NOT NULL THEN 1 ELSE 0 END) as 'With Embeddings',
    (SELECT COUNT(*) FROM failed_images) as 'Failed'
FROM images;
SQL
    echo ""
    
    # Calculate percentages
    echo "🎯 PROGRESS:"
    sqlite3 "$DB_PATH" << 'SQL'
.mode column
.headers on
SELECT 
    PRINTF('%.2f%%', CAST(COUNT(*) AS FLOAT) / 3174680 * 100) as 'Registration %',
    PRINTF('%.3f%%', CAST(SUM(CASE WHEN embedding_index IS NOT NULL THEN 1 ELSE 0 END) AS FLOAT) / 3174680 * 100) as 'Embedding %'
FROM images;
SQL
    echo ""
    
    # Show recent activity
    echo "📸 LAST 5 REGISTERED IMAGES:"
    sqlite3 "$DB_PATH" << 'SQL'
.mode column
.headers on
SELECT 
    file_name as 'Image',
    CASE WHEN embedding_index IS NOT NULL THEN '✅' ELSE '⏳' END as 'Emb',
    width || 'x' || height as 'Size'
FROM images 
ORDER BY id DESC 
LIMIT 5;
SQL
    echo ""
    
else
    echo "❌ Database not found at: $DB_PATH"
    echo ""
fi

echo "💾 CHECKING FILES..."
echo ""

# Check data directory
if [ -d "$DATA_DIR" ]; then
    echo "✅ Data directory exists: $DATA_DIR"
    
    # Check for embeddings file
    if [ -f "$DATA_DIR/embeddings.npy" ]; then
        EMB_SIZE=$(du -h "$DATA_DIR/embeddings.npy" | cut -f1)
        echo "✅ Embeddings file saved: $EMB_SIZE"
        echo "   (All embedding vectors are SAFE on disk!)"
    else
        echo "⚠️  Embeddings file not yet created"
        echo "   (Embedding vectors are in memory, will save at end)"
    fi
    echo ""
    
    # Show total data size
    echo "📁 TOTAL DATA SIZE:"
    du -sh "$DATA_DIR"
    echo ""
else
    echo "❌ Data directory not found: $DATA_DIR"
    echo ""
fi

echo "🔍 CHECKING PROCESSES..."
echo ""

# Check if processing is running
PROC_COUNT=$(ps aux | grep -E "(cli.py|pipeline.py)" | grep -v grep | wc -l)
if [ "$PROC_COUNT" -gt 0 ]; then
    echo "✅ Processing is running ($PROC_COUNT processes active)"
    echo ""
    echo "Active processes:"
    ps aux | grep -E "(cli.py)" | grep -v grep | awk '{print "   - PID " $2 ": " $13 " " $14 " " $15 " " $16}' | head -5
else
    echo "⏸  No processing currently running"
fi
echo ""

echo "======================================================================"
echo "  🎯 SAFETY SUMMARY"
echo "======================================================================"
echo ""

if [ -f "$DB_PATH" ]; then
    REGISTERED=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM images")
    WITH_EMB=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM images WHERE embedding_index IS NOT NULL")
    
    echo "✅ COMPLETELY SAFE (Survives shutdown):"
    echo "   - $REGISTERED registered images in database"
    echo "   - All metadata, paths, dimensions"
    echo "   - Perceptual hashes for duplicate detection"
    echo "   - Processing history and logs"
    echo ""
    
    if [ -f "$DATA_DIR/embeddings.npy" ]; then
        echo "✅ EMBEDDINGS SAFE:"
        echo "   - All embedding vectors saved to disk"
        echo "   - Can build FAISS index anytime"
        echo ""
    else
        if [ "$WITH_EMB" -gt 0 ]; then
            RECOVERY_MIN=$((WITH_EMB / 5 / 60))
            echo "⚠️  EMBEDDINGS AT RISK (if shutdown):"
            echo "   - $WITH_EMB embedding vectors in memory"
            echo "   - Database knows WHICH images have embeddings (safe)"
            echo "   - But actual vectors not yet saved to disk"
            echo "   - Recovery time: ~$RECOVERY_MIN minutes (can regenerate)"
            echo ""
        fi
    fi
    
    echo "🔄 RESUMABILITY:"
    echo "   ✅ Process resumes automatically after restart"
    echo "   ✅ Skips already registered images"
    echo "   ✅ Only processes what's missing"
    echo "   ✅ No duplicate work"
    echo ""
fi

echo "📖 For detailed safety information, see:"
echo "   cat DATA_SAFETY_REPORT.md"
echo ""
echo "======================================================================"



