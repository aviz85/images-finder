#!/usr/bin/env python3
"""
Comprehensive check of image embeddings quality.
Validates that embeddings are correct and meaningful.
"""

import numpy as np
from pathlib import Path
import sqlite3

def check_embeddings_file(embeddings_path):
    """Check if embeddings file exists and is valid."""
    print("=" * 70)
    print("  Step 1: Checking Embeddings File")
    print("=" * 70)
    
    if not embeddings_path.exists():
        print(f"  ❌ Embeddings file not found: {embeddings_path}")
        return None
    
    print(f"  ✓ Found embeddings file: {embeddings_path}")
    file_size = embeddings_path.stat().st_size / (1024 * 1024)  # MB
    print(f"  ✓ File size: {file_size:.2f} MB")
    
    try:
        embeddings = np.load(str(embeddings_path))
        print(f"  ✓ Successfully loaded embeddings")
        return embeddings
    except Exception as e:
        print(f"  ❌ Failed to load embeddings: {e}")
        return None

def check_normalization(embeddings):
    """Check if embeddings are properly normalized."""
    print("\n" + "=" * 70)
    print("  Step 2: Checking Normalization")
    print("=" * 70)
    
    if embeddings is None:
        print("  ❌ No embeddings to check")
        return False
    
    # Compute norms
    norms = np.linalg.norm(embeddings, axis=1)
    
    mean_norm = float(norms.mean())
    std_norm = float(norms.std())
    min_norm = float(norms.min())
    max_norm = float(norms.max())
    
    print(f"  Total embeddings: {len(embeddings)}")
    print(f"  Embedding dimension: {embeddings.shape[1]}")
    print(f"\n  Norm Statistics:")
    print(f"    Mean: {mean_norm:.6f} (should be ~1.0)")
    print(f"    Std:  {std_norm:.6f} (should be ~0.0)")
    print(f"    Min:  {min_norm:.6f}")
    print(f"    Max:  {max_norm:.6f}")
    
    # Check if normalized
    is_normalized = abs(mean_norm - 1.0) < 0.1 and std_norm < 0.1
    
    if is_normalized:
        print(f"\n  ✅ Embeddings ARE properly normalized")
    else:
        print(f"\n  ❌ Embeddings are NOT properly normalized!")
        print(f"     This will cause incorrect similarity scores.")
        print(f"     Recommendation: Re-normalize embeddings")
    
    return is_normalized

def check_value_distribution(embeddings):
    """Check the distribution of embedding values."""
    print("\n" + "=" * 70)
    print("  Step 3: Checking Value Distribution")
    print("=" * 70)
    
    if embeddings is None:
        print("  ❌ No embeddings to check")
        return False
    
    # Check for NaN or Inf
    has_nan = np.isnan(embeddings).any()
    has_inf = np.isinf(embeddings).any()
    
    print(f"  Contains NaN: {has_nan}")
    print(f"  Contains Inf: {has_inf}")
    
    if has_nan or has_inf:
        print(f"  ❌ Embeddings contain invalid values!")
        return False
    
    # Statistics
    mean_val = float(embeddings.mean())
    std_val = float(embeddings.std())
    min_val = float(embeddings.min())
    max_val = float(embeddings.max())
    
    print(f"\n  Value Statistics:")
    print(f"    Mean: {mean_val:.6f}")
    print(f"    Std:  {std_val:.6f}")
    print(f"    Min:  {min_val:.6f}")
    print(f"    Max:  {max_val:.6f}")
    
    # Check if values are reasonable (for normalized embeddings, should be small)
    if abs(mean_val) > 0.5 or std_val > 1.0:
        print(f"\n  ⚠️  Values seem unusual for normalized embeddings")
        print(f"     Expected: mean ~0, std ~0.1-0.3 for normalized vectors")
    
    # Check for all zeros
    all_zeros = np.allclose(embeddings, 0)
    if all_zeros:
        print(f"\n  ❌ All embeddings are zeros - this is wrong!")
        return False
    
    # Check for duplicates
    unique_embeddings = len(np.unique(embeddings, axis=0))
    print(f"\n  Unique embeddings: {unique_embeddings}/{len(embeddings)}")
    
    if unique_embeddings < len(embeddings) * 0.9:
        print(f"  ⚠️  Many duplicate embeddings found - this is unusual")
    
    return True

