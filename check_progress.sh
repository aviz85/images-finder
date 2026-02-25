#!/bin/bash
#
# Check embedding generation progress and estimate time
#

set -e

BASE_DIR="/Users/aviz/images-finder"
LOG_DIR="$BASE_DIR/logs"

cd "$BASE_DIR"

# Find database
DB_PATH=""
for db in "data/metadata.db" "/Volumes/My Book/images-finder-data/metadata.db"; do
    if [ -f "$db" ]; then
        DB_PATH="$db"
        break
    fi
done

if [ -z "$DB_PATH" ]; then
    echo "❌ Database not found!"
    exit 1
fi

# Get database status
with_emb=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM images WHERE embedding_index IS NOT NULL" 2>/dev/null)
remaining=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM images WHERE embedding_index IS NULL" 2>/dev/null)
total=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM images" 2>/dev/null)

if [ -z "$with_emb" ] || [ -z "$remaining" ] || [ -z "$total" ]; then
    echo "❌ Could not read database!"
    exit 1
fi

percent=$(python3 -c "print('{:.1f}'.format(($with_emb / $total * 100) if $total > 0 else 0))")

echo "============================================================"
echo "  📊 סטטוס התקדמות"
echo "============================================================"
echo ""
echo "✅ עם embeddings: $(printf "%'d" $with_emb)"
echo "⏳ נותרו: $(printf "%'d" $remaining)"
echo "📸 סה\"כ: $(printf "%'d" $total)"
echo "📈 התקדמות: ${percent}%"
echo ""
echo "============================================================"

# Calculate speed from logs
echo ""
echo "  ⚡ מהירות נוכחית"
echo "============================================================"
echo ""

speeds=()
for i in {0..5}; do
    log_file="$LOG_DIR/embed_worker_${i}.log"
    if [ -f "$log_file" ]; then
        # Get last rate from log
        rate=$(tail -100 "$log_file" | grep -o "Rate: [0-9.]* img/s" | tail -1 | grep -o "[0-9.]*" || echo "")
        if [ -n "$rate" ] && [ "$rate" != "0" ]; then
            speeds+=($rate)
            printf "  Worker %d: %.2f img/sec\n" $i $rate
        fi
    fi
done

if [ ${#speeds[@]} -eq 0 ]; then
    echo "  ⚠️  לא נמצאו נתוני מהירות"
    echo "  משתמש בהערכה שמרנית: 1.3 img/sec per worker"
    avg_speed=1.3
    total_speed=7.8
else
    # Calculate average
    sum=0
    for speed in "${speeds[@]}"; do
        sum=$(echo "$sum + $speed" | bc -l 2>/dev/null || echo "$sum")
    done
    avg_speed=$(echo "scale=2; $sum / ${#speeds[@]}" | bc -l 2>/dev/null || echo "1.3")
    total_speed=$(echo "scale=2; $avg_speed * 6" | bc -l 2>/dev/null || echo "7.8")
    
    echo ""
    echo "  ממוצע: ${avg_speed} img/sec per worker"
    echo "  סה\"כ (6 workers): ${total_speed} img/sec"
fi

echo ""
echo "============================================================"
echo "  ⏱️  הערכת זמן"
echo "============================================================"
echo ""

if [ "$remaining" -gt 0 ] && [ -n "$total_speed" ]; then
    # Calculate time
    seconds=$(echo "scale=0; $remaining / $total_speed" | bc -l 2>/dev/null || echo "0")
    
    if [ "$seconds" -gt 0 ]; then
        hours=$(echo "scale=0; $seconds / 3600" | bc -l 2>/dev/null || echo "0")
        days=$(echo "scale=1; $hours / 24" | bc -l 2>/dev/null || echo "0")
        
        days_int=$(echo "scale=0; $days / 1" | bc -l)
        hours_remaining=$(echo "scale=0; $hours % 24" | bc -l)
        
        echo "  תמונות נותרות: $(printf "%'d" $remaining)"
        echo ""
        
        if [ "$days_int" -ge 1 ]; then
            echo "  ⏱️  זמן משוער לסיום: ${days_int} ימים, ${hours_remaining} שעות"
            echo "     (${days} ימים)"
        else
            minutes=$(echo "scale=0; ($seconds % 3600) / 60" | bc -l)
            echo "  ⏱️  זמן משוער לסיום: ${hours} שעות, ${minutes} דקות"
        fi
        
        # Total time estimate
        if [ "$total" -gt 0 ]; then
            total_seconds=$(echo "scale=0; $total / $total_speed" | bc -l)
            total_days=$(echo "scale=1; $total_seconds / 86400" | bc -l)
            total_days_int=$(echo "scale=0; $total_days / 1" | bc -l)
            
            echo ""
            echo "  📈 זמן כולל משוער (סה\"כ ${total} תמונות):"
            if [ "$total_days_int" -ge 1 ]; then
                total_hours=$(echo "scale=0; ($total_seconds % 86400) / 3600" | bc -l)
                echo "     ${total_days_int} ימים, ${total_hours} שעות"
                echo "     (${total_days} ימים)"
            else
                total_hours=$(echo "scale=0; $total_seconds / 3600" | bc -l)
                echo "     ${total_hours} שעות"
            fi
        fi
    fi
fi

echo ""
echo "============================================================"

