#!/usr/bin/env python3
"""
Find similar images based on approved/rejected seeds.
Run after client provides new IDs.
"""
import sqlite3
import numpy as np
from pathlib import Path
import re
import json

BASE = Path(__file__).parent.parent
DATA = BASE / 'data'
GALLERY = BASE.parent

def load_ids(filename):
    """Load IDs from text file."""
    text = (BASE / filename).read_text()
    return set(int(x) for x in re.findall(r'\d+', text))

def main():
    print("=" * 50)
    print("Finding Similar Images")
    print("=" * 50)

    # Load seeds
    approved = load_ids('approved_ids.txt')
    rejected = load_ids('rejected_ids.txt')
    print(f"✅ Approved: {len(approved)}")
    print(f"❌ Rejected: {len(rejected)}")

    # Load embeddings
    embeddings = np.load(DATA / 'gallery_embeddings.npy')
    print(f"📦 Embeddings: {len(embeddings)}")

    # Load mappings
    conn = sqlite3.connect(str(DATA / 'embeddings.db'))
    rows = conn.execute("SELECT id, thumbnail_path, embedding_idx FROM embedding_progress").fetchall()
    conn.close()

    id_to_idx = {r[0]: r[1] for r in rows}
    idx_to_id = {r[1]: r[0] for r in rows}
    id_to_thumb = {r[0]: r[1] for r in rows}

    # Get centroids
    good_idx = [id_to_idx[i] for i in approved if i in id_to_idx]
    bad_idx = [id_to_idx[i] for i in rejected if i in id_to_idx]

    good_centroid = embeddings[good_idx].mean(axis=0)
    good_centroid /= np.linalg.norm(good_centroid)

    if bad_idx:
        bad_centroid = embeddings[bad_idx].mean(axis=0)
        bad_centroid /= np.linalg.norm(bad_centroid)
    else:
        bad_centroid = None

    # Score all images
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    emb_norm = embeddings / norms

    good_sim = emb_norm @ good_centroid
    if bad_centroid is not None:
        bad_sim = emb_norm @ bad_centroid
        scores = good_sim - 0.7 * bad_sim
    else:
        scores = good_sim

    # Find candidates
    exclude = approved | rejected
    results = []
    for idx in np.argsort(scores)[::-1]:
        img_id = idx_to_id[idx]
        if img_id not in exclude:
            results.append({
                'id': img_id,
                'thumb': id_to_thumb[img_id],
                'score': float(scores[idx]),
                'good_sim': float(good_sim[idx])
            })
        if len(results) >= 500:
            break

    print(f"🔍 Found {len(results)} candidates")
    print(f"   Score range: {results[0]['score']:.3f} - {results[-1]['score']:.3f}")

    # Save results
    output = BASE / 'similar_results.json'
    with open(output, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"💾 Saved to {output}")

    # Print top 20
    print("\n📊 Top 20 candidates:")
    for r in results[:20]:
        print(f"   ID {r['id']}: score={r['score']:.3f}")

if __name__ == "__main__":
    main()
