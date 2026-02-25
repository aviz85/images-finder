#!/usr/bin/env python3
"""Debug script to test text search and verify similarity scores."""

import sys
import numpy as np
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("  🔍 Debugging Text Search Process")
print("=" * 70)
print()

# Step 1: Load config and initialize search engine
print("Step 1: Loading configuration...")
from src.config import load_config
config = load_config(Path('config_optimized.yaml'))
print(f"  ✓ Config loaded: model={config.model_name}, device={config.device}")
print(f"  ✓ Embedding dimension: {config.embedding_dim}")
print()

# Step 2: Initialize search engine
print("Step 2: Initializing search engine...")
from src.search import ImageSearchEngine
search_engine = ImageSearchEngine(config, use_hybrid=True)
search_engine.initialize()
print(f"  ✓ Search engine initialized")
print()

# Step 3: Test simple queries
test_queries = ["sky", "cat", "dog", "sunset", "ocean"]

print("=" * 70)
print("  Testing Text Search Queries")
print("=" * 70)
print()

for query in test_queries:
    print(f"\n📝 Query: '{query}'")
    print("-" * 70)
    
    try:
        # Encode text query
        print(f"  Step 1: Encoding text query...")
        if search_engine.embedding_model is None:
            print("    ⚠️  WARNING: Embedding model is None!")
            break
        
        query_embedding = search_engine.embedding_model.encode_text(query, normalize=True)
        print(f"    ✓ Text encoded, shape: {query_embedding.shape}")
        print(f"    ✓ Embedding norm: {np.linalg.norm(query_embedding):.4f} (should be ~1.0)")
        print(f"    ✓ First 5 values: {query_embedding[:5]}")
        
        # Check dimension
        if query_embedding.shape[0] != config.embedding_dim:
            print(f"    ⚠️  WARNING: Dimension mismatch! {query_embedding.shape[0]} != {config.embedding_dim}")
        
        # Perform search
        print(f"  Step 2: Performing search...")
        results = search_engine.search_by_text(query, top_k=10)
        
        if not results:
            print(f"    ⚠️  WARNING: No results returned!")
            continue
        
        print(f"    ✓ Found {len(results)} results")
        print()
        print(f"  Step 3: Analyzing similarity scores...")
        print(f"  {'Rank':<6} {'Score':<12} {'% Similarity':<15} {'File Name'}")
        print(f"  {'-'*6} {'-'*12} {'-'*15} {'-'*50}")
        
        # Show top results with scores
        for i, result in enumerate(results[:10], 1):
            score = result.score
            similarity_percent = score * 100 if score <= 1.0 else (score / 10.0) * 100  # Handle different score ranges
            
            # Check if score is above 30%
            indicator = "✅" if similarity_percent >= 30 else "❌"
            
            file_name = Path(result.file_path).name[:47]
            print(f"  {i:<6} {score:>10.4f}   {similarity_percent:>6.2f}% {indicator:<3} {file_name}")
        
        # Analyze score distribution
        scores = [r.score for r in results]
        max_score = max(scores)
        min_score = min(scores)
        avg_score = np.mean(scores)
        
        print()
        print(f"  Score Statistics:")
        print(f"    Max:  {max_score:.4f} ({max_score*100:.2f}%)")
        print(f"    Min:  {min_score:.4f} ({min_score*100:.2f}%)")
        print(f"    Avg:  {avg_score:.4f} ({avg_score*100:.2f}%)")
        
        # Count results above 30%
        above_30 = sum(1 for s in scores if (s * 100 if s <= 1.0 else (s / 10.0) * 100) >= 30)
        print(f"    Above 30%: {above_30}/{len(scores)} results")
        
        if above_30 == 0:
            print(f"    ⚠️  WARNING: No results above 30% similarity!")
        
        # Show some actual file paths to verify relevance
        print()
        print(f"  Sample Results (first 3):")
        for i, result in enumerate(results[:3], 1):
            print(f"    {i}. {Path(result.file_path).name}")
            print(f"       Path: {result.file_path[:60]}...")
            print(f"       Score: {result.score:.4f}")
        
    except Exception as e:
        print(f"    ✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print()
        continue

print()
print("=" * 70)
print("  🔍 Additional Diagnostics")
print("=" * 70)
print()

# Check embeddings cache
print("Checking embeddings cache...")
try:
    from src.embeddings import EmbeddingCache
    cache = EmbeddingCache(config.embeddings_path)
    embeddings = cache.load()
    print(f"  ✓ Loaded {len(embeddings)} embeddings")
    print(f"  ✓ Shape: {embeddings.shape}")
    print(f"  ✓ Embedding dimension: {embeddings.shape[1]}")
    
    # Check if embeddings are normalized
    sample_norms = [np.linalg.norm(embeddings[i]) for i in range(min(10, len(embeddings)))]
    avg_norm = np.mean(sample_norms)
    print(f"  ✓ Average norm of sample embeddings: {avg_norm:.4f} (should be ~1.0)")
    
    if avg_norm < 0.9 or avg_norm > 1.1:
        print(f"    ⚠️  WARNING: Embeddings may not be normalized!")
        
except Exception as e:
    print(f"  ✗ Error loading embeddings: {e}")

# Check FAISS index
print()
print("Checking FAISS index...")
try:
    if search_engine.faiss_index and search_engine.faiss_index.index:
        index = search_engine.faiss_index.index
        print(f"  ✓ Index loaded")
        print(f"  ✓ Total vectors: {index.ntotal}")
        print(f"  ✓ Index type: {type(index).__name__}")
        
        if hasattr(index, 'nprobe'):
            print(f"  ✓ Nprobe: {index.nprobe}")
    else:
        print(f"  ⚠️  WARNING: FAISS index not loaded!")
        
except Exception as e:
    print(f"  ✗ Error checking index: {e}")

print()
print("=" * 70)
print("  ✅ Debug complete!")
print("=" * 70)


