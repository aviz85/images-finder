#!/usr/bin/env python3
"""
Auto-hide duplicate images in gallery based on CLIP embedding similarity.
Keeps the image with lower ID visible, hides the one with higher ID.
"""

import sys
import os
import sqlite3
import numpy as np
from pathlib import Path
from typing import List, Tuple
from datetime import datetime

GALLERY_DIR = Path(__file__).parent
DB_PATH = GALLERY_DIR / "gallery.db"
EMBEDDINGS_CACHE = GALLERY_DIR / "gallery_embeddings_full.npy"
IDS_CACHE = GALLERY_DIR / "gallery_ids_full.npy"
LOG_FILE = GALLERY_DIR / "duplicate_processing.log"

os.environ['TOKENIZERS_PARALLELISM'] = 'false'
import warnings
warnings.filterwarnings('ignore')


def log(msg):
    """Log to file and stdout."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, 'a') as f:
        f.write(line + "\n")


def load_clip_model():
    """Load CLIP model."""
    import open_clip
    model, _, preprocess = open_clip.create_model_and_transforms(
        'ViT-B-32', pretrained='openai'
    )
    model.eval()
    return model, preprocess


def get_gallery_images() -> List[Tuple[int, str]]:
    """Get all gallery images with thumbnails."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.execute("""
        SELECT id, original_path FROM gallery_images
        WHERE thumbnail_path IS NOT NULL
        ORDER BY id
    """)
    results = cursor.fetchall()
    conn.close()
    return results


def compute_embeddings(images, model, preprocess, batch_size=32):
    """Compute CLIP embeddings with progress logging."""
    import torch
    from PIL import Image
    from tqdm import tqdm

    embeddings = []
    ids = []
    failed = 0

    log(f"Computing embeddings for {len(images)} images...")

    with torch.no_grad():
        for i in tqdm(range(0, len(images), batch_size), desc="Embedding"):
            batch = images[i:i+batch_size]
            batch_images = []
            batch_ids = []

            for img_id, path in batch:
                try:
                    img = Image.open(path).convert('RGB')
                    img_tensor = preprocess(img)
                    batch_images.append(img_tensor)
                    batch_ids.append(img_id)
                except Exception as e:
                    failed += 1
                    continue

            if batch_images:
                batch_tensor = torch.stack(batch_images)
                features = model.encode_image(batch_tensor)
                features = features / features.norm(dim=-1, keepdim=True)
                embeddings.append(features.numpy())
                ids.extend(batch_ids)

            # Progress checkpoint every 1000 images
            if (i + batch_size) % 1000 == 0:
                log(f"Progress: {i + batch_size}/{len(images)} images processed")

    log(f"Embedding complete. Success: {len(ids)}, Failed: {failed}")
    return np.vstack(embeddings), np.array(ids)


def find_similar_pairs(embeddings, ids, threshold=0.92):
    """Find all similar pairs above threshold."""
    from tqdm import tqdm

    log(f"Finding similar pairs (threshold={threshold})...")
    n = len(embeddings)
    pairs = []

    chunk_size = 1000
    for i in tqdm(range(0, n, chunk_size), desc="Similarity"):
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
    log(f"Found {len(pairs)} similar pairs")
    return pairs


def hide_duplicates(pairs: List[Tuple[int, int, float]]):
    """Mark duplicates as hidden in DB. Keep lower ID, hide higher ID."""
    log(f"Marking {len(pairs)} duplicates as hidden...")

    conn = sqlite3.connect(str(DB_PATH))

    # Track which IDs to hide (higher ID in each pair)
    to_hide = {}
    for id1, id2, sim in pairs:
        keep_id = min(id1, id2)
        hide_id = max(id1, id2)
        # Only update if not already marked as duplicate of something else
        if hide_id not in to_hide:
            to_hide[hide_id] = (keep_id, sim)

    log(f"Unique images to hide: {len(to_hide)}")

    # Update in batches
    batch_size = 100
    hidden_ids = list(to_hide.keys())

    for i in range(0, len(hidden_ids), batch_size):
        batch = hidden_ids[i:i+batch_size]
        for hide_id in batch:
            keep_id, sim = to_hide[hide_id]
            conn.execute("""
                UPDATE gallery_images
                SET is_hidden = 1, duplicate_of = ?
                WHERE id = ? AND is_hidden = 0
            """, (keep_id, hide_id))
        conn.commit()

    conn.close()
    log(f"Done! Hidden {len(to_hide)} duplicate images")


def get_stats():
    """Get current stats."""
    conn = sqlite3.connect(str(DB_PATH))
    total = conn.execute("SELECT COUNT(*) FROM gallery_images WHERE thumbnail_path IS NOT NULL").fetchone()[0]
    hidden = conn.execute("SELECT COUNT(*) FROM gallery_images WHERE is_hidden = 1").fetchone()[0]
    visible = total - hidden
    conn.close()
    return total, hidden, visible


def main():
    log("=" * 60)
    log("Starting duplicate detection process")
    log("=" * 60)

    threshold = 0.92

    # Load or compute embeddings
    if EMBEDDINGS_CACHE.exists() and IDS_CACHE.exists():
        log("Loading cached embeddings...")
        embeddings = np.load(str(EMBEDDINGS_CACHE))
        ids = np.load(str(IDS_CACHE))
        log(f"Loaded {len(ids)} cached embeddings")
    else:
        log("Loading CLIP model...")
        model, preprocess = load_clip_model()

        images = get_gallery_images()
        log(f"Found {len(images)} images with thumbnails")

        embeddings, ids = compute_embeddings(images, model, preprocess)

        # Save cache
        np.save(str(EMBEDDINGS_CACHE), embeddings)
        np.save(str(IDS_CACHE), ids)
        log(f"Cached embeddings to {EMBEDDINGS_CACHE}")

    # Find similar pairs
    pairs = find_similar_pairs(embeddings, ids, threshold=threshold)

    # Hide duplicates
    if pairs:
        hide_duplicates(pairs)

    # Final stats
    total, hidden, visible = get_stats()
    log("=" * 60)
    log(f"FINAL STATS:")
    log(f"  Total images with thumbnails: {total}")
    log(f"  Hidden as duplicates: {hidden}")
    log(f"  Visible (unique): {visible}")
    log(f"  Reduction: {hidden/total*100:.1f}%")
    log("=" * 60)


if __name__ == "__main__":
    main()
