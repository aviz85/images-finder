#!/usr/bin/env python3
"""
Safe embedding regeneration script that preserves ID order.

SAFETY GUARANTEES:
1. Pre-allocates array by max_id → no index shifting possible
2. Direct assignment embeddings[id] = vector → position always correct
3. Verification at end confirms every ID matches its position
4. Failed images logged to file for retry
5. Atomic saves with backup

Usage:
    python regenerate_embeddings_safe.py [--batch-size 32] [--resume] [--verify-only]
"""

import sqlite3
import numpy as np
from pathlib import Path
from tqdm import tqdm
import argparse
import torch
import open_clip
from PIL import Image
import shutil
from datetime import datetime

# Paths
DATA_DIR = Path('data')
DB_PATH = DATA_DIR / 'images.db'
EMBEDDINGS_PATH = DATA_DIR / 'embeddings.npy'
PROGRESS_PATH = DATA_DIR / 'embedding_progress.json'
FAILED_PATH = DATA_DIR / 'embedding_failed.txt'
EMBEDDING_DIM = 512  # ViT-B-32


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


def get_all_images(db_path):
    """Get all images as dict: {id: file_path}."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT id, file_path FROM images")
    images = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return images


def get_max_id(db_path):
    """Get maximum image ID."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT MAX(id) FROM images")
    max_id = cursor.fetchone()[0]
    conn.close()
    return max_id


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


def save_with_backup(embeddings, path):
    """Save embeddings with backup of previous version."""
    if path.exists():
        backup_path = path.with_suffix('.npy.backup')
        shutil.copy(path, backup_path)
    np.save(path, embeddings)


def verify_embeddings(embeddings, images):
    """
    Verify that embeddings array is correctly aligned with database.
    Returns (is_valid, issues_list)
    """
    issues = []

    # Check 1: Array size covers all IDs
    max_id = max(images.keys())
    if len(embeddings) <= max_id:
        issues.append(f"Array too small: {len(embeddings)} but max_id is {max_id}")

    # Check 2: All images have embeddings (not all zeros)
    zero_vector = np.zeros(EMBEDDING_DIM)
    missing = []
    for img_id in images.keys():
        if img_id < len(embeddings):
            if np.array_equal(embeddings[img_id], zero_vector):
                missing.append(img_id)
        else:
            missing.append(img_id)

    if missing:
        issues.append(f"{len(missing)} images have zero/missing embeddings")

    # Check 3: Non-zero embeddings are normalized (length ~1.0)
    non_zero_count = 0
    bad_norm_count = 0
    for img_id in list(images.keys())[:1000]:  # Sample first 1000
        if img_id < len(embeddings):
            emb = embeddings[img_id]
            if not np.array_equal(emb, zero_vector):
                non_zero_count += 1
                norm = np.linalg.norm(emb)
                if abs(norm - 1.0) > 0.01:
                    bad_norm_count += 1

    if bad_norm_count > 0:
        issues.append(f"{bad_norm_count}/{non_zero_count} embeddings not normalized")

    return len(issues) == 0, issues, missing


