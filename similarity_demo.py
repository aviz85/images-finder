#!/usr/bin/env python3
"""
Minimal similarity search demo with visual proof.
Shows a query image and its most similar images side-by-side.
"""

from flask import Flask, render_template_string, request, send_file
import sqlite3
from pathlib import Path
import random
from PIL import Image
import io
import numpy as np
from src.config import load_config
from src.embeddings import EmbeddingModel

app = Flask(__name__)

# Load config
config = load_config(Path('config_optimized.yaml'))
DB_PATH = str(config.db_path)

# Initialize model globally
print("Loading embedding model...")
model = EmbeddingModel(
    model_name=config.model_name,
    pretrained=config.pretrained,
    device=config.device
)
print("Model loaded!")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>🔍 Similarity Search Proof</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            text-align: center;
        }
        h1 {
            color: #667eea;
            font-size: 2.5rem;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #666;
            font-size: 1.2rem;
        }
        .controls {
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            display: flex;
            gap: 20px;
            align-items: center;
            justify-content: center;
        }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 40px;
            border-radius: 8px;
            font-size: 1.1rem;
            cursor: pointer;
            font-weight: 600;
            transition: transform 0.2s;
            text-decoration: none;
            display: inline-block;
        }
        .btn:hover {
            transform: translateY(-2px);
        }
        .query-section {
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        .section-title {
            font-size: 1.5rem;
            color: #333;
            margin-bottom: 20px;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }
        .query-image-container {
            text-align: center;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .query-image {
            max-width: 100%;
            max-height: 400px;
            border-radius: 8px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            margin-bottom: 15px;
        }
        .query-info {
            color: #666;
            font-size: 0.9rem;
            margin-top: 10px;
        }
        .results-section {
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        .results-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .result-card {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            transition: transform 0.2s;
            border: 2px solid transparent;
        }
        .result-card:hover {
            transform: translateY(-5px);
            border-color: #667eea;
        }
        .result-image {
            width: 100%;
            height: 200px;
            object-fit: cover;
            border-radius: 6px;
            margin-bottom: 10px;
        }
        .rank {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9rem;
            margin-bottom: 8px;
        }
        .similarity-score {
            font-size: 1.2rem;
            font-weight: bold;
            color: #10b981;
            margin: 8px 0;
        }
        .filename {
            font-size: 0.8rem;
            color: #666;
            word-break: break-all;
            margin-top: 5px;
        }
        .loading {
            text-align: center;
            padding: 60px;
            font-size: 1.5rem;
            color: #666;
        }
        .stats {
            background: #f0f4ff;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 15px;
        }
        .stat-item {
            text-align: center;
        }
        .stat-label {
            font-size: 0.9rem;
            color: #666;
            margin-bottom: 5px;
        }
        .stat-value {
            font-size: 1.5rem;
            font-weight: bold;
            color: #667eea;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Similarity Search Visual Proof</h1>
            <p class="subtitle">See how semantic search finds similar images</p>
        </div>

        <div class="controls">
            <a href="/" class="btn">🎲 Random Image</a>
            <a href="/random-with-search" class="btn">🔍 Random + Search</a>
        </div>

        {% if query_image %}
        <div class="query-section">
            <h2 class="section-title">🎯 Query Image</h2>
            <div class="query-image-container">
                <img src="/image/{{ query_image.id }}" class="query-image" alt="Query">
                <div class="query-info">
                    <strong>ID:</strong> {{ query_image.id }} | 
                    <strong>Size:</strong> {{ query_image.width }}×{{ query_image.height }} | 
                    <strong>File:</strong> {{ query_image.file_name }}
                </div>
            </div>
        </div>

        {% if results %}
        <div class="results-section">
            <h2 class="section-title">✨ Top {{ results|length }} Most Similar Images</h2>
            
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-label">Images Searched</div>
                    <div class="stat-value">{{ total_searched }}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Avg Similarity</div>
                    <div class="stat-value">{{ "%.1f"|format(avg_similarity * 100) }}%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Best Match</div>
                    <div class="stat-value">{{ "%.1f"|format(results[0].similarity * 100) }}%</div>
                </div>
            </div>

            <div class="results-grid">
                {% for result in results %}
                <div class="result-card">
                    <span class="rank">#{{ loop.index }}</span>
                    <img src="/image/{{ result.id }}" class="result-image" alt="Result {{ loop.index }}">
                    <div class="similarity-score">{{ "%.1f"|format(result.similarity * 100) }}% match</div>
                    <div class="filename">{{ result.file_name }}</div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% else %}
        <div class="results-section">
            <div class="loading">Click "Random + Search" to see similar images!</div>
        </div>
        {% endif %}

        {% else %}
        <div class="query-section">
            <div class="loading">Click "Random Image" or "Random + Search" to start!</div>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""


def get_random_image_with_embedding():
    """Get a random image that has an embedding."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM images 
        WHERE embedding_index IS NOT NULL 
        ORDER BY RANDOM() 
        LIMIT 1
    """)
    
    image = cur.fetchone()
    conn.close()
    return dict(image) if image else None


def get_sample_images_with_embeddings(limit=200):
    """Get sample images for similarity comparison."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM images 
        WHERE embedding_index IS NOT NULL 
        ORDER BY RANDOM() 
        LIMIT ?
    """, (limit,))
    
    images = [dict(row) for row in cur.fetchall()]
    conn.close()
    return images


def compute_similarity(query_image_path, candidate_images, top_k=10):
    """Compute similarity between query image and candidates."""
    # Load and encode query image
    query_img = Image.open(query_image_path).convert('RGB')
    query_embedding = model.encode_images([query_img])[0]
    
    # Encode candidate images
    results = []
    for img_info in candidate_images:
        try:
            img_path = Path(img_info['file_path'])
            if not img_path.exists():
                continue
                
            img = Image.open(img_path).convert('RGB')
            img_embedding = model.encode_images([img])[0]
            
            # Compute cosine similarity
            similarity = np.dot(query_embedding, img_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(img_embedding)
            )
            
            results.append({
                'id': img_info['id'],
                'file_name': img_info['file_name'],
                'file_path': img_info['file_path'],
                'width': img_info['width'],
                'height': img_info['height'],
                'similarity': float(similarity)
            })
        except Exception as e:
            print(f"Error processing {img_info['file_path']}: {e}")
            continue
    
    # Sort by similarity (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:top_k]


@app.route('/')
def index():
    """Show a random image."""
    query_image = get_random_image_with_embedding()
    return render_template_string(HTML_TEMPLATE, query_image=query_image, results=None)


@app.route('/random-with-search')
def random_with_search():
    """Show a random image and find similar ones."""
    # Get random query image
    query_image = get_random_image_with_embedding()
    if not query_image:
        return "No images with embeddings found!", 404
    
    # Get sample images to search through
    print(f"Loading sample images for comparison...")
    candidate_images = get_sample_images_with_embeddings(limit=200)
    print(f"Loaded {len(candidate_images)} candidates")
    
    # Compute similarities
    print(f"Computing similarities for query image: {query_image['file_name']}")
    results = compute_similarity(query_image['file_path'], candidate_images, top_k=10)
    
    # Calculate stats
    total_searched = len(candidate_images)
    avg_similarity = sum(r['similarity'] for r in results) / len(results) if results else 0
    
    print(f"Found {len(results)} similar images")
    
    return render_template_string(
        HTML_TEMPLATE,
        query_image=query_image,
        results=results,
        total_searched=total_searched,
        avg_similarity=avg_similarity
    )


@app.route('/image/<int:image_id>')
def serve_image(image_id):
    """Serve an image by ID."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("SELECT file_path FROM images WHERE id = ?", (image_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return "Image not found", 404
    
    file_path = Path(row['file_path'])
    if not file_path.exists():
        return "Image file not found", 404
    
    # Resize image for faster loading
    try:
        img = Image.open(file_path)
        img.thumbnail((800, 800), Image.Resampling.LANCZOS)
        
        img_io = io.BytesIO()
        img.save(img_io, 'JPEG', quality=85)
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/jpeg')
    except Exception as e:
        return f"Error loading image: {e}", 500


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("  🔍 Similarity Search Visual Demo")
    print("=" * 60)
    print("\n✓ Starting server on http://localhost:5555")
    print("\n💡 This will:")
    print("   1. Pick a random image from your collection")
    print("   2. Search through 200 random images")
    print("   3. Show you the 10 most similar ones")
    print("   4. Display similarity scores (higher = more similar)")
    print("\n🎯 This PROVES the similarity search works!\n")
    print("=" * 60 + "\n")
    
    app.run(host='0.0.0.0', port=5555, debug=False)

