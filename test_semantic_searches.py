#!/usr/bin/env python3
"""
Test 50 diverse semantic searches on ImageSearch FAISS system.
Verifies that search works and results are valid images.
"""

import requests
import os
import time
import json
from pathlib import Path

API_URL = "http://localhost:5001/api/search/text"

# 50 diverse search queries covering many categories
QUERIES = [
    # Nature & Landscapes
    "sunset over ocean",
    "mountain landscape with snow",
    "forest path in autumn",
    "desert sand dunes",
    "tropical beach with palm trees",
    "waterfall in jungle",
    "green meadow with flowers",
    "stormy sky with lightning",
    "lake reflection at dawn",
    "aurora borealis northern lights",

    # People & Activities
    "family portrait smiling",
    "children playing in park",
    "wedding ceremony outdoor",
    "birthday party celebration",
    "people hiking mountain trail",
    "crowd at concert",
    "graduation ceremony",
    "elderly couple holding hands",
    "baby sleeping peacefully",
    "friends laughing together",

    # Animals
    "dog running on beach",
    "cat sleeping on couch",
    "birds flying in sky",
    "horse galloping in field",
    "fish in aquarium",
    "butterfly on flower",
    "lion in savanna",
    "penguin on ice",
    "squirrel eating nut",
    "owl at night",

    # Urban & Architecture
    "city skyline at night",
    "old european street",
    "modern glass building",
    "bridge over river",
    "colorful houses",
    "church with steeple",
    "busy street market",
    "graffiti on wall",
    "train station platform",
    "lighthouse on cliff",

    # Food & Objects
    "fresh fruit basket",
    "coffee cup on table",
    "birthday cake with candles",
    "pizza with toppings",
    "flowers in vase",
    "books on shelf",
    "vintage car",
    "musical instruments",
    "christmas decorations",
    "colorful balloons",
]

def test_search(query, top_k=10):
    """Run a single search and verify results."""
    try:
        response = requests.post(API_URL, json={"query": query, "top_k": top_k}, timeout=60)

        if response.status_code != 200:
            return {"query": query, "status": "error", "error": f"HTTP {response.status_code}"}

        data = response.json()
        results = data.get("results", [])

        if not results:
            return {"query": query, "status": "no_results", "count": 0}

        # Check if result paths exist
        valid_count = 0
        invalid_paths = []
        scores = []

        for r in results[:5]:  # Check first 5 results
            path = r.get("path", "")
            score = r.get("score", 0)
            scores.append(score)

            if path and os.path.exists(path):
                valid_count += 1
            else:
                invalid_paths.append(path)

        return {
            "query": query,
            "status": "success" if valid_count > 0 else "paths_invalid",
            "count": len(results),
            "valid_files": valid_count,
            "checked": min(5, len(results)),
            "avg_score": sum(scores) / len(scores) if scores else 0,
            "top_score": max(scores) if scores else 0,
            "sample_path": results[0].get("path", "") if results else "",
            "invalid_paths": invalid_paths[:2] if invalid_paths else []
        }

    except requests.exceptions.Timeout:
        return {"query": query, "status": "timeout"}
    except Exception as e:
        return {"query": query, "status": "error", "error": str(e)}

def main():
    print("=" * 70)
    print("SEMANTIC SEARCH TEST - 50 Queries")
    print("=" * 70)
    print()

    # Check server is up
    try:
        status = requests.get("http://localhost:5001/api/status", timeout=5)
        print(f"Server status: {status.status_code}")
    except:
        print("ERROR: Server not responding!")
        return

    results = []
    success_count = 0
    failed_count = 0
    total_valid_files = 0

    start_time = time.time()

    for i, query in enumerate(QUERIES, 1):
        print(f"[{i:2d}/50] Testing: {query[:40]:<40}", end=" ")

        result = test_search(query)
        results.append(result)

        if result["status"] == "success":
            success_count += 1
            total_valid_files += result.get("valid_files", 0)
            print(f"✅ {result['count']:3d} results, score: {result['top_score']:.3f}")
        else:
            failed_count += 1
            print(f"❌ {result['status']}: {result.get('error', result.get('invalid_paths', ''))}")

        # Small delay to not overwhelm
        time.sleep(0.1)

    elapsed = time.time() - start_time

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total queries:     {len(QUERIES)}")
    print(f"Successful:        {success_count}")
    print(f"Failed:            {failed_count}")
    print(f"Success rate:      {success_count/len(QUERIES)*100:.1f}%")
    print(f"Valid files found: {total_valid_files}")
    print(f"Time elapsed:      {elapsed:.1f}s")
    print(f"Avg per query:     {elapsed/len(QUERIES):.2f}s")
    print()

    # Show score distribution
    scores = [r.get("top_score", 0) for r in results if r.get("status") == "success"]
    if scores:
        print(f"Score range:       {min(scores):.3f} - {max(scores):.3f}")
        print(f"Average score:     {sum(scores)/len(scores):.3f}")

    # Show any failures
    failures = [r for r in results if r["status"] != "success"]
    if failures:
        print()
        print("FAILED QUERIES:")
        for f in failures[:5]:
            print(f"  - {f['query']}: {f['status']}")

    # Sample results
    print()
    print("SAMPLE RESULTS (first 3 successful):")
    shown = 0
    for r in results:
        if r["status"] == "success" and shown < 3:
            print(f"  Query: '{r['query']}'")
            print(f"    Results: {r['count']}, Top score: {r['top_score']:.3f}")
            print(f"    Sample: {r['sample_path'][:80]}...")
            print()
            shown += 1

    # Final verdict
    print("=" * 70)
    if success_count >= 45:
        print("✅ VERDICT: EXCELLENT - System working as expected!")
    elif success_count >= 40:
        print("✅ VERDICT: GOOD - Most searches working")
    elif success_count >= 25:
        print("⚠️  VERDICT: PARTIAL - Some issues detected")
    else:
        print("❌ VERDICT: FAILING - Major issues detected")
    print("=" * 70)

    # Save detailed results
    with open("/Users/aviz/images-finder/search_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to search_test_results.json")

if __name__ == "__main__":
    main()
