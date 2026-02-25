#!/bin/bash
# Full pipeline: Embed → Classify → Collages → WAME

cd /Users/aviz/images-finder
source venv/bin/activate

echo "=============================================="
echo "Gallery Re-embedding & Classification Pipeline"
echo "Started: $(date)"
echo "=============================================="

# Step 1: Generate embeddings
echo ""
echo "📊 STEP 1: Generating embeddings..."
python gallery/reindex/embed_gallery.py
if [ $? -ne 0 ]; then
    echo "❌ Embedding failed!"
    exit 1
fi

# Step 2: Classify from embeddings
echo ""
echo "📊 STEP 2: Classifying from embeddings..."
python gallery/reindex/classify_from_embeddings.py
if [ $? -ne 0 ]; then
    echo "❌ Classification failed!"
    exit 1
fi

# Step 3: Create sample collages
echo ""
echo "📊 STEP 3: Creating sample collages..."
python gallery/reindex/create_sample_collages.py

# Step 4: Get stats and send WAME
echo ""
echo "📊 STEP 4: Sending results via WhatsApp..."

# Get stats
STATS=$(python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('gallery/reindex/classification.db')
total = conn.execute("SELECT COUNT(*) FROM image_classification").fetchone()[0]
keep = conn.execute("SELECT COUNT(*) FROM image_classification WHERE classification='KEEP'").fetchone()[0]
remove = conn.execute("SELECT COUNT(*) FROM image_classification WHERE classification='REMOVE'").fetchone()[0]
high_keep = conn.execute("SELECT COUNT(*) FROM image_classification WHERE classification='KEEP' AND confidence > 0.03").fetchone()[0]
high_remove = conn.execute("SELECT COUNT(*) FROM image_classification WHERE classification='REMOVE' AND confidence > 0.03").fetchone()[0]
conn.close()
print(f"Total: {total}")
print(f"KEEP: {keep} ({keep*100/total:.1f}%)")
print(f"REMOVE: {remove} ({remove*100/total:.1f}%)")
print(f"High-conf KEEP: {high_keep}")
print(f"High-conf REMOVE: {high_remove}")
EOF
)

# Send summary message
cd ~/.claude/skills/whatsapp/scripts
npx ts-node send-message.ts "✅ Gallery Re-embedding & Classification Complete!

$STATS

Sending 10 sample collages..." --to 972503973736

# Send all 10 collages
COLLAGE_DIR="/Users/aviz/images-finder/gallery/reindex/collages"

for i in 1 2 3 4 5; do
    npx ts-node send-message.ts --to 972503973736 \
        --image "$COLLAGE_DIR/collage_top_$i.jpg" \
        --caption "🏘️ Top confidence ($i/5)"
done

for i in 1 2 3 4 5; do
    npx ts-node send-message.ts --to 972503973736 \
        --image "$COLLAGE_DIR/collage_random_$i.jpg" \
        --caption "🎲 Random sample ($i/5)"
done

npx ts-node send-message.ts "✅ All 10 collages sent! Review and let me know if classification looks good." --to 972503973736

echo ""
echo "=============================================="
echo "Pipeline complete: $(date)"
echo "=============================================="
