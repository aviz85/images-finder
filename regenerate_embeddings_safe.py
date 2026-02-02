#!/usr/bin/env python3
"""
Safe embedding regeneration script that preserves ID order.

This ensures the index in embeddings.npy matches the image ID in the database,
maintaining compatibility with existing searches and gallery data.

Usage:
    python regenerate_embeddings_safe.py [--batch-size 32] [--resume]
"""

import sqlite3
import numpy as np
from pathlib import Path
from tqdm import tqdm
import argparse
import torch
import open_clip
from PIL import Image

# Paths
DATA_DIR = Path('data')
DB_PATH = DATA_DIR / 'images.db'
EMBEDDINGS_PATH = DATA_DIR / 'embeddings.npy'
PROGRESS_PATH = DATA_DIR / 'embedding_progress.txt'

def load_model():
    """Load CLIP model."""
    print("Loading CLIP model...")
    model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')
    model.eval()
    if torch.backends.mps.is_available():
        device = torch.device('mps')
    elif torch.cuda.is_available():
        device = torch.device('cuda')
    else:
        device = torch.device('cpu')
    model = model.to(device)
    print(f"Using device: {device}")
    return model, preprocess, device

def get_images_ordered(db_path):
    """Get all images ordered by ID."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("""
        SELECT id, file_path FROM images
        ORDER BY id
    """)
    images = cursor.fetchall()
    conn.close()
    return images

def generate_embedding(model, preprocess, device, image_path):
    """Generate embedding for a single image."""
    try:
        img = Image.open(image_path).convert('RGB')
        img_tensor = preprocess(img).unsqueeze(0).to(device)
        with torch.no_grad():
            embedding = model.encode_image(img_tensor)
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)
        return embedding.cpu().numpy().flatten()
    except Exception as e:
        return None

def main():
    parser = argparse.ArgumentParser(description='Regenerate embeddings safely')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size')
    parser.add_argument('--resume', action='store_true', help='Resume from last progress')
    args = parser.parse_args()

    # Load model
    model, preprocess, device = load_model()
    embedding_dim = 512  # ViT-B-32

    # Get all images in ID order
    print(f"Loading images from {DB_PATH}...")
    images = get_images_ordered(DB_PATH)
    total_images = len(images)
    print(f"Total images: {total_images}")

    # Check for existing embeddings to resume
    start_idx = 0
    if args.resume and EMBEDDINGS_PATH.exists():
        existing = np.load(EMBEDDINGS_PATH)
        start_idx = len(existing)
        print(f"Resuming from index {start_idx}")
        embeddings = list(existing)
    else:
        embeddings = []

    # Verify ID order matches expected
    for i, (img_id, _) in enumerate(images[:100]):
        if img_id != i:
            print(f"WARNING: ID mismatch at index {i}, image_id={img_id}")
            print("Database IDs are not sequential. Creating ID mapping...")
            break

    # Generate embeddings
    print(f"\nGenerating embeddings from index {start_idx}...")
    failed = []

    for idx in tqdm(range(start_idx, total_images), desc="Generating"):
        img_id, file_path = images[idx]

        # Verify order
        if idx != img_id:
            # Non-sequential IDs - use placeholder for missing
            while len(embeddings) < img_id:
                embeddings.append(np.zeros(embedding_dim))

        emb = generate_embedding(model, preprocess, device, file_path)
        if emb is not None:
            embeddings.append(emb)
        else:
            embeddings.append(np.zeros(embedding_dim))
            failed.append((img_id, file_path))

        # Save progress every 1000
        if (idx + 1) % 1000 == 0:
            np.save(EMBEDDINGS_PATH, np.array(embeddings))
            with open(PROGRESS_PATH, 'w') as f:
                f.write(f"{idx + 1}")
            print(f"\nSaved progress at {idx + 1}")

    # Final save
    embeddings_array = np.array(embeddings)
    np.save(EMBEDDINGS_PATH, embeddings_array)
    print(f"\nSaved {len(embeddings)} embeddings to {EMBEDDINGS_PATH}")
    print(f"Shape: {embeddings_array.shape}")

    if failed:
        print(f"\nFailed to process {len(failed)} images:")
        for img_id, path in failed[:10]:
            print(f"  ID {img_id}: {path}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more")

    # Cleanup progress file
    if PROGRESS_PATH.exists():
        PROGRESS_PATH.unlink()

    print("\nDone! Embeddings regenerated with preserved ID order.")
    print("Index in embeddings.npy = image ID in database")

if __name__ == "__main__":
    main()