def check_similarity_distribution(embeddings, sample_size=1000):
    """Check similarity between random pairs of embeddings."""
    print("\n" + "=" * 70)
    print("  Step 4: Checking Similarity Distribution")
    print("=" * 70)
    
    if embeddings is None or len(embeddings) < 2:
        print("  ❌ Not enough embeddings to check")
        return False
    
    # Sample random pairs
    n = min(sample_size, len(embeddings))
    indices = np.random.choice(len(embeddings), n, replace=False)
    sample_embeddings = embeddings[indices]
    
    # Compute pairwise similarities
    # For normalized embeddings, dot product = cosine similarity
    similarities = np.dot(sample_embeddings, sample_embeddings.T)
    
    # Remove diagonal (self-similarity = 1.0)
    mask = ~np.eye(len(sample_embeddings), dtype=bool)
    pairwise_sims = similarities[mask]
    
    mean_sim = float(pairwise_sims.mean())
    std_sim = float(pairwise_sims.std())
    min_sim = float(pairwise_sims.min())
    max_sim = float(pairwise_sims.max())
    
    print(f"  Sampled {n} embeddings")
    print(f"  Computed {len(pairwise_sims)} pairwise similarities")
    print(f"\n  Similarity Statistics:")
    print(f"    Mean: {mean_sim:.6f} (should be ~0.0 for diverse images)")
    print(f"    Std:  {std_sim:.6f}")
    print(f"    Min:  {min_sim:.6f}")
    print(f"    Max:  {max_sim:.6f}")
    
    # Check if similarities are in valid range [-1, 1]
    if min_sim < -1.1 or max_sim > 1.1:
        print(f"\n  ❌ Similarities outside valid range [-1, 1]!")
        return False
    
    # For diverse images, mean similarity should be close to 0
    if abs(mean_sim) > 0.5:
        print(f"\n  ⚠️  Average similarity is high ({mean_sim:.4f})")
        print(f"     This suggests embeddings might be too similar")
    
    return True

def check_against_database(db_path, embeddings):
    """Check if embedding indices match database."""
    print("\n" + "=" * 70)
    print("  Step 5: Checking Against Database")
    print("=" * 70)
    
    if embeddings is None:
        print("  ❌ No embeddings to check")
        return False
    
    if not db_path.exists():
        print(f"  ❌ Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Count images with embeddings
        cursor.execute("""
            SELECT COUNT(*) FROM images 
            WHERE embedding_index IS NOT NULL
        """)
        db_count = cursor.fetchone()[0]
        
        print(f"  Images in database with embeddings: {db_count}")
        print(f"  Embeddings in file: {len(embeddings)}")
        
        if db_count != len(embeddings):
            print(f"  ⚠️  Count mismatch! Database: {db_count}, File: {len(embeddings)}")
        
        # Check embedding_index range
        cursor.execute("""
            SELECT MIN(embedding_index), MAX(embedding_index) 
            FROM images 
            WHERE embedding_index IS NOT NULL
        """)
        min_idx, max_idx = cursor.fetchone()
        
        if min_idx is not None:
            print(f"  Embedding index range: {min_idx} - {max_idx}")
            
            if max_idx >= len(embeddings):
                print(f"  ❌ Max embedding_index ({max_idx}) >= embeddings count ({len(embeddings)})!")
                print(f"     This will cause index errors!")
                conn.close()
                return False
        
        conn.close()
        print(f"  ✓ Database check passed")
        return True
        
    except Exception as e:
        print(f"  ❌ Database check failed: {e}")
        return False

def main():
    """Main function to run all checks."""
    print("=" * 70)
    print("  🔍 Comprehensive Embedding Quality Check")
    print("=" * 70)
    print()
    
    # Paths
    base_dir = Path("/Users/aviz/images-finder")
    embeddings_path = base_dir / "data" / "embeddings.npy"
    db_path = base_dir / "data" / "metadata.db"
    
    # Step 1: Load embeddings
    embeddings = check_embeddings_file(embeddings_path)
    
    if embeddings is None:
        print("\n" + "=" * 70)
        print("  ❌ Cannot proceed - embeddings file not found or invalid")
        print("=" * 70)
        return
    
    # Step 2-4: Various checks
    norm_ok = check_normalization(embeddings)
    dist_ok = check_value_distribution(embeddings)
    sim_ok = check_similarity_distribution(embeddings)
    db_ok = check_against_database(db_path, embeddings)
    
    # Summary
    print("\n" + "=" * 70)
    print("  Summary")
    print("=" * 70)
    
    all_ok = norm_ok and dist_ok and sim_ok and db_ok
    
    if all_ok:
        print("  ✅ All checks passed!")
        print("\n  The embeddings appear to be correct.")
        print("  If search still doesn't work, the issue might be:")
        print("    - Text-image embedding alignment")
        print("    - Query formatting")
        print("    - FAISS index configuration")
    else:
        print("  ❌ Issues found!")
        if not norm_ok:
            print("    - Embeddings are not normalized")
            print("      Fix: Re-normalize embeddings and rebuild index")
        if not dist_ok:
            print("    - Embedding values are invalid")
            print("      Fix: Regenerate embeddings")
        if not sim_ok:
            print("    - Similarity distribution is unusual")
            print("      Fix: Check embedding generation process")
        if not db_ok:
            print("    - Database mismatch")
            print("      Fix: Re-index images")
    
    print("=" * 70)

if __name__ == "__main__":
    main()


