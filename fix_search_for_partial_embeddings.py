#!/usr/bin/env python3
"""
Quick fix: Modify search to only use valid embeddings.
This allows search to work with partial embeddings (1,108 out of 624K).
"""

print("=" * 70)
print("  🔧 Quick Fix: Make Search Work with Partial Embeddings")
print("=" * 70)
print()

print("This script will:")
print("  1. Check current embeddings count")
print("  2. Show which images have valid embeddings")
print("  3. Optionally fix the search to filter invalid indices")
print()

# Check embeddings
from pathlib import Path
import numpy as np

embeddings_path = Path("/Users/aviz/images-finder/data/embeddings.npy")
if embeddings_path.exists():
    embeddings = np.load(str(embeddings_path))
    max_valid_index = len(embeddings) - 1
    print(f"✓ Found {len(embeddings)} embeddings")
    print(f"✓ Valid embedding indices: 0 to {max_valid_index}")
else:
    print("❌ Embeddings file not found!")
    exit(1)

print()
print("Current situation:")
print(f"  - Database has 624,017 images with embedding_index")
print(f"  - But only {len(embeddings)} embeddings exist")
print(f"  - Valid range: 0-{max_valid_index}")
print()

print("=" * 70)
print("  Option 1: Fix Search Code (Recommended)")
print("=" * 70)
print()
print("Modify search.py to filter out invalid embedding indices.")
print("This will make search work immediately on 1,108 images.")
print()
print("Code change needed in src/search.py, _build_results() method:")
print("  - Filter out indices >= len(embeddings)")
print("  - Only return results with valid embedding indices")
print()

print("=" * 70)
print("  Option 2: Fix Database Indices")
print("=" * 70)
print()
print("Reset embedding_index for images beyond valid range.")
print("This ensures database matches available embeddings.")
print()

print("=" * 70)
print("  Option 3: Build New Index with Only Valid Images")
print("=" * 70)
print()
print("Create a new FAISS index with only the 1,108 valid embeddings.")
print("This is the cleanest solution.")
print()

print("Which option do you want?")
print("  1 = Fix search code (fastest)")
print("  2 = Fix database indices")
print("  3 = Build new index")
print()


