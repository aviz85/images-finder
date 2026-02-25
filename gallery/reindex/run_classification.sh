#!/bin/bash
# Run classification with caffeinate and hourly updates

cd /Users/aviz/images-finder
source venv/bin/activate

echo "Starting classification at $(date)"

# Run classification
python gallery/reindex/classify_images.py 2>&1 | tee gallery/reindex/classification.log

echo "Classification complete at $(date)"

# Final stats
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('gallery/reindex/classification.db')
total = conn.execute("SELECT COUNT(*) FROM image_classification").fetchone()[0]
keep = conn.execute("SELECT COUNT(*) FROM image_classification WHERE classification='KEEP'").fetchone()[0]
remove = conn.execute("SELECT COUNT(*) FROM image_classification WHERE classification='REMOVE'").fetchone()[0]
print(f"DONE: {total} classified - {keep} KEEP, {remove} REMOVE")
EOF
