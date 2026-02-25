#!/usr/bin/env python3
"""
Simple UI for semantic image search with on-demand thumbnail generation.
Thumbnails are stored on the external drive and cached for future use.
"""

from flask import Flask, render_template, request, jsonify, send_file
from pathlib import Path
import sqlite3
import hashlib
import logging
from PIL import Image
import os
import threading
from typing import Optional, List, Dict

from src.config import load_config
from src.search import ImageSearchEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global search engine
search_engine: Optional[ImageSearchEngine] = None
config = None

# Thumbnail generation lock
thumbnail_lock = threading.Lock()

# Thumbnail directory on external drive
EXTERNAL_DRIVE_BASE = Path("/Volumes/My Book")
THUMBNAILS_DIR = EXTERNAL_DRIVE_BASE / ".thumbnails"
THUMBNAIL_SIZE = (384, 384)


def init_search_engine():
    """Initialize the search engine."""
    global search_engine, config
    
    logger.info("Initializing search engine...")
    config = load_config(Path('config_optimized.yaml'))
    search_engine = ImageSearchEngine(config)
    search_engine.initialize()
    logger.info("Search engine ready!")
    
    # Create thumbnails directory on external drive
    THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Thumbnails directory: {THUMBNAILS_DIR}")


def get_thumbnail_path(file_path: str) -> Path:
    """Get thumbnail path for an image file."""
    # Create hash from file path
    path_hash = hashlib.md5(file_path.encode()).hexdigest()
    thumbnail_name = f"{path_hash}.jpg"
    return THUMBNAILS_DIR / thumbnail_name


def generate_thumbnail(file_path: str) -> Optional[Path]:
    """
    Generate thumbnail for an image file.
    Saves to external drive thumbnails directory.
    """
    thumbnail_path = get_thumbnail_path(file_path)
    
    # Check if already exists
    if thumbnail_path.exists():
        return thumbnail_path
    
    # Use lock to prevent concurrent generation
    with thumbnail_lock:
        # Double-check after acquiring lock
        if thumbnail_path.exists():
            return thumbnail_path
        
        try:
            source_path = Path(file_path)
            if not source_path.exists():
                logger.warning(f"Source image not found: {file_path}")
                return None
            
            # Open and process image
            with Image.open(source_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Create thumbnail (aspect-preserving)
                img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                
                # Save thumbnail
                img.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
                logger.info(f"Generated thumbnail: {thumbnail_path}")
                return thumbnail_path
                
        except Exception as e:
            logger.error(f"Failed to generate thumbnail for {file_path}: {e}")
            return None


def generate_thumbnails_batch(file_paths: List[str]) -> Dict[str, str]:
    """
    Generate thumbnails for multiple images in batch.
    Returns dict mapping file_path -> thumbnail_path (or None if failed).
    """
    results = {}
    for file_path in file_paths:
        thumbnail_path = generate_thumbnail(file_path)
        if thumbnail_path:
            results[file_path] = str(thumbnail_path)
        else:
            results[file_path] = None
    return results


@app.route('/')
def index():
    """Serve the main search UI."""
    return render_template('search_ui.html')


@app.route('/api/search', methods=['POST'])
def search():
    """Search for images by text query."""
    global search_engine
    
    if search_engine is None:
        return jsonify({'error': 'Search engine not initialized'}), 500
    
    data = request.get_json()
    query = data.get('query', '').strip()
    top_k = data.get('top_k', 20)
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    try:
        logger.info(f"Searching for: '{query}' (top_k={top_k})")
        results = search_engine.search_by_text(query, top_k=top_k)
        
        # Convert results to dict format
        results_data = []
        for result in results:
            result_dict = result.to_dict()
            
            # Check if thumbnail exists
            thumbnail_path = get_thumbnail_path(result.file_path)
            if thumbnail_path.exists():
                result_dict['thumbnail_url'] = f'/api/thumbnail/{hashlib.md5(result.file_path.encode()).hexdigest()}'
            else:
                result_dict['thumbnail_url'] = None  # Will be generated on-demand
            
            results_data.append(result_dict)
        
        return jsonify({
            'query': query,
            'num_results': len(results_data),
            'results': results_data
        })
        
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/thumbnail/<thumbnail_hash>')
def get_thumbnail(thumbnail_hash: str):
    """Get thumbnail image by hash."""
    # Find thumbnail file
    thumbnail_path = THUMBNAILS_DIR / f"{thumbnail_hash}.jpg"
    
    if thumbnail_path.exists():
        return send_file(str(thumbnail_path), mimetype='image/jpeg')
    else:
        return jsonify({'error': 'Thumbnail not found'}), 404


@app.route('/api/generate-thumbnails', methods=['POST'])
def generate_thumbnails():
    """Generate thumbnails for a list of image paths."""
    data = request.get_json()
    file_paths = data.get('file_paths', [])
    
    if not file_paths:
        return jsonify({'error': 'file_paths is required'}), 400
    
    try:
        # Generate thumbnails in background thread
        def generate_in_background():
            logger.info(f"Generating {len(file_paths)} thumbnails in background...")
            generate_thumbnails_batch(file_paths)
            logger.info("Thumbnail generation complete")
        
        thread = threading.Thread(target=generate_in_background)
        thread.daemon = True
        thread.start()
        
        # Return immediately with paths that will be available
        results = {}
        for file_path in file_paths:
            thumbnail_path = get_thumbnail_path(file_path)
            file_path_hash = hashlib.md5(file_path.encode()).hexdigest()
            if thumbnail_path.exists():
                results[file_path] = f'/api/thumbnail/{file_path_hash}'
            else:
                results[file_path] = None  # Will be generated
        
        return jsonify({
            'status': 'generating',
            'thumbnails': results
        })
        
    except Exception as e:
        logger.error(f"Thumbnail generation error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/check-thumbnail/<file_path_hash>')
def check_thumbnail(file_path_hash: str):
    """Check if thumbnail exists for a file path hash."""
    thumbnail_path = THUMBNAILS_DIR / f"{file_path_hash}.jpg"
    
    if thumbnail_path.exists():
        return jsonify({
            'exists': True,
            'url': f'/api/thumbnail/{file_path_hash}'
        })
    else:
        return jsonify({'exists': False})


@app.route('/api/get-thumbnail-hash', methods=['POST'])
def get_thumbnail_hash():
    """Get thumbnail hash for a file path."""
    data = request.get_json()
    file_path = data.get('file_path', '')
    
    if not file_path:
        return jsonify({'error': 'file_path is required'}), 400
    
    file_path_hash = hashlib.md5(file_path.encode()).hexdigest()
    return jsonify({'hash': file_path_hash})


if __name__ == '__main__':
    # Initialize search engine
    init_search_engine()
    
    # Run Flask app on port 8889 (different from dashboard port 8888)
    port = 8889
    logger.info(f"Starting Flask server on http://localhost:{port}")
    app.run(host='127.0.0.1', port=port, debug=False, threaded=True)

