#!/bin/bash
# Start the simple search UI

cd /Users/aviz/images-finder

echo "======================================================================"
echo "  🚀 Starting Semantic Search UI"
echo "======================================================================"
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import flask" 2>/dev/null; then
    echo "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies"
        exit 1
    fi
fi

# Check if external drive is mounted
if [ ! -d "/Volumes/My Book" ]; then
    echo "⚠️  WARNING: External drive 'My Book' not mounted!"
    echo "   Thumbnails will be stored locally instead."
    THUMBNAILS_DIR="/Users/aviz/images-finder/data/.thumbnails"
    mkdir -p "$THUMBNAILS_DIR"
else
    # Create thumbnails directory on external drive
    mkdir -p "/Volumes/My Book/.thumbnails" 2>/dev/null || {
        echo "⚠️  Could not create thumbnails directory on external drive."
        echo "   Using local directory instead."
        mkdir -p "/Users/aviz/images-finder/data/.thumbnails"
    }
fi

echo ""
echo "Starting server..."
echo "UI will be available at: http://localhost:8889"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python simple_search_ui.py

