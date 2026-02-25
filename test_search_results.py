#!/usr/bin/env python3
"""
Comprehensive test of text search after fixes.
Tests multiple queries and validates result quality.
"""

import requests
import json
from pathlib import Path
import time

BASE_URL = "http://localhost:8000"

def test_query(query: str, top_k: int = 10, min_score: float = 0.3):
    """Test a single query and analyze results."""
    print(f"\n{'='*70}")
    print(f"🔍 Testing Query: '{query}'")
    print(f"{'='*70}")
    
    try:
        start_time = time.time()
        response = requests.get(
            f"{BASE_URL}/search/text",
            params={"q": query, "top_k": top_k},
            timeout=60
        )
        elapsed = time.time() - start_time
        
        if response.status_code != 200:
            print(f"❌ Error: HTTP {response.status_code}")
            print(f"   {response.text[:200]}")
            return False
        
        data = response.json()
        results = data.get("results", [])
        
        print(f"⏱️  Response time: {elapsed:.2f} seconds")
        print(f"📊 Found {len(results)} results")
        
        if not results:
            print("⚠️  No results returned!")
            return False
        
        # Analyze scores
        scores = [r.get("score", 0) for r in results]
        max_score = max(scores)
        min_score_result = min(scores)
        avg_score = sum(scores) / len(scores)
        
        # Count results above threshold
        above_threshold = sum(1 for s in scores if s >= min_score)
        
        print(f"\n📈 Score Statistics:")
        print(f"   Max:  {max_score:.4f} ({max_score*100:.2f}%)")
        print(f"   Min:  {min_score_result:.4f} ({min_score_result*100:.2f}%)")
        print(f"   Avg:  {avg_score:.4f} ({avg_score*100:.2f}%)")
        print(f"   Above {min_score*100:.0f}%: {above_threshold}/{len(scores)}")
        
        # Check if we have good results
        if max_score < min_score:
            print(f"\n❌ All scores below {min_score*100:.0f}% threshold!")
            print(f"   This suggests poor matches or search issues.")
            return False
        
        # Show top results
        print(f"\n🏆 Top 5 Results:")
        print(f"{'Rank':<6} {'Score':<12} {'% Match':<12} {'File Name'}")
        print(f"{'-'*6} {'-'*12} {'-'*12} {'-'*50}")
        
        for i, result in enumerate(results[:5], 1):
            score = result.get("score", 0)
            percent = score * 100
            indicator = "✅" if score >= min_score else "❌"
            file_name = Path(result.get("file_path", "")).name[:47]
            print(f"{i:<6} {score:>10.4f}   {percent:>6.2f}%  {indicator:<3} {file_name}")
        
        # Show file paths for relevance check
        print(f"\n📁 File Paths (first 3):")
        for i, result in enumerate(results[:3], 1):
            file_path = result.get("file_path", "")
            print(f"   {i}. {file_path[:70]}")
        
        # Validation
        success = max_score >= min_score and above_threshold >= 3
        
        if success:
            print(f"\n✅ Query passed validation!")
        else:
            print(f"\n⚠️  Query results may need improvement")
        
        return success
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_server_health():
    """Test if server is running and responsive."""
    print("=" * 70)
    print("  🏥 Server Health Check")
    print("=" * 70)
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
            return True
        else:
            print(f"⚠️  Server returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Server not responding: {e}")
        print(f"   Make sure server is running at {BASE_URL}")
        return False

def test_stats():
    """Check server stats."""
    print("\n" + "=" * 70)
    print("  📊 Server Statistics")
    print("=" * 70)
    
    try:
        response = requests.get(f"{BASE_URL}/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"Total images: {data.get('total_images', 0):,}")
            print(f"Processed: {data.get('processed_images', 0):,}")
            print(f"Index ready: {data.get('index_ready', False)}")
            return True
        else:
            print(f"⚠️  Could not get stats: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        return False

def main():
    """Run comprehensive search tests."""
    print("=" * 70)
    print("  🧪 Comprehensive Search Quality Tests")
    print("=" * 70)
    print()
    
    # Test 1: Server health
    if not test_server_health():
        print("\n❌ Server is not running. Please start the server first.")
        print("   Run: python server.py")
        return
    
    # Test 2: Stats
    test_stats()
    
    # Test 3: Multiple queries
    print("\n" + "=" * 70)
    print("  🔍 Testing Search Queries")
    print("=" * 70)
    
    test_queries = [
        "sky",
        "cat",
        "dog", 
        "sunset",
        "ocean",
        "car",
        "person",
        "building"
    ]
    
    results = {}
    for query in test_queries:
        success = test_query(query, top_k=10, min_score=0.3)
        results[query] = success
        time.sleep(1)  # Small delay between queries
    
    # Summary
    print("\n" + "=" * 70)
    print("  📊 Test Summary")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total} queries")
    print(f"\nResults:")
    for query, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} - '{query}'")
    
    if passed == total:
        print(f"\n🎉 All tests passed! Search is working correctly.")
    elif passed > total // 2:
        print(f"\n⚠️  Some tests failed. Search works but may need tuning.")
    else:
        print(f"\n❌ Many tests failed. Search may have issues.")
    
    print("=" * 70)

if __name__ == "__main__":
    main()


