#!/usr/bin/env python3
"""
Classify gallery images using pre-computed embeddings.
Uses CLIP text embeddings to match against image embeddings.
"""

import sqlite3
import numpy as np
from pathlib import Path
import torch
import open_clip
from datetime import datetime
from tqdm import tqdm

# Paths
GALLERY_DIR = Path(__file__).parent.parent
EMBED_DB = GALLERY_DIR / "reindex" / "embeddings.db"
EMBED_NPY = GALLERY_DIR / "reindex" / "gallery_embeddings.npy"
CLASS_DB = GALLERY_DIR / "reindex" / "classification.db"

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
    "rooftops and buildings",
    "hillside settlement",
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
    "wedding ceremony",
    "indoor event with people",
]


def init_class_db():
    """Create classification database."""
    conn = sqlite3.connect(str(CLASS_DB))
    conn.execute("DROP TABLE IF EXISTS image_classification")
    conn.execute("""
        CREATE TABLE image_classification (
            id INTEGER PRIMARY KEY,
            thumbnail_path TEXT,
            embedding_idx INTEGER,
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


def load_embeddings_with_ids():
    """Load embeddings and their image IDs."""
    conn = sqlite3.connect(str(EMBED_DB))
    rows = conn.execute("""
        SELECT id, thumbnail_path, embedding_idx
        FROM embedding_progress
        ORDER BY embedding_idx
    """).fetchall()
    conn.close()

    embeddings = np.load(str(EMBED_NPY))
    print(f"📦 Loaded {len(embeddings)} embeddings")

    return rows, embeddings


def encode_text_prompts(model, tokenizer, prompts):
    """Encode text prompts."""
    with torch.no_grad():
        tokens = tokenizer(prompts)
        features = model.encode_text(tokens)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.cpu().numpy()


def classify_embeddings(embeddings, keep_features, remove_features):
    """Classify all embeddings at once."""
    # Normalize embeddings
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings_norm = embeddings / norms

    # Compute similarities
    keep_sims = embeddings_norm @ keep_features.T  # (N, num_keep_prompts)
    remove_sims = embeddings_norm @ remove_features.T  # (N, num_remove_prompts)

    # Average across prompts
    keep_scores = keep_sims.mean(axis=1)
    remove_scores = remove_sims.mean(axis=1)

    # Classification
    classifications = []
    for keep_score, remove_score in zip(keep_scores, remove_scores):
        if keep_score > remove_score:
            classifications.append(("KEEP", keep_score - remove_score))
        else:
            classifications.append(("REMOVE", remove_score - keep_score))

    return keep_scores, remove_scores, classifications


def save_results(rows, keep_scores, remove_scores, classifications):
    """Save classification results."""
    conn = sqlite3.connect(str(CLASS_DB))
    now = datetime.now().isoformat()

    records = []
    for i, (img_id, thumb_path, emb_idx) in enumerate(rows):
        classification, confidence = classifications[i]
        records.append((
            img_id,
            thumb_path,
            emb_idx,
            float(keep_scores[i]),
            float(remove_scores[i]),
            classification,
            float(confidence),
            now
        ))

    conn.executemany("""
        INSERT INTO image_classification
        (id, thumbnail_path, embedding_idx, keep_score, remove_score, classification, confidence, processed_at)
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
    stats['high_conf_keep'] = conn.execute(
        "SELECT COUNT(*) FROM image_classification WHERE classification='KEEP' AND confidence > 0.03"
    ).fetchone()[0]
    stats['high_conf_remove'] = conn.execute(
        "SELECT COUNT(*) FROM image_classification WHERE classification='REMOVE' AND confidence > 0.03"
    ).fetchone()[0]
    conn.close()
    return stats


def main():
    print("=" * 60)
    print("Classification from Pre-computed Embeddings")
    print("=" * 60)

    # Check embeddings exist
    if not EMBED_NPY.exists():
        print("❌ Embeddings file not found! Run embed_gallery.py first.")
        return

    # Setup
    init_class_db()

    # Load embeddings
    rows, embeddings = load_embeddings_with_ids()

    # Load CLIP model for text encoding
    print("🔄 Loading CLIP model for text encoding...")
    model, _, _ = open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')
    tokenizer = open_clip.get_tokenizer('ViT-B-32')
    model.eval()

    # Encode prompts
    print("📝 Encoding classification prompts...")
    keep_features = encode_text_prompts(model, tokenizer, KEEP_PROMPTS)
    remove_features = encode_text_prompts(model, tokenizer, REMOVE_PROMPTS)
    print(f"   KEEP prompts: {len(KEEP_PROMPTS)}")
    print(f"   REMOVE prompts: {len(REMOVE_PROMPTS)}")

    # Classify all at once (vectorized)
    print("🔄 Classifying embeddings...")
    keep_scores, remove_scores, classifications = classify_embeddings(
        embeddings, keep_features, remove_features
    )

    # Save results
    print("💾 Saving results...")
    save_results(rows, keep_scores, remove_scores, classifications)

    # Stats
    stats = get_stats()
    print(f"\n✅ Classification complete!")
    print(f"   Total: {stats['total']}")
    print(f"   KEEP (landscapes): {stats['keep']} ({stats['keep']*100/stats['total']:.1f}%)")
    print(f"   REMOVE (people): {stats['remove']} ({stats['remove']*100/stats['total']:.1f}%)")
    print(f"   High-confidence KEEP: {stats['high_conf_keep']}")
    print(f"   High-confidence REMOVE: {stats['high_conf_remove']}")


if __name__ == "__main__":
    main()
