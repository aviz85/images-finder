#!/usr/bin/env python3
"""
Generate CLIP embeddings for gallery images.
Saves to separate file, doesn't touch main project embeddings.
Resumable - tracks progress in SQLite.
"""

import sqlite3
import numpy as np
from pathlib import Path
import torch
from PIL import Image
from tqdm import tqdm
import open_clip
from datetime import datetime

# Paths
GALLERY_DIR = Path(__file__).parent.parent
MAIN_DB = GALLERY_DIR / "gallery.db"
EMBED_DB = GALLERY_DIR / "reindex" / "embeddings.db"
EMBED_NPY = GALLERY_DIR / "reindex" / "gallery_embeddings.npy"
THUMBNAILS_DIR = GALLERY_DIR / "thumbnails"


def init_embed_db():
    """Create embeddings tracking database."""
    conn = sqlite3.connect(str(EMBED_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS embedding_progress (
            id INTEGER PRIMARY KEY,
            thumbnail_path TEXT,
            embedding_idx INTEGER,
            processed_at TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_id ON embedding_progress(id)")
    conn.commit()
    conn.close()
    print(f"✅ Embeddings DB: {EMBED_DB}")


def get_visible_images():
    """Get all visible images from gallery."""
    conn = sqlite3.connect(str(MAIN_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT id, thumbnail_path
        FROM gallery_images
        WHERE thumbnail_path IS NOT NULL
          AND (is_hidden IS NULL OR is_hidden = 0)
        ORDER BY id
    """)
    images = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return images


def get_processed_ids():
    """Get IDs already processed."""
    conn = sqlite3.connect(str(EMBED_DB))
    try:
        ids = {r[0] for r in conn.execute("SELECT id FROM embedding_progress").fetchall()}
    except:
        ids = set()
    conn.close()
    return ids


def load_existing_embeddings():
    """Load existing embeddings if any."""
    if EMBED_NPY.exists():
        return np.load(str(EMBED_NPY))
    return None


def load_model():
    """Load CLIP model."""
    print("🔄 Loading CLIP model (ViT-B-32)...")
    model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')
    model.eval()
    print("✅ Model loaded")
    return model, preprocess


def embed_batch(model, preprocess, images):
    """Generate embeddings for a batch of images."""
    embeddings = []
    valid_indices = []

    with torch.no_grad():
        batch_tensors = []

        for i, img_info in enumerate(images):
            thumb_path = THUMBNAILS_DIR / img_info['thumbnail_path']
            if not thumb_path.exists():
                embeddings.append(None)
                continue

            try:
                img = Image.open(thumb_path).convert('RGB')
                tensor = preprocess(img)
                batch_tensors.append(tensor)
                valid_indices.append(i)
            except Exception as e:
                embeddings.append(None)

        if not batch_tensors:
            return embeddings

        # Encode images
        batch = torch.stack(batch_tensors)
        features = model.encode_image(batch)
        features = features / features.norm(dim=-1, keepdim=True)
        features = features.cpu().numpy()

        # Fill results
        result_idx = 0
        for i in range(len(images)):
            if i in valid_indices:
                embeddings.append(features[result_idx])
                result_idx += 1
            elif len(embeddings) <= i:
                embeddings.append(None)

    return embeddings


def save_progress(images, embeddings, all_embeddings):
    """Save embeddings and progress."""
    conn = sqlite3.connect(str(EMBED_DB))
    now = datetime.now().isoformat()

    for img, emb in zip(images, embeddings):
        if emb is not None:
            idx = len(all_embeddings)
            all_embeddings.append(emb)
            conn.execute("""
                INSERT OR REPLACE INTO embedding_progress (id, thumbnail_path, embedding_idx, processed_at)
                VALUES (?, ?, ?, ?)
            """, (img['id'], img['thumbnail_path'], idx, now))

    conn.commit()
    conn.close()

    # Save numpy file
    if all_embeddings:
        np.save(str(EMBED_NPY), np.array(all_embeddings))


def get_stats():
    """Get embedding stats."""
    conn = sqlite3.connect(str(EMBED_DB))
    total = conn.execute("SELECT COUNT(*) FROM embedding_progress").fetchone()[0]
    conn.close()
    return total


def main():
    print("=" * 60)
    print("Gallery Image Embedding Generation")
    print("=" * 60)

    # Setup
    init_embed_db()

    # Get images
    images = get_visible_images()
    print(f"📷 Visible images: {len(images)}")

    # Check progress
    processed = get_processed_ids()
    print(f"✅ Already embedded: {len(processed)}")

    # Load existing embeddings
    existing = load_existing_embeddings()
    if existing is not None:
        all_embeddings = list(existing)
        print(f"📦 Loaded {len(all_embeddings)} existing embeddings")
    else:
        all_embeddings = []

    # Filter to unprocessed
    to_process = [img for img in images if img['id'] not in processed]
    print(f"📤 To embed: {len(to_process)}")

    if not to_process:
        print("\n✅ All images already embedded!")
        return

    # Load model
    model, preprocess = load_model()

    # Process in batches
    batch_size = 32
    save_every = 100  # Save every N batches

    for i in tqdm(range(0, len(to_process), batch_size), desc="Embedding"):
        batch = to_process[i:i+batch_size]
        embeddings = embed_batch(model, preprocess, batch)
        save_progress(batch, embeddings, all_embeddings)

        # Periodic status
        if (i // batch_size) % save_every == 0 and i > 0:
            print(f"\n  📊 Progress: {get_stats()}/{len(images)} embedded")

    # Final stats
    total = get_stats()
    print(f"\n✅ Embedding complete!")
    print(f"   Total embedded: {total}")
    print(f"   Saved to: {EMBED_NPY}")
    print(f"   File size: {EMBED_NPY.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
