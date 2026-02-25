#!/usr/bin/env python3
"""Simple test script to debug text search - can be run via server API."""

import sys
import json
from pathlib import Path

# Test via server API if server is running
import requests

BASE_URL = "http://localhost:8000"

def test_query(query: str, top_k: int = 10):
    """Test a text query and analyze results."""
    print(f"\n{'='*70}")
    print(f"Testing query: '{query}'")
    print(f"{'='*70}")
    
    try:
        response = requests.get(
            f"{BASE_URL}/search/text",
            params={"q": query, "top_k": top_k},
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        print(f"\nFound {len(results)} results")
        
        if not results:
            print("  ⚠️  No results returned!")
            return
        
        print(f"\n{'Rank':<6} {'Score':<12} {'% Match':<12} {'File Name'}")
        print(f"{'-'*6} {'-'*12} {'-'*12} {'-'*50}")
        
        scores_above_30 = 0
        for i, result in enumerate(results, 1):
            score = result.get("score", 0)
            
            # Handle different score formats
            # If score is already percentage-like (0-1), convert to %
            # If score is cosine similarity (-1 to 1), convert to %
            if -1 <= score <= 1:
                # Cosine similarity: convert to 0-100% range
                # -1 to 1 -> 0 to 100%
                percent = ((score + 1) / 2) * 100
            elif 0 <= score <= 1:
                # Already in 0-1 range
                percent = score * 100
            else:
                # Assume it's already a percentage
                percent = score
            
            indicator = "✅" if percent >= 30 else "❌"
            if percent >= 30:
                scores_above_30 += 1
            
            file_name = Path(result.get("file_path", "")).name[:47]
            print(f"{i:<6} {score:>10.4f}   {percent:>6.2f}%  {indicator:<3} {file_name}")
        
        print(f"\nResults above 30%: {scores_above_30}/{len(results)}")
        
        # Show first few file paths
        print(f"\nFirst 3 results:")
        for i, result in enumerate(results[:3], 1):
            print(f"  {i}. {result.get('file_path', 'N/A')[:70]}")
        
        return results
        
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error: {e}")
        print(f"  Make sure server is running at {BASE_URL}")
        return None

if __name__ == "__main__":
    print("="*70)
    print("  🔍 Text Search Debug Tool")
    print("="*70)
    print("\nTesting simple queries to verify search quality...")
    
    test_queries = ["sky", "cat", "dog", "sunset", "ocean", "car"]
    
    for query in test_queries:
        results = test_query(query, top_k=10)
    
    print(f"\n{'='*70}")
    print("  ✅ Test complete!")
    print("="*70)
    print("\nAnalysis:")
    print("  - If scores are consistently < 30%, there's a problem")
    print("  - If results are irrelevant, embeddings or search may be wrong")
    print("  - Check if embeddings are normalized correctly")
    print("  - Verify FAISS index is working correctly")


