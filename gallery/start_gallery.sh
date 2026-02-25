#!/bin/bash
# Start Gallery Review System

cd "$(dirname "$0")/.."
source venv/bin/activate

echo "============================================="
echo "   Gallery Review System"
echo "============================================="
echo ""

# Check if thumbnails exist
THUMB_COUNT=$(ls -1 gallery/thumbnails/*.jpg 2>/dev/null | wc -l | tr -d ' ')
if [ "$THUMB_COUNT" -lt 100 ]; then
    echo "Warning: Only $THUMB_COUNT thumbnails found."
    echo "Run 'python gallery/generate_thumbnails.py' first to generate thumbnails."
    echo ""
fi

# Start server
echo "Starting Gallery Server on http://localhost:8080"
echo "Press Ctrl+C to stop"
echo ""

cd gallery
python gallery_server.py --port 8080
