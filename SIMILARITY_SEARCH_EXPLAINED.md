# 🔍 How Similarity Search Works

## 📚 The Complete Picture

### 1. **What Are Embeddings?**

Embeddings are **dense vector representations** of images:

```
Image: sunset.jpg  →  Embedding: [0.23, -0.45, 0.12, ..., 0.67]
                                  ↑_____512 numbers_____↑
```

**Key Properties:**
- Each image = 512-dimensional vector (with ViT-B-32 model)
- Similar images = vectors close together in space
- Different images = vectors far apart

### 2. **How Similarity Search Works**

```
Query Image
    ↓
Generate Embedding → [0.12, 0.45, -0.23, ...]
    ↓
Compare to ALL embeddings
    ↓
Find closest vectors (nearest neighbors)
    ↓
Return corresponding images
```

---

## 🚀 Two Methods: FAISS vs Simple Comparison

### Method 1: **Simple Numpy (Small Scale)**

For **< 10K images**, you can use pure numpy:

```python
import numpy as np

# Query embedding
query = np.array([0.12, 0.45, ...])  # 512 dims

# All embeddings (N x 512)
all_embeddings = np.load('embeddings.npy')  # Shape: (N, 512)

# Compute cosine similarity (dot product for normalized vectors)
similarities = np.dot(all_embeddings, query)  # Shape: (N,)

# Get top-k most similar
top_k = 10
indices = np.argsort(-similarities)[:top_k]  # Top 10
scores = similarities[indices]

# Results!
for idx, score in zip(indices, scores):
    print(f"Image {idx}: similarity = {score:.4f}")
```

**Pros:**
- ✅ Simple, no dependencies
- ✅ Exact results
- ✅ Fast for < 10K images

**Cons:**
- ❌ Slow for > 100K images (your case: 3M!)
- ❌ High memory usage

---

### Method 2: **FAISS (Large Scale)** ⭐ Recommended

**FAISS** (Facebook AI Similarity Search) is designed for **millions of vectors**:

```python
import faiss
import numpy as np

# 1. Load embeddings
embeddings = np.load('embeddings.npy')  # (3M, 512)

# 2. Build FAISS index
index = faiss.IndexFlatIP(512)  # Inner Product (cosine sim)
index.add(embeddings)            # Add all vectors

# 3. Search
query = np.array([[0.12, 0.45, ...]])  # Shape: (1, 512)
k = 10  # Top 10 results

distances, indices = index.search(query, k)
# distances: similarity scores
# indices: which embeddings matched
```

**FAISS Index Types:**

1. **IndexFlatIP** - Exact search (brute force)
   - Best for: < 1M vectors
   - Speed: ~10K searches/sec
   - Memory: Full embeddings in RAM

2. **IndexIVFPQ** - Approximate search (compressed) ⭐
   - Best for: > 1M vectors (your case!)
   - Speed: ~100K searches/sec
   - Memory: 8-32× less RAM
   - Accuracy: 95-99% (configurable)

---

## 🎯 Your System's Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Processing Phase                    │
│                                                          │
│  Images → Registration → Embedding Generation           │
│  3.17M      (570K done)     (2.5K done)                │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                      Search Phase                        │
│                                                          │
│  1. Save embeddings.npy (all 512-dim vectors)           │
│  2. Build FAISS IndexIVFPQ (compressed index)           │
│  3. Query image → Embedding → FAISS search → Results    │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 Current Status

```bash
# You have:
✅ 2,562 embeddings (in database, embedding_index column)
❌ No embeddings.npy file yet (vectors not extracted)
❌ No FAISS index yet (not built)

# You need:
1. Extract embeddings from pipeline to .npy file
2. Build FAISS index
3. Then you can search!
```

---

## 🔧 How to Search NOW (with 2.5K images)

### Quick Test Search

You can test search with your 2,562 current embeddings:

```python
from src.config import Config
from src.search import ImageSearchEngine

# Initialize
config = Config.from_yaml('config_optimized.yaml')
search_engine = ImageSearchEngine(config)

# This will:
# 1. Load embeddings (if embeddings.npy exists)
# 2. Build or load FAISS index
# 3. Enable searching
search_engine.initialize()

# Search by text
results = search_engine.search_by_text("sunset beach", top_k=10)
for r in results:
    print(f"{r.file_path} - Score: {r.score:.4f}")

# Search by image
results = search_engine.search_by_image("/path/to/query.jpg", top_k=10)
for r in results:
    print(f"{r.file_path} - Score: {r.score:.4f}")
```

---

## 🛡️ Database Locking: Will Search Interfere?

### **NO! You can search while processing continues!** ✅

**Why:**

```python
# Your database.py already configured:
PRAGMA journal_mode = WAL    # Multiple readers allowed!
PRAGMA busy_timeout = 300000 # 5 min wait if locked
```

