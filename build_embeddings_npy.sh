#!/bin/bash
#
# Build embeddings.npy file from database
# This regenerates embeddings for all images that have embedding_index
#

set -e

BASE_DIR="/Users/aviz/images-finder"
VENV_PYTHON="$BASE_DIR/venv/bin/python"

cd "$BASE_DIR"

# Check if venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

echo "============================================================"
echo "  🔨 בניית embeddings.npy מחדש"
echo "============================================================"
echo ""

# Check current status
python3 << 'PYTHON'
import sqlite3
from pathlib import Path
import numpy as np

db_path = Path("data/metadata.db")
if db_path.exists():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM images WHERE embedding_index IS NOT NULL")
    count = cursor.fetchone()[0]
    
    cursor.execute("SELECT MAX(embedding_index) FROM images WHERE embedding_index IS NOT NULL")
    max_idx = cursor.fetchone()[0]
    
    conn.close()
    
    embeddings_path = Path("data/embeddings.npy")
    if embeddings_path.exists():
        embeddings = np.load(embeddings_path)
        existing = len(embeddings)
    else:
        existing = 0
    
    print(f"📊 מצב נוכחי:")
    print(f"   תמונות עם embedding_index: {count:,}")
    print(f"   Max embedding_index: {max_idx:,}")
    print(f"   Embeddings ב-npy: {existing:,}")
    print(f"   חסרים: {max_idx + 1 - existing:,}")
    print()
PYTHON

echo "============================================================"
echo "  ⚠️  הערה חשובה:"
echo "============================================================"
echo ""
echo "זה ייקח זמן רב! (~2-3 ימים עבור 900K תמונות)"
echo ""
echo "אפשרויות:"
echo ""
echo "1. בדיקה מהירה (100 תמונות):"
echo "   source venv/bin/activate"
echo "   python regenerate_embeddings_by_index.py --max-images 100"
echo ""
echo "2. יצירה מלאה:"
echo "   source venv/bin/activate"
echo "   python regenerate_embeddings_by_index.py"
echo ""
echo "3. המשך מנקודה מסוימת:"
echo "   python regenerate_embeddings_by_index.py --start-from 1000"
echo ""
echo "============================================================"
echo ""
read -p "להתחיל יצירה מלאה עכשיו? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 מתחיל יצירת embeddings.npy..."
    echo ""
    
    source "$BASE_DIR/venv/bin/activate"
    python regenerate_embeddings_by_index.py
    
    echo ""
    echo "✅ סיום!"
else
    echo ""
    echo "לא התחלנו. אתה יכול להריץ ידנית:"
    echo "  source venv/bin/activate"
    echo "  python regenerate_embeddings_by_index.py"
fi

