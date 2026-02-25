#!/usr/bin/env python3
"""Test script to debug CLIP text encoding hanging issue."""

import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("  🔍 Testing CLIP Text Encoding")
print("=" * 70)
print()

# Step 1: Load config
print("Step 1: Loading configuration...")
try:
    from src.config import load_config
    config = load_config(Path('config_optimized.yaml'))
    print(f"  ✓ Config loaded: model={config.model_name}, device={config.device}")
except Exception as e:
    print(f"  ✗ Config error: {e}")
    traceback.print_exc()
    sys.exit(1)

print()

# Step 2: Test model loading
print("Step 2: Loading CLIP model...")
print(f"  Model: {config.model_name}, Pretrained: {config.pretrained}, Device: {config.device}")
print("  (This might take 30-60 seconds on first load...)")
start_time = time.time()

try:
    from src.embeddings import EmbeddingModel
    model = EmbeddingModel(
        model_name=config.model_name,
        pretrained=config.pretrained,
        device=config.device
    )
    load_time = time.time() - start_time
    print(f"  ✓ Model loaded successfully in {load_time:.2f} seconds")
    print(f"  ✓ Embedding dimension: {model.embedding_dim}")
except Exception as e:
    print(f"  ✗ Model loading error: {e}")
    traceback.print_exc()
    sys.exit(1)

print()

# Step 3: Test text encoding (this is where it might hang)
print("Step 3: Testing text encoding...")
print("  (This might take 10-30 seconds on first encoding due to JIT compilation)")
print("  Encoding text: 'a photo of a cat'")

start_time = time.time()
try:
    test_query = "a photo of a cat"
    embedding = model.encode_text(test_query, normalize=True)
    encode_time = time.time() - start_time
    
    print(f"  ✓ Text encoded successfully in {encode_time:.2f} seconds")
    print(f"  ✓ Embedding shape: {embedding.shape}")
    print(f"  ✓ First 5 values: {embedding[:5]}")
    
    if encode_time > 60:
        print()
        print("  ⚠️  WARNING: Encoding took more than 60 seconds!")
        print("     This is very slow - might indicate a problem.")
    elif encode_time > 30:
        print()
        print("  ⚠️  WARNING: Encoding took more than 30 seconds.")
        print("     This is slow but might be normal on CPU (JIT compilation).")
        
except KeyboardInterrupt:
    print()
    print("  ✗ Text encoding was interrupted (took too long)")
    print("     This confirms the hanging issue!")
    sys.exit(1)
except Exception as e:
    print(f"  ✗ Text encoding error: {e}")
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 70)
print("  ✅ All tests passed!")
print()
print("If encoding works here but hangs in server, the issue might be:")
print("  1. Model not loaded during server startup")
print("  2. Server timeout/async issues")
print("  3. Different model configuration")
print("=" * 70)


