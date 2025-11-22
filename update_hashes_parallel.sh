#!/bin/bash
# Run hash computation in parallel for existing images

echo "======================================================================"
echo "  🔄 Updating SHA-256 & Perceptual Hashes"
echo "======================================================================"
echo ""

# First, apply database migration
echo "1. Applying database migration..."
python3 << 'EOF'
from pathlib import Path
from src.database import ImageDatabase

db_path = Path("/Volumes/My Book/images-finder-data/metadata.db")
db = ImageDatabase(db_path)
print("✓ Database schema updated (added sha256_hash column and index)")
EOF

echo ""
echo "2. Computing hashes for all images..."
echo "   (This will update perceptual hash to phash and add SHA-256)"
echo ""

# Run hash computation
cd /Users/aviz/images-finder
python3 compute_hashes_parallel.py config_optimized.yaml

echo ""
echo "======================================================================"
echo "✓ Hash update complete!"
echo ""
echo "📊 Check duplicate statistics:"
echo "   ./show_duplicates.sh"
echo ""
echo "🔄 Restart processing:"
echo "   ./run_parallel_optimized.sh"
echo ""
echo "======================================================================"



