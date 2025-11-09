#!/bin/bash
# Setup script for Local Semantic Image Search

set -e

echo "Setting up Local Semantic Image Search..."

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create data directory
echo "Creating data directory..."
mkdir -p data/thumbnails

# Copy example config if config doesn't exist
if [ ! -f "config.yaml" ]; then
    echo "Creating default config.yaml..."
    cp config.example.yaml config.yaml
fi

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit config.yaml if needed (optional)"
echo "2. Index your images: python cli.py run-pipeline /path/to/images"
echo "3. Search: python cli.py search-text 'your query'"
echo ""
echo "For HTTP API, run: python server.py"
echo ""
