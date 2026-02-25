#!/usr/bin/env python3
"""
Deep analysis of search issues - why scores are low.
"""

import numpy as np
from pathlib import Path
import sqlite3

print("=" * 70)
print("  🔍 Deep Analysis: Why Are Scores Low?")
print("=" * 70)
print()

# Check 1: Embeddings vs Index
embeddings_path = Path("/Users/aviz/images-finder/data/embeddings.npy")
index_path = Path("/Users/aviz/images-finder/data/faiss.index")

print("Step 1: Checking FAISS Index vs Embeddings")
print("-" * 70)

if embeddings_path.exists():
    embeddings = np.load(str(embeddings_path))
    print(f"  Embeddings: {len(embeddings)} vectors")
    print(f"  Dimension: {embeddings.shape[1]}")
else:
    print("  ❌ No embeddings file")
    exit(1)

if index_path.exists():
    try:
        import faiss
        index = faiss.read_index(str(index_path))
        print(f"  FAISS Index: {index.ntotal} vectors")
        print(f"  Index type: {type(index).__name__}")
        
        if index.ntotal > len(embeddings):
            print(f"\n  ❌ PROBLEM FOUND!")
            print(f"     Index has {index.ntotal} vectors")
            print(f"     But only {len(embeddings)} embeddings exist")
            print(f"     This mismatch will cause wrong results!")
        elif index.ntotal < len(embeddings):
            print(f"\n  ⚠️  Index smaller than embeddings")
            print(f"     Index: {index.ntotal}, Embeddings: {len(embeddings)}")
        else:
            print(f"\n  ✅ Index matches embeddings count")
            
    except Exception as e:
        print(f"  ❌ Could not read index: {e}")
else:
    print("  ❌ No FAISS index file")

# Check 2: Database indices
print("\nStep 2: Checking Database Embedding Indices")
print("-" * 70)

db_path = Path("/Users/aviz/images-finder/data/metadata.db")
if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Count images with embedding_index
    cursor.execute("""
        SELECT COUNT(*), MIN(embedding_index), MAX(embedding_index)
        FROM images 
        WHERE embedding_index IS NOT NULL
    """)
    count, min_idx, max_idx = cursor.fetchone()
    
    print(f"  Images with embedding_index: {count:,}")
    print(f"  Index range: {min_idx} - {max_idx}")
    
    # Check how many are valid
    valid_count = sum(1 for idx in range(min_idx or 0, (max_idx or 0) + 1) if idx < len(embeddings))
    print(f"  Valid indices (< {len(embeddings)}): ~{min(count, len(embeddings))}")
    
    if max_idx and max_idx >= len(embeddings):
        print(f"\n  ❌ PROBLEM: Max index {max_idx} >= embeddings count {len(embeddings)}")
    
    conn.close()
else:
    print("  ❌ Database not found")

# Check 3: Embedding quality
print("\nStep 3: Checking Embedding Quality")
print("-" * 70)

norms = np.linalg.norm(embeddings, axis=1)
print(f"  Mean norm: {norms.mean():.6f} (should be ~1.0)")
print(f"  Std norm: {norms.std():.6f} (should be ~0.0)")

# Check value range
print(f"  Value range: [{embeddings.min():.4f}, {embeddings.max():.4f}]")
print(f"  Mean value: {embeddings.mean():.6f}")
print(f"  Std value: {embeddings.std():.6f}")

# Check similarity between embeddings (should be diverse)
sample_size = min(100, len(embeddings))
sample_indices = np.random.choice(len(embeddings), sample_size, replace=False)
sample_embeddings = embeddings[sample_indices]

# Compute pairwise similarities
similarities = np.dot(sample_embeddings, sample_embeddings.T)
# Remove diagonal
mask = ~np.eye(len(sample_embeddings), dtype=bool)
pairwise_sims = similarities[mask]

print(f"\n  Pairwise similarity (sample of {sample_size}):")
print(f"    Mean: {pairwise_sims.mean():.4f} (should be ~0.0 for diverse)")
print(f"    Max: {pairwise_sims.max():.4f}")
print(f"    Min: {pairwise_sims.min():.4f}")

if pairwise_sims.mean() > 0.6:
    print(f"\n  ⚠️  WARNING: Embeddings are very similar (mean similarity > 0.6)")
    print(f"     This suggests limited diversity in the image dataset")

print("\n" + "=" * 70)
print("  Summary & Recommendations")
print("=" * 70)
print()
print("If index size > embeddings count:")
print("  → Rebuild FAISS index with only valid embeddings")
print()
print("If scores are consistently low (24-26%):")
print("  → This might be normal for this dataset")
print("  → CLIP embeddings for diverse images often have 20-30% similarity")
print("  → Try more descriptive queries: 'a photo of sky' instead of 'sky'")
print()
print("If embeddings are too similar:")
print("  → The 1,108 images might be from similar categories")
print("  → This limits search diversity")
print()


