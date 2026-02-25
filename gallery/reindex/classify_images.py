#!/usr/bin/env python3
"""
Classify gallery images as landscape/village vs people/crowd.
Uses CLIP zero-shot classification.
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
CLASS_DB = GALLERY_DIR / "reindex" / "classification.db"
THUMBNAILS_DIR = GALLERY_DIR / "thumbnails"

# Classification prompts
KEEP_PROMPTS = [
    "a village landscape",
    "settlement houses on a hill",
    "rural buildings and sky",
    "landscape with houses",
    "aerial view of settlement",
    "mountains and houses",
    "countryside with buildings",
    "wide shot of village",
    "houses in nature",
    "architectural exterior",
]

REMOVE_PROMPTS = [
    "a person",
    "people in crowd",
    "portrait of a person",
    "group of people",
    "close up of face",
    "human figure",
    "people gathering",
    "funeral ceremony",
    "protest with people",
    "soldiers or military personnel",
]


def init_class_db():
    """Create classification database."""
    conn = sqlite3.connect(str(CLASS_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS image_classification (
            id INTEGER PRIMARY KEY,
            original_path TEXT,
            thumbnail_path TEXT,
            keep_score REAL,
            remove_score REAL,
            classification TEXT,
            confidence REAL,
            processed_at TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_class ON image_classification(classification)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conf ON image_classification(confidence)")
    conn.commit()
    conn.close()
    print(f"✅ Classification DB: {CLASS_DB}")


def get_visible_images():
    """Get all visible images from gallery."""
    conn = sqlite3.connect(str(MAIN_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT id, original_path, thumbnail_path
        FROM gallery_images
        WHERE thumbnail_path IS NOT NULL
          AND (is_hidden IS NULL OR is_hidden = 0)
        ORDER BY id
    """)
    images = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return images


def get_already_processed():
    """Get IDs already processed."""
    conn = sqlite3.connect(str(CLASS_DB))
    try:
        ids = {r[0] for r in conn.execute("SELECT id FROM image_classification").fetchall()}
    except:
        ids = set()
    conn.close()
    return ids


def load_model():
    """Load CLIP model and tokenizer."""
    print("Loading CLIP model...")
    model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')
    tokenizer = open_clip.get_tokenizer('ViT-B-32')
    model.eval()
    return model, preprocess, tokenizer


def encode_text_prompts(model, tokenizer, prompts):
    """Encode text prompts."""
    with torch.no_grad():
        tokens = tokenizer(prompts)
        features = model.encode_text(tokens)
        features = features / features.norm(dim=-1, keepdim=True)
    return features


def classify_batch(model, preprocess, images, keep_features, remove_features):
    """Classify a batch of images."""
    results = []

    with torch.no_grad():
        batch_tensors = []
        valid_indices = []

        for i, img_info in enumerate(images):
            thumb_path = THUMBNAILS_DIR / img_info['thumbnail_path']
            if not thumb_path.exists():
                results.append(None)
                continue

            try:
                img = Image.open(thumb_path).convert('RGB')
                tensor = preprocess(img)
                batch_tensors.append(tensor)
                valid_indices.append(i)
            except Exception as e:
                results.append(None)

        if not batch_tensors:
            return results

        # Encode images
        batch = torch.stack(batch_tensors)
        img_features = model.encode_image(batch)
        img_features = img_features / img_features.norm(dim=-1, keepdim=True)

        # Compute similarities
        keep_sims = (img_features @ keep_features.T).mean(dim=1)
        remove_sims = (img_features @ remove_features.T).mean(dim=1)

        # Fill results
        result_idx = 0
        for i in range(len(images)):
            if i in valid_indices:
                keep_score = float(keep_sims[result_idx])
                remove_score = float(remove_sims[result_idx])

                # Classification based on which score is higher
                if keep_score > remove_score:
                    classification = "KEEP"
                    confidence = keep_score - remove_score
                else:
                    classification = "REMOVE"
                    confidence = remove_score - keep_score

                results.append({
                    'keep_score': keep_score,
                    'remove_score': remove_score,
                    'classification': classification,
                    'confidence': confidence
                })
                result_idx += 1
            else:
                if len(results) <= i:
                    results.append(None)

    return results


def save_results(images, results):
    """Save classification results to DB."""
    conn = sqlite3.connect(str(CLASS_DB))
    now = datetime.now().isoformat()

    records = []
    for img, result in zip(images, results):
        if result:
            records.append((
                img['id'],
                img['original_path'],
                img['thumbnail_path'],
                result['keep_score'],
                result['remove_score'],
                result['classification'],
                result['confidence'],
                now
            ))

    conn.executemany("""
        INSERT OR REPLACE INTO image_classification
        (id, original_path, thumbnail_path, keep_score, remove_score, classification, confidence, processed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, records)
    conn.commit()
    conn.close()


def get_stats():
    """Get classification stats."""
    conn = sqlite3.connect(str(CLASS_DB))
    stats = {}

    stats['total'] = conn.execute("SELECT COUNT(*) FROM image_classification").fetchone()[0]
    stats['keep'] = conn.execute("SELECT COUNT(*) FROM image_classification WHERE classification='KEEP'").fetchone()[0]
    stats['remove'] = conn.execute("SELECT COUNT(*) FROM image_classification WHERE classification='REMOVE'").fetchone()[0]

    # High confidence removes
    stats['high_conf_remove'] = conn.execute(
        "SELECT COUNT(*) FROM image_classification WHERE classification='REMOVE' AND confidence > 0.05"
    ).fetchone()[0]

    conn.close()
    return stats


def main():
    print("=" * 60)
    print("Image Classification: Landscape vs People")
    print("=" * 60)

    # Setup
    init_class_db()

    # Get images
    images = get_visible_images()
    print(f"📷 Visible images: {len(images)}")

    # Check already processed
    processed = get_already_processed()
    print(f"✅ Already processed: {len(processed)}")

    images = [img for img in images if img['id'] not in processed]
    print(f"📤 To process: {len(images)}")

    if not images:
        print("\n✅ All done!")
        stats = get_stats()
        print(f"\n📊 Stats: {stats}")
        return

    # Load model
    model, preprocess, tokenizer = load_model()

    # Encode prompts
    print("Encoding prompts...")
    keep_features = encode_text_prompts(model, tokenizer, KEEP_PROMPTS)
    remove_features = encode_text_prompts(model, tokenizer, REMOVE_PROMPTS)

    # Process in batches
    batch_size = 32

    for i in tqdm(range(0, len(images), batch_size), desc="Classifying"):
        batch = images[i:i+batch_size]
        results = classify_batch(model, preprocess, batch, keep_features, remove_features)
        save_results(batch, results)

    # Final stats
    stats = get_stats()
    print(f"\n📊 Final Stats:")
    print(f"   Total: {stats['total']}")
    print(f"   KEEP (landscapes): {stats['keep']}")
    print(f"   REMOVE (people): {stats['remove']}")
    print(f"   High-confidence removes: {stats['high_conf_remove']}")


if __name__ == "__main__":
    main()
