#!/usr/bin/env python3
"""
Generate HTML viewer for reviewing duplicate pairs.
"""

import sys
import os
import sqlite3
import numpy as np
from pathlib import Path
import json
import webbrowser
import argparse
from typing import List, Tuple

GALLERY_DIR = Path(__file__).parent
DB_PATH = GALLERY_DIR / "gallery.db"
THUMBNAILS_DIR = GALLERY_DIR / "thumbnails"
EMBEDDINGS_CACHE = GALLERY_DIR / "gallery_embeddings.npy"
IDS_CACHE = GALLERY_DIR / "gallery_ids.npy"
OUTPUT_HTML = GALLERY_DIR / "duplicate_review.html"

# Suppress warnings
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
import warnings
warnings.filterwarnings('ignore')


def load_clip_model():
    """Load CLIP model."""
    import open_clip
    model, _, preprocess = open_clip.create_model_and_transforms(
        'ViT-B-32', pretrained='openai'
    )
    model.eval()
    return model, preprocess


def get_gallery_images(limit: int = None) -> List[Tuple[int, str]]:
    """Get gallery images with thumbnails."""
    conn = sqlite3.connect(str(DB_PATH))
    query = """
        SELECT id, original_path FROM gallery_images
        WHERE thumbnail_path IS NOT NULL
        ORDER BY id
    """
    if limit:
        query += f" LIMIT {limit}"
    cursor = conn.execute(query)
    results = cursor.fetchall()
    conn.close()
    return results


def compute_embeddings(images, model, preprocess, batch_size=32):
    """Compute CLIP embeddings."""
    import torch
    from PIL import Image
    from tqdm import tqdm

    embeddings = []
    ids = []

    print(f"Computing embeddings for {len(images)} images...")

    with torch.no_grad():
        for i in tqdm(range(0, len(images), batch_size)):
            batch = images[i:i+batch_size]
            batch_images = []
            batch_ids = []

            for img_id, path in batch:
                try:
                    img = Image.open(path).convert('RGB')
                    img_tensor = preprocess(img)
                    batch_images.append(img_tensor)
                    batch_ids.append(img_id)
                except:
                    continue

            if batch_images:
                batch_tensor = torch.stack(batch_images)
                features = model.encode_image(batch_tensor)
                features = features / features.norm(dim=-1, keepdim=True)
                embeddings.append(features.numpy())
                ids.extend(batch_ids)

    return np.vstack(embeddings), np.array(ids)


def find_similar_pairs(embeddings, ids, threshold=0.92):
    """Find similar pairs."""
    from tqdm import tqdm

    print(f"Finding similar pairs (threshold={threshold})...")
    n = len(embeddings)
    pairs = []

    chunk_size = 1000
    for i in tqdm(range(0, n, chunk_size)):
        end_i = min(i + chunk_size, n)
        chunk = embeddings[i:end_i]

        for j in range(i, n, chunk_size):
            end_j = min(j + chunk_size, n)
            other_chunk = embeddings[j:end_j]
            sim = np.dot(chunk, other_chunk.T)
            indices = np.where(sim >= threshold)

            for ci, cj in zip(indices[0], indices[1]):
                global_i = i + ci
                global_j = j + cj
                if global_i < global_j:
                    pairs.append((int(ids[global_i]), int(ids[global_j]), float(sim[ci, cj])))

    pairs.sort(key=lambda x: x[2], reverse=True)
    return pairs