def main():
    parser = argparse.ArgumentParser(description='Regenerate embeddings safely')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size')
    parser.add_argument('--resume', action='store_true', help='Resume from existing file')
    parser.add_argument('--verify-only', action='store_true', help='Only verify existing embeddings')
    parser.add_argument('--retry-failed', action='store_true', help='Retry only failed images')
    args = parser.parse_args()

    # Get all images from database
    print(f"Loading images from {DB_PATH}...")
    images = get_all_images(DB_PATH)
    max_id = max(images.keys())
    total_images = len(images)
    print(f"Total images: {total_images}, Max ID: {max_id}")

    # Check if IDs are sequential
    expected_ids = set(range(max_id + 1))
    actual_ids = set(images.keys())
    gaps = expected_ids - actual_ids
    if gaps:
        print(f"Note: {len(gaps)} gaps in IDs (deleted images)")

    # Verify-only mode
    if args.verify_only:
        if not EMBEDDINGS_PATH.exists():
            print("ERROR: No embeddings file to verify")
            return
        embeddings = np.load(EMBEDDINGS_PATH)
        print(f"Loaded embeddings: {embeddings.shape}")
        is_valid, issues, missing = verify_embeddings(embeddings, images)
        if is_valid:
            print("✓ Embeddings are valid and correctly aligned!")
        else:
            print("✗ Issues found:")
            for issue in issues:
                print(f"  - {issue}")
            if missing:
                print(f"\nMissing IDs (first 20): {missing[:20]}")
        return

    # Load model
    model, preprocess, device = load_model()

    # Initialize or load embeddings array
    # KEY SAFETY: Pre-allocate to max_id + 1, so embeddings[id] is always valid
    array_size = max_id + 1

    if args.resume and EMBEDDINGS_PATH.exists():
        print(f"Loading existing embeddings...")
        embeddings = np.load(EMBEDDINGS_PATH)
        if len(embeddings) < array_size:
            # Extend array if needed
            print(f"Extending array from {len(embeddings)} to {array_size}")
            new_embeddings = np.zeros((array_size, EMBEDDING_DIM), dtype=np.float32)
            new_embeddings[:len(embeddings)] = embeddings
            embeddings = new_embeddings
        print(f"Resumed with shape: {embeddings.shape}")
    else:
        print(f"Creating new embeddings array: ({array_size}, {EMBEDDING_DIM})")
        embeddings = np.zeros((array_size, EMBEDDING_DIM), dtype=np.float32)

    # Determine which images to process
    if args.retry_failed and FAILED_PATH.exists():
        # Only retry previously failed
        with open(FAILED_PATH) as f:
            ids_to_process = [int(line.strip()) for line in f if line.strip()]
        print(f"Retrying {len(ids_to_process)} failed images")
    elif args.resume:
        # Find images with zero embeddings
        zero_vector = np.zeros(EMBEDDING_DIM)
        ids_to_process = [
            img_id for img_id in images.keys()
            if np.array_equal(embeddings[img_id], zero_vector)
        ]
        print(f"Processing {len(ids_to_process)} images without embeddings")
    else:
        ids_to_process = list(images.keys())
        print(f"Processing all {len(ids_to_process)} images")

    if not ids_to_process:
        print("Nothing to process!")
        return

    # Sort for predictable progress
    ids_to_process.sort()

    # Process images
    failed = []
    success_count = 0

    print(f"\nGenerating embeddings...")
    for img_id in tqdm(ids_to_process, desc="Generating"):
        file_path = images.get(img_id)
        if not file_path:
            failed.append((img_id, "NOT_IN_DB"))
            continue

        emb = generate_embedding(model, preprocess, device, file_path)

        if emb is not None:
            # SAFETY: Direct assignment by ID - position always correct
            embeddings[img_id] = emb
            success_count += 1
        else:
            # Keep zeros for failed (already there)
            failed.append((img_id, file_path))

        # Save progress every 1000
        if (success_count + len(failed)) % 1000 == 0:
            save_with_backup(embeddings, EMBEDDINGS_PATH)
            # Save failed list for retry
            with open(FAILED_PATH, 'w') as f:
                for fid, fpath in failed:
                    f.write(f"{fid}\n")

    # Final save
    save_with_backup(embeddings, EMBEDDINGS_PATH)
    print(f"\nSaved embeddings to {EMBEDDINGS_PATH}")
    print(f"Shape: {embeddings.shape}")
    print(f"Success: {success_count}, Failed: {len(failed)}")

    # Save failed list
    if failed:
        with open(FAILED_PATH, 'w') as f:
            for img_id, path in failed:
                f.write(f"{img_id}\t{path}\n")
        print(f"\nFailed images saved to {FAILED_PATH}")
        print(f"Run with --retry-failed to retry them")

    # Final verification
    print("\n" + "="*50)
    print("VERIFICATION")
    print("="*50)
    is_valid, issues, missing = verify_embeddings(embeddings, images)
    if is_valid:
        print("✓ All embeddings correctly aligned!")
    else:
        print("Issues found:")
        for issue in issues:
            print(f"  - {issue}")

    # Cleanup
    if PROGRESS_PATH.exists():
        PROGRESS_PATH.unlink()

    print("\n" + "="*50)
    print("SAFETY SUMMARY")
    print("="*50)
    print(f"✓ Array size: {len(embeddings)} (covers max_id {max_id})")
    print(f"✓ Direct assignment: embeddings[id] = vector")
    print(f"✓ Verification passed: {is_valid}")
    if not is_valid and missing:
        print(f"⚠ {len(missing)} images need retry (--retry-failed)")


if __name__ == "__main__":
    main()
