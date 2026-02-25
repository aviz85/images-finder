#!/usr/bin/env python3
"""
Find near-duplicate images in gallery using CLIP embeddings.
Computes embeddings on-the-fly and finds similar pairs.
"""

import sys
import os
import sqlite3
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict
import argparse

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Suppress warnings
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
import warnings
warnings.filterwarnings('ignore')

import torch
from PIL import Image
from tqdm import tqdm

# Gallery paths
GALLERY_DIR = Path(__file__).parent
DB_PATH = GALLERY_DIR / "gallery.db"
EMBEDDINGS_CACHE = GALLERY_DIR / "gallery_embeddings.npy"
IDS_CACHE = GALLERY_DIR / "gallery_ids.npy"


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


def compute_embeddings(images: List[Tuple[int, str]], model, preprocess, batch_size: int = 32) -> Tuple[np.ndarray, np.ndarray]:
    """Compute CLIP embeddings for images."""
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
                except Exception as e:
                    continue

            if batch_images:
                batch_tensor = torch.stack(batch_images)
                features = model.encode_image(batch_tensor)
                features = features / features.norm(dim=-1, keepdim=True)
                embeddings.append(features.numpy())
                ids.extend(batch_ids)

    if embeddings:
        return np.vstack(embeddings), np.array(ids)
    return np.array([]), np.array([])


def find_similar_pairs(embeddings: np.ndarray, ids: np.ndarray, threshold: float = 0.95) -> List[Tuple[int, int, float]]:
    """Find pairs of images with similarity above threshold."""
    print(f"Finding similar pairs (threshold={threshold})...")

    # Compute cosine similarity matrix
    # For large sets, do this in chunks
    n = len(embeddings)
    pairs = []

    chunk_size = 1000
    for i in tqdm(range(0, n, chunk_size)):
        end_i = min(i + chunk_size, n)
        chunk = embeddings[i:end_i]

        # Similarity with all vectors after this chunk
        for j in range(i, n, chunk_size):
            end_j = min(j + chunk_size, n)
            other_chunk = embeddings[j:end_j]

            sim = np.dot(chunk, other_chunk.T)

            # Find pairs above threshold
            indices = np.where(sim >= threshold)
            for ci, cj in zip(indices[0], indices[1]):
                global_i = i + ci
                global_j = j + cj

                # Avoid self-pairs and duplicates
                if global_i < global_j:
                    pairs.append((int(ids[global_i]), int(ids[global_j]), float(sim[ci, cj])))

    # Sort by similarity descending
    pairs.sort(key=lambda x: x[2], reverse=True)
    return pairs


def get_thumbnail_path(image_id: int) -> str:
    """Get thumbnail path for an image."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.execute("SELECT thumbnail_path FROM gallery_images WHERE id = ?", (image_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def show_sample_pairs(pairs: List[Tuple[int, int, float]], num_samples: int = 5):
    """Print sample pairs for review."""
    print(f"\n{'='*60}")
    print(f"Found {len(pairs)} similar pairs")
    print(f"Showing {min(num_samples, len(pairs))} samples:")
    print(f"{'='*60}\n")

    conn = sqlite3.connect(str(DB_PATH))

    for i, (id1, id2, sim) in enumerate(pairs[:num_samples]):
        cursor = conn.execute(
            "SELECT id, original_path, thumbnail_path FROM gallery_images WHERE id IN (?, ?)",
            (id1, id2)
        )
        rows = {r[0]: (r[1], r[2]) for r in cursor.fetchall()}

        print(f"Pair {i+1}: Similarity = {sim:.4f}")
        print(f"  Image A (ID {id1}):")
        print(f"    {rows.get(id1, ('?', '?'))[0]}")
        print(f"  Image B (ID {id2}):")
        print(f"    {rows.get(id2, ('?', '?'))[0]}")
        print()

    conn.close()


def main():
    parser = argparse.ArgumentParser(description='Find duplicate images in gallery')
    parser.add_argument('--threshold', type=float, default=0.95, help='Similarity threshold (0-1)')
    parser.add_argument('--samples', type=int, default=10, help='Number of sample pairs to show')
    parser.add_argument('--limit', type=int, default=None, help='Limit images to process')
    parser.add_argument('--recompute', action='store_true', help='Recompute embeddings even if cached')
    args = parser.parse_args()

    # Load or compute embeddings
    if EMBEDDINGS_CACHE.exists() and IDS_CACHE.exists() and not args.recompute:
        print("Loading cached embeddings...")
        embeddings = np.load(str(EMBEDDINGS_CACHE))
        ids = np.load(str(IDS_CACHE))
        print(f"Loaded {len(ids)} embeddings")
    else:
        print("Loading CLIP model...")
        model, preprocess = load_clip_model()

        images = get_gallery_images(limit=args.limit)
        print(f"Found {len(images)} images with thumbnails")

        embeddings, ids = compute_embeddings(images, model, preprocess)

        # Cache embeddings
        if len(embeddings) > 0:
            np.save(str(EMBEDDINGS_CACHE), embeddings)
            np.save(str(IDS_CACHE), ids)
            print(f"Cached {len(ids)} embeddings")

    if len(embeddings) == 0:
        print("No embeddings to compare!")
        return

    # Find similar pairs
    pairs = find_similar_pairs(embeddings, ids, threshold=args.threshold)

    # Show samples
    show_sample_pairs(pairs, num_samples=args.samples)

    print(f"\nTotal similar pairs found: {len(pairs)}")
    print(f"Run with --threshold=X to adjust sensitivity (current: {args.threshold})")


if __name__ == "__main__":
    main()
