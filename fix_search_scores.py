#!/usr/bin/env python3
"""
Debug and fix text search scoring issues.
Checks normalization, embedding alignment, and score interpretation.
"""

import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def check_embedding_normalization():
    """Check if cached embeddings are normalized."""
    print("=" * 70)
    print("  Step 1: Checking Embedding Normalization")
    print("=" * 70)
    
    from src.config import load_config
    config = load_config(Path('config_optimized.yaml'))
    
    # Load embeddings
    embeddings_path = config.embeddings_path
    if not embeddings_path.exists():
        print(f"  ❌ Embeddings file not found: {embeddings_path}")
        return False
    
    print(f"  Loading embeddings from: {embeddings_path}")
    embeddings = np.load(embeddings_path)
    print(f"  ✓ Loaded {len(embeddings)} embeddings")
    print(f"  ✓ Shape: {embeddings.shape}")
    
    # Check normalization
    norms = np.linalg.norm(embeddings, axis=1)
    mean_norm = norms.mean()
    std_norm = norms.std()
    min_norm = norms.min()
    max_norm = norms.max()
    
    print(f"\n  Normalization Statistics:")
    print(f"    Mean norm: {mean_norm:.6f} (should be ~1.0)")
    print(f"    Std norm:  {std_norm:.6f} (should be ~0.0)")
    print(f"    Min norm:  {min_norm:.6f}")
    print(f"    Max norm:  {max_norm:.6f}")
    
    if abs(mean_norm - 1.0) > 0.1 or std_norm > 0.1:
        print(f"\n  ⚠️  WARNING: Embeddings are NOT properly normalized!")
        print(f"     This will cause incorrect similarity scores.")
        print(f"     Recommendation: Re-normalize embeddings and rebuild index.")
        return False
    else:
        print(f"\n  ✅ Embeddings are properly normalized")
        return True

def test_text_image_alignment():
    """Test if text and image embeddings are aligned."""
    print("\n" + "=" * 70)
    print("  Step 2: Testing Text-Image Embedding Alignment")
    print("=" * 70)
    
    # This would require loading a known image with "sky"
    # For now, just check if we can encode text
    try:
        from src.config import load_config
        from src.embeddings import create_embedding_model
        
        config = load_config(Path('config_optimized.yaml'))
        model = create_embedding_model(config)
        
        # Encode test query
        test_query = "sky"
        text_emb = model.encode_text(test_query, normalize=True)
        text_norm = np.linalg.norm(text_emb)
        
        print(f"  Test query: '{test_query}'")
        print(f"  ✓ Text embedding shape: {text_emb.shape}")
        print(f"  ✓ Text embedding norm: {text_norm:.6f} (should be ~1.0)")
        
        if abs(text_norm - 1.0) > 0.1:
            print(f"  ⚠️  WARNING: Text embedding is NOT normalized!")
            return False
        else:
            print(f"  ✅ Text embedding is properly normalized")
            return True
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def analyze_score_distribution():
    """Analyze score distribution from actual search."""
    print("\n" + "=" * 70)
    print("  Step 3: Analyzing Score Distribution")
    print("=" * 70)
    
    import requests
    
    test_queries = ["sky", "cat", "dog", "sunset"]
    
    all_scores = []
    for query in test_queries:
        try:
            response = requests.get(
                "http://localhost:8000/search/text",
                params={"q": query, "top_k": 20},
                timeout=60
            )
            if response.status_code == 200:
                data = response.json()
                scores = [r["score"] for r in data.get("results", [])]
                all_scores.extend(scores)
                
                print(f"\n  Query: '{query}'")
                if scores:
                    print(f"    Scores: {min(scores):.4f} - {max(scores):.4f} (avg: {np.mean(scores):.4f})")
                    above_30 = sum(1 for s in scores if s >= 0.3)
                    print(f"    Above 30%: {above_30}/{len(scores)}")
                else:
                    print(f"    No results")
                    
        except Exception as e:
            print(f"  ❌ Error querying '{query}': {e}")
    
    if all_scores:
        print(f"\n  Overall Statistics:")
        print(f"    Total scores analyzed: {len(all_scores)}")
        print(f"    Mean score: {np.mean(all_scores):.4f} ({np.mean(all_scores)*100:.2f}%)")
        print(f"    Max score:  {max(all_scores):.4f} ({max(all_scores)*100:.2f}%)")
        print(f"    Min score:  {min(all_scores):.4f} ({min(all_scores)*100:.2f}%)")
        print(f"    Scores >= 0.3: {sum(1 for s in all_scores if s >= 0.3)}/{len(all_scores)}")
        
        if np.mean(all_scores) < 0.3:
            print(f"\n  ⚠️  WARNING: Average score is below 30%!")
            print(f"     This suggests embeddings may not be aligned correctly.")
            return False
    
    return True

def suggest_fixes():
    """Suggest fixes based on findings."""
    print("\n" + "=" * 70)
    print("  Recommended Fixes")
    print("=" * 70)
    
    print("""
  1. **Ensure Embeddings Are Normalized**
     - Check if cached embeddings are normalized
     - If not, re-normalize and rebuild index
  
  2. **Improve Query Formatting**
     - Try descriptive queries: "a photo of sky" instead of "sky"
     - CLIP works better with natural language descriptions
  
  3. **Check Embedding Model**
     - Verify text and image encoders use same CLIP model
     - Ensure both are normalized the same way
  
  4. **Rebuild Index**
     - If embeddings were fixed, rebuild FAISS index
     - This ensures index matches normalized embeddings
  
  5. **Test with Known Images**
     - Find images that clearly contain "sky"
     - Test if they get high scores
     - This verifies the system works correctly
    """)

if __name__ == "__main__":
    print("=" * 70)
    print("  🔍 Text Search Debugging Tool")
    print("=" * 70)
    print()
    
    # Step 1: Check normalization
    norm_ok = check_embedding_normalization()
    
    # Step 2: Test alignment
    align_ok = test_text_image_alignment()
    
    # Step 3: Analyze scores
    print("\n  Note: Skipping score analysis (requires server to be running)")
    # score_ok = analyze_score_distribution()
    
    # Summary
    print("\n" + "=" * 70)
    print("  Summary")
    print("=" * 70)
    
    if norm_ok and align_ok:
        print("  ✅ Basic checks passed")
        print("  ⚠️  If scores are still low, try:")
        print("     1. More descriptive queries (e.g., 'a photo of sky')")
        print("     2. Rebuilding the FAISS index")
        print("     3. Checking if database contains relevant images")
    else:
        print("  ❌ Issues found - see recommendations above")
    
    suggest_fixes()


