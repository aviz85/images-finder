#!/bin/bash
#
# Simple search test script - searches and opens images with ~70% match
#

set -e

BASE_DIR="/Users/aviz/images-finder"
VENV_PYTHON="$BASE_DIR/venv/bin/python"

cd "$BASE_DIR"

# Activate venv
source "$BASE_DIR/venv/bin/activate" 2>/dev/null || true

echo "============================================================"
echo "  🔍 בדיקת חיפוש - תמונות עם ~70% התאמה"
echo "============================================================"
echo ""

# Test queries
queries=("sky" "ocean" "mountain" "people" "cat")

for query in "${queries[@]}"; do
    echo "============================================================"
    echo "חיפוש: '$query'"
    echo "============================================================"
    echo ""
    
    # Search using CLI
    "$VENV_PYTHON" cli.py search-text "$query" --top-k 50 --json-output > /tmp/search_results_${query}.json 2>&1
    
    if [ $? -eq 0 ]; then
        # Parse results and filter ~70% matches
        "$VENV_PYTHON" << PYTHON
import json
from pathlib import Path
import subprocess

# Load results
with open('/tmp/search_results_${query}.json', 'r') as f:
    results = json.load(f)

# Filter results in 65-75% range
target_results = [r for r in results if 0.65 <= r['score'] <= 0.75]

print(f"נמצאו {len(results)} תוצאות")
print(f"בטווח 65-75%: {len(target_results)} תמונות")
print()

if target_results:
    print("פותח את 5 הראשונות בטווח 70%:")
    print()
    
    for i, result in enumerate(target_results[:5], 1):
        score = result['score'] * 100
        file_path = result['file_path']
        file_name = Path(file_path).name
        
        print(f"{i}. {file_name}")
        print(f"   התאמה: {score:.1f}%")
        print(f"   {file_path}")
        
        # Open image
        if Path(file_path).exists():
            subprocess.run(['open', file_path])
            print(f"   ✅ נפתח")
        else:
            print(f"   ⚠️  קובץ לא נמצא")
        print()
else:
    # Find closest to 70%
    closest = sorted(results, key=lambda x: abs(x['score'] - 0.7))[:5]
    print("לא נמצאו בטווח, הקרובות ביותר ל-70%:")
    print()
    
    for i, result in enumerate(closest, 1):
        score = result['score'] * 100
        diff = abs(result['score'] - 0.7) * 100
        file_path = result['file_path']
        file_name = Path(file_path).name
        
        print(f"{i}. {file_name}")
        print(f"   התאמה: {score:.1f}% (הפרש: {diff:.1f}%)")
        print(f"   {file_path}")
        
        if Path(file_path).exists():
            subprocess.run(['open', file_path])
            print(f"   ✅ נפתח")
        print()

PYTHON
        
        echo ""
        read -p "לחץ Enter להמשך לשאילתה הבאה..." || true
        echo ""
    else
        echo "❌ שגיאה בחיפוש '$query'"
        echo ""
    fi
done

echo "✅ סיום בדיקה"