def get_image_info(image_id: int) -> dict:
    """Get full image info."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.execute(
        "SELECT id, original_path, thumbnail_path, semantic_score FROM gallery_images WHERE id = ?",
        (image_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0],
            'original_path': row[1],
            'thumbnail_path': row[2],
            'semantic_score': row[3],
            'filename': Path(row[1]).name
        }
    return None


def generate_html(pairs: List[Tuple[int, int, float]], max_pairs: int = 100):
    """Generate HTML review page."""
    pair_data = []

    for id1, id2, sim in pairs[:max_pairs]:
        img1 = get_image_info(id1)
        img2 = get_image_info(id2)
        if img1 and img2:
            pair_data.append({
                'similarity': round(sim, 4),
                'image1': img1,
                'image2': img2
            })

    html = f'''<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>Duplicate Review - {len(pair_data)} pairs</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #1a1a2e;
            color: #eee;
            margin: 0;
            padding: 20px;
        }}
        h1 {{ text-align: center; color: #00d4ff; }}
        .stats {{
            text-align: center;
            margin: 20px 0;
            padding: 15px;
            background: #16213e;
            border-radius: 10px;
        }}
        .pair {{
            display: flex;
            gap: 20px;
            margin: 30px auto;
            max-width: 1400px;
            background: #16213e;
            padding: 20px;
            border-radius: 15px;
            align-items: flex-start;
        }}
        .pair.hidden {{ display: none; }}
        .pair.marked-duplicate {{ border: 3px solid #ff6b6b; opacity: 0.6; }}
        .pair.marked-keep {{ border: 3px solid #51cf66; }}
        .image-box {{
            flex: 1;
            text-align: center;
        }}
        .image-box img {{
            max-width: 100%;
            max-height: 400px;
            border-radius: 10px;
            cursor: pointer;
            transition: transform 0.2s;
        }}
        .image-box img:hover {{ transform: scale(1.02); }}
        .info {{
            margin-top: 10px;
            font-size: 12px;
            color: #888;
            word-break: break-all;
        }}
        .similarity {{
            background: #0f3460;
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 18px;
            font-weight: bold;
            white-space: nowrap;
        }}
        .similarity.exact {{ background: #ff4757; }}
        .similarity.high {{ background: #ffa502; }}
        .controls {{
            display: flex;
            flex-direction: column;
            gap: 10px;
            justify-content: center;
            min-width: 150px;
        }}
        button {{
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }}
        .btn-duplicate {{ background: #ff6b6b; color: white; }}
        .btn-duplicate:hover {{ background: #ee5a5a; }}
        .btn-keep {{ background: #51cf66; color: white; }}
        .btn-keep:hover {{ background: #40c057; }}
        .btn-skip {{ background: #495057; color: white; }}
        .btn-skip:hover {{ background: #343a40; }}
        .summary {{
            position: fixed;
            bottom: 20px;
            left: 20px;
            background: #16213e;
            padding: 15px 25px;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }}
        .export-btn {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #00d4ff;
            color: #000;
            padding: 15px 30px;
            border-radius: 10px;
            font-weight: bold;
        }}
        .threshold-control {{
            text-align: center;
            margin: 20px 0;
        }}
        .threshold-control input {{
            width: 200px;
        }}
    </style>
</head>
<body>
    <h1>🔍 Duplicate Image Review</h1>

    <div class="stats">
        <strong>{len(pair_data)}</strong> similar pairs found
        | Threshold: <span id="threshold-display">0.92</span>
    </div>

    <div class="threshold-control">
        <label>Filter by similarity: </label>
        <input type="range" id="threshold-slider" min="0.9" max="1.0" step="0.01" value="0.92">
        <span id="slider-value">0.92</span>
    </div>

    <div id="pairs-container">
'''

    for i, pair in enumerate(pair_data):
        sim_class = 'exact' if pair['similarity'] >= 0.99 else ('high' if pair['similarity'] >= 0.95 else '')
        html += f'''
        <div class="pair" data-similarity="{pair['similarity']}" data-pair-id="{i}">
            <div class="image-box">
                <img src="thumbnails/{Path(pair['image1']['thumbnail_path']).name}"
                     onclick="window.open('{pair['image1']['original_path']}', '_blank')"
                     title="Click to open original">
                <div class="info">
                    ID: {pair['image1']['id']}<br>
                    {pair['image1']['filename']}
                </div>
            </div>

            <div class="controls">
                <div class="similarity {sim_class}">{pair['similarity']}</div>
                <button class="btn-duplicate" onclick="markDuplicate({i}, {pair['image2']['id']})">
                    🗑️ Hide Right
                </button>
                <button class="btn-duplicate" onclick="markDuplicate({i}, {pair['image1']['id']})">
                    🗑️ Hide Left
                </button>
                <button class="btn-keep" onclick="markKeep({i})">
                    ✓ Keep Both
                </button>
                <button class="btn-skip" onclick="skipPair({i})">
                    Skip
                </button>
            </div>

            <div class="image-box">
                <img src="thumbnails/{Path(pair['image2']['thumbnail_path']).name}"
                     onclick="window.open('{pair['image2']['original_path']}', '_blank')"
                     title="Click to open original">
                <div class="info">
                    ID: {pair['image2']['id']}<br>
                    {pair['image2']['filename']}
                </div>
            </div>
        </div>
'''

    html += '''
    </div>

    <div class="summary">
        Reviewed: <span id="reviewed-count">0</span> |
        Duplicates: <span id="duplicate-count">0</span> |
        Keep: <span id="keep-count">0</span>
    </div>

    <button class="export-btn" onclick="exportResults()">
        📥 Export Results
    </button>

    <script>
        const duplicates = new Set();
        const keeps = new Set();
        let reviewed = 0;

        function updateCounts() {
            document.getElementById('reviewed-count').textContent = reviewed;
            document.getElementById('duplicate-count').textContent = duplicates.size;
            document.getElementById('keep-count').textContent = keeps.size;
        }

        function markDuplicate(pairId, imageId) {
            const pair = document.querySelector(`[data-pair-id="${pairId}"]`);
            pair.classList.add('marked-duplicate');
            pair.classList.remove('marked-keep');
            duplicates.add(imageId);
            reviewed++;
            updateCounts();
        }

        function markKeep(pairId) {
            const pair = document.querySelector(`[data-pair-id="${pairId}"]`);
            pair.classList.add('marked-keep');
            pair.classList.remove('marked-duplicate');
            keeps.add(pairId);
            reviewed++;
            updateCounts();
        }

        function skipPair(pairId) {
            const pair = document.querySelector(`[data-pair-id="${pairId}"]`);
            pair.classList.add('hidden');
            reviewed++;
            updateCounts();
        }

        function exportResults() {
            const result = {
                duplicates_to_hide: Array.from(duplicates),
                timestamp: new Date().toISOString()
            };
            const blob = new Blob([JSON.stringify(result, null, 2)], {type: 'application/json'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'duplicates_to_hide.json';
            a.click();
        }

        // Threshold slider
        document.getElementById('threshold-slider').addEventListener('input', function(e) {
            const threshold = parseFloat(e.target.value);
            document.getElementById('slider-value').textContent = threshold.toFixed(2);
            document.querySelectorAll('.pair').forEach(pair => {
                const sim = parseFloat(pair.dataset.similarity);
                if (sim >= threshold) {
                    pair.style.display = 'flex';
                } else {
                    pair.style.display = 'none';
                }
            });
        });
    </script>
</body>
</html>
'''

    with open(OUTPUT_HTML, 'w') as f:
        f.write(html)

    print(f"Generated: {OUTPUT_HTML}")
    return str(OUTPUT_HTML)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--threshold', type=float, default=0.92)
    parser.add_argument('--max-pairs', type=int, default=200)
    parser.add_argument('--limit', type=int, default=None, help='Limit images to process')
    parser.add_argument('--recompute', action='store_true')
    parser.add_argument('--open', action='store_true', help='Open in browser')
    args = parser.parse_args()

    # Load or compute embeddings
    if EMBEDDINGS_CACHE.exists() and IDS_CACHE.exists() and not args.recompute:
        print("Loading cached embeddings...")
        embeddings = np.load(str(EMBEDDINGS_CACHE))
        ids = np.load(str(IDS_CACHE))
    else:
        print("Loading CLIP model...")
        model, preprocess = load_clip_model()
        images = get_gallery_images(limit=args.limit)
        embeddings, ids = compute_embeddings(images, model, preprocess)
        np.save(str(EMBEDDINGS_CACHE), embeddings)
        np.save(str(IDS_CACHE), ids)

    # Find pairs
    pairs = find_similar_pairs(embeddings, ids, threshold=args.threshold)
    print(f"Found {len(pairs)} similar pairs")

    # Generate HTML
    html_path = generate_html(pairs, max_pairs=args.max_pairs)

    if args.open:
        webbrowser.open(f'file://{html_path}')


if __name__ == "__main__":
    main()