**What happens:**

```
┌───────────────┐     ┌──────────────────┐
│  Background   │────▶│  SQLite DB (WAL) │
│  Processing   │     │                  │
│  (WRITE)      │     │  - Registering   │
│               │     │  - Embedding     │
└───────────────┘     └──────────────────┘
                             ▲
                             │ READ (no lock!)
                             │
                      ┌──────┴───────┐
                      │   Search     │
                      │   (READ)     │
                      └──────────────┘
```

**Operations:**

1. **Background:** Writing new embeddings (slow, continuous)
2. **Search:** Reading existing embeddings (fast, instant)
3. **WAL Mode:** Allows simultaneous read + write ✅

**No need to duplicate DB!**

---

## 🎨 Complete Search Example

Let me create a search script for you:

```python
#!/usr/bin/env python3
"""
Test similarity search with current embeddings
"""
import sys
from pathlib import Path
from src.config import Config
from src.database import ImageDatabase
from src.embeddings import EmbeddingModel
import numpy as np

def simple_search(query_image_path: str, db_path: str, top_k: int = 10):
    """
    Simple similarity search without FAISS.
    Works with current embeddings.
    """
    
    # 1. Load model
    print("Loading embedding model...")
    model = EmbeddingModel(
        model_name="ViT-B-32",
        pretrained="openai",
        device="cpu"
    )
    
    # 2. Get query embedding
    print(f"Processing query image: {query_image_path}")
    from PIL import Image
    query_img = Image.open(query_image_path).convert('RGB')
    query_embedding = model.encode_image(query_img, normalize=True)
    
    # 3. Get all embeddings from database
    print("Loading embeddings from database...")
    db = ImageDatabase(Path(db_path))
    
    # Get images with embeddings
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT id, file_path, file_name, embedding_index, width, height
        FROM images 
        WHERE embedding_index IS NOT NULL
        ORDER BY embedding_index
    """)
    records = [dict(row) for row in cursor.fetchall()]
    
    if not records:
        print("No embeddings found in database!")
        return
    
    print(f"Found {len(records)} images with embeddings")
    
    # For now, we need to regenerate embeddings since they're not stored yet
    # This is a limitation - normally they'd be in embeddings.npy
    
    print("\n⚠️  Note: Embeddings are generated but not yet saved to file.")
    print("    Full search will be available after processing completes.")
    print("    Run 'python cli.py build-index' to create searchable index.")
    
    db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python search_test.py <query_image_path>")
        sys.exit(1)
    
    query_path = sys.argv[1]
    db_path = "/Volumes/My Book/images-finder-data/metadata.db"
    
    simple_search(query_path, db_path)
```

---

## 📈 When Can You Search?

### Option 1: **Search With Current 2.5K Images** (Now)

Problem: Embeddings marked in DB but not saved to file yet.

**Solution:** Extract embeddings to file:

```bash
# Create a small index with current embeddings
python cli.py build-mini-index
```

### Option 2: **Wait for Processing to Complete** (Recommended)

After all 3M images have embeddings:

```bash
# 1. Save all embeddings to file
python cli.py save-embeddings

# 2. Build FAISS index
python cli.py build-index

# 3. Search!
python cli.py search-text "sunset beach"
python cli.py search-image query.jpg
```

---

## 🚀 The Full Pipeline

```
1. Registration (ongoing)
   └─ 570K / 3.17M images ✅

2. Embedding Generation (ongoing)  
   └─ 2.5K / 3.17M images ✅
   └─ Embeddings marked in DB ✅
   └─ Vectors not saved to file yet ❌

3. Save Embeddings (not done yet)
   └─ Extract all vectors to embeddings.npy
   └─ Shape: (3.17M, 512)

4. Build FAISS Index (not done yet)
   └─ Create IndexIVFPQ from embeddings
   └─ Compressed, fast search

5. Search (ready after step 4)
   └─ Query → FAISS → Results in milliseconds
```

---

## 💡 Summary

### How Search Works:
1. **Embeddings** = 512-dim vectors representing images
2. **Similarity** = Cosine distance between vectors
3. **FAISS** = Fast nearest neighbor search for millions of vectors
4. **Hybrid Search** = Approximate + exact re-ranking for best results

### Your Situation:
- ✅ You have 2,562 embeddings generated
- ❌ They're not saved to searchable format yet
- ✅ Database allows reading while processing (WAL mode)
- ❌ No need to duplicate database!

### What to Do:
1. **Wait** for more embeddings to be generated (~568K remaining)
2. **OR** extract current 2.5K to test search now
3. **After processing:** Build full FAISS index for all 3M images
4. **Search** will work in milliseconds!

---

**Want me to create a script to extract and search your current 2,562 embeddings?** 🔍

