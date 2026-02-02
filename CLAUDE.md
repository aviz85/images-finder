# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Local semantic image search engine for millions of images using OpenCLIP embeddings and FAISS indexing. Privacy-preserving (fully local), supports text-to-image and image-to-image search.

**Scale:** ~3.8M images, 15.7 TB on external drive (`/Volumes/My Book/`)
**System:** Apple M1, 8 cores, 16 GB RAM

## Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run tests
./run_tests.sh                           # All tests with coverage
pytest tests/ -v                         # All tests
pytest tests/test_database.py -v         # Single test file
pytest tests/ -m "not integration"       # Unit tests only
pytest tests/ -m integration             # Integration tests only

# CLI usage
python cli.py --config config_optimized.yaml run-pipeline /path/to/images
python cli.py --config config_optimized.yaml search-text "sunset over mountains" --top-k 20
python cli.py --config config_optimized.yaml search-image query.jpg --top-k 20
python cli.py --config config_optimized.yaml stats

# API server
python server.py                         # Starts on port 8000
uvicorn server:app --host 0.0.0.0 --port 8000

# Processing scripts
./start_everything.sh                    # Start all processing (registration + embeddings + dashboard)
./check_status.sh                        # Check progress (simple)
./run_parallel_embeddings.sh             # Start 2 parallel embedding workers
pkill -f "cli.py" && pkill -f "compute_hashes" && pkill -f "generate_embeddings"  # Stop all

# Backups
./backup_database.sh                     # Safe while workers running
./backup_embeddings.sh
```

## Architecture

```
src/
├── config.py           # Pydantic config from YAML, handles paths/model/FAISS settings
├── database.py         # SQLite with WAL mode, UNIQUE on file_path, batch commits
├── embeddings.py       # OpenCLIP (ViT-B-32) embedding generation + caching
├── embedding_storage.py # Thread-safe incremental .npy storage with filelock
├── faiss_index.py      # FAISS IVF-PQ index, HybridSearch for accuracy
├── pipeline.py         # Batch processing with checkpoints, smart scanner
├── search.py           # ImageSearchEngine: text/image queries, hybrid re-ranking
├── image_processor.py  # PIL loading, perceptual hashing (imagehash)
└── smart_scanner.py    # Skips already-registered images

Entry points:
├── cli.py              # Click CLI: index, embed, build-index, search-text, search-image, run-pipeline
└── server.py           # FastAPI: /search/text, /search/image, /browse, /thumbnail/{id}, /rating/{id}
```

**Data flow:**
1. `pipeline.scan_and_register_images()` → SQLite (file_path UNIQUE)
2. `pipeline.generate_embeddings()` → embeddings.npy (incremental, resumable)
3. `FAISSIndex.build_ivf_pq_index()` → faiss.index
4. `ImageSearchEngine.search_by_text/image()` → hybrid IVF-PQ + exact re-rank

## Key Design Decisions

**SQLite concurrency:** WAL mode + 300s timeout + batch commits (100 images). Max 5 concurrent processes safe.

**Duplicate prevention (3 layers):**
1. Smart scanner filters already-registered paths before processing
2. Pipeline checks `get_image_by_path()` before insert
3. Database UNIQUE constraint on `file_path` with ON CONFLICT UPDATE

**Embedding storage:** Thread-safe incremental saves using `filelock`. Workers partition by `id % num_workers` to avoid overlap. Survives crashes.

**Thumbnails:** Disabled in code due to ExFAT filesystem issues on external drive.

## Configuration

Active config: `config_optimized.yaml`

Key settings:
- `db_path`, `embeddings_path`, `index_path`: Local SSD (backed up to external)
- `model_name`: "ViT-B-32" (512-dim embeddings)
- `embedding_mode`: "local" (CLIP) or "gemini" (API)
- `batch_size`: 32
- `nlist`: 8192, `m_pq`: 64, `nprobe`: 64 (FAISS IVF-PQ params)
- `duplicate_hash_threshold`: 5 (Hamming distance for perceptual hash)

## API Endpoints

```
GET  /health
GET  /stats
GET  /search/text?q=<query>&top_k=20
POST /search/image (multipart file upload)
GET  /browse?page=1&per_page=24&min_rating=3&tag_ids=1,2
GET  /thumbnail/{image_id}
GET  /image/{image_id}/similar
POST /rating/{image_id}
GET  /tags
POST /tags/bulk
```

## Constraints

- Never change database schema without migration (2.4M+ records exist)
- Keep UNIQUE constraint on `file_path`
- Keep thumbnails disabled (filesystem issues)
- Max 5 parallel processes (SQLite lock contention)
- Always use `caffeinate -dims &` for overnight processing
- Database/embeddings on local SSD, images on external drive

## Full Embeddings Database (3.4M images)

**Location:** `/Volumes/My Book/ImageSearch/data/`

| File | Size | Description |
|------|------|-------------|
| `embeddings.npy` | 6.5 GB | 3,387,179 × 512 CLIP embeddings |
| `paths.txt` | 410 MB | Line-by-line file paths (line N = embedding index N) |
| `search.index` | 241 MB | FAISS index |

**⚠️ CRITICAL: Index Alignment Issues**

| Range | Status | Accuracy |
|-------|--------|----------|
| **0-300,000** | ✅ Valid | 100% |
| 300K-350K | ❌ Broken | 25% |
| 350K-3.4M | ❌ Broken | ~0% |

**Only use indices 0-300,000 for reliable results!**

**Usage:**
```python
import numpy as np

# Memory-map for efficiency (don't load all into RAM)
emb = np.load('/Volumes/My Book/ImageSearch/data/embeddings.npy', mmap_mode='r')

# ONLY USE FIRST 300K - rest has index alignment bugs!
valid_emb = emb[:300000]

# Get paths (only first 300K)
with open('/Volumes/My Book/ImageSearch/data/paths.txt') as f:
    paths = [line.strip() for i, line in enumerate(f) if i < 300000]

# Index N in embeddings.npy corresponds to paths[N] (for N < 300000)
```

## Gallery Data (5,331 verified settlement images as of 2026-02-02)

**Location:** `/Users/aviz/images-finder/gallery/`

| Item | Location |
|------|----------|
| Gallery DB | `gallery/gallery.db` (thumbnails, metadata) |
| Client review | `gallery/client-review/` |
| Approved seeds | `gallery/client-review/approved_ids.txt` (125 IDs) |
| Rejected | `gallery/client-review/rejected_ids.txt` (43 IDs) |
| Gallery embeddings | `gallery/client-review/data/gallery_embeddings.npy` (11,724 × 512) |
| Supabase project | `zvmeqrttfldvcvgzftyn` |
| Vercel deploy | `gallery/vercel-deploy/` |

**Gallery composition (CLEAN - only valid range 0-300K):**
| Source | Count | Similarity |
|--------|-------|------------|
| KEEP from valid range | ~380 | CLIP classified |
| Added (high quality) | 957 | >= 0.85 |
| Added (medium quality) | 3,993 | 0.80-0.85 |
| **Total Visible** | **5,331** | |
| Hidden | 25,081 | Duplicates, REMOVE, broken range |
| **Total in DB** | **30,412** | |

## Settlement Image Search (Seeds-based)

**Approach:** Use 125 manually verified settlement images as seeds, compute centroid, find similar images via cosine similarity.

**Seeds location:** `gallery/client-review/approved_ids.txt`

**Search code:**
```python
import numpy as np
import sqlite3
from pathlib import Path
import re

# Load seeds
approved_text = Path('gallery/client-review/approved_ids.txt').read_text()
approved_ids = set(int(x) for x in re.findall(r'\d+', approved_text))

# Load gallery embeddings
gallery_emb = np.load('gallery/client-review/data/gallery_embeddings.npy')
conn = sqlite3.connect('gallery/client-review/data/embeddings.db')
rows = conn.execute("SELECT id, embedding_idx FROM embedding_progress").fetchall()
conn.close()
id_to_idx = {r[0]: r[1] for r in rows}

# Compute centroid
seed_indices = [id_to_idx[aid] for aid in approved_ids if aid in id_to_idx]
centroid = gallery_emb[seed_indices].mean(axis=0)
centroid = centroid / np.linalg.norm(centroid)

# Search in valid range (0-300K)
full_emb = np.load('/Volumes/My Book/ImageSearch/data/embeddings.npy', mmap_mode='r')
valid_emb = np.array(full_emb[:300000])
# ... normalize and compute similarity ...
```

**Thresholds used:**
- >= 0.85: High quality settlement images (957 found)
- 0.80-0.85: Medium quality, borderline (3,993 found)
- < 0.80: Not used (too much noise)

## Settlement Gallery (Vercel)

**Live:** https://village-gallery.vercel.app
**Code:** `gallery/vercel-deploy/`

**Features:**
- 5,012 visible images (319 duplicates auto-hidden)
- Sorted by semantic similarity to "settlement" query
- Left-click = select, Right-click = modal
- Bulk rating, hide, comments
- Find duplicates (perceptual hash), Find similar

**Supabase Backend:**
- Project: `vlmtxakutftzftccizjf`
- Table: `settlement_images`
- Storage: `settlement-images` bucket

**Data linking:**
```
original_path (unique key)
    ↓
gallery.db: semantic_score, rating, is_hidden
    ↓
hex_id = MD5(original_path)[:8]
    ↓
Supabase: semantic_score, rating, comment
```

**Deploy:**
```bash
cd gallery/vercel-deploy && vercel --prod --yes
```

## Embedding Regeneration

**IMPORTANT:** The `embeddings.npy` file is corrupted. The `semantic_score` for settlement images is already saved and does NOT require embeddings.

**Safe regeneration script:** `regenerate_embeddings_safe.py`

### Quick Start
```bash
# Full regeneration (plug and play)
python regenerate_embeddings_safe.py

# Verify existing embeddings without changing
python regenerate_embeddings_safe.py --verify-only

# Resume from where we stopped
python regenerate_embeddings_safe.py --resume

# Retry only failed images
python regenerate_embeddings_safe.py --retry-failed
```

### Safety Guarantees (5 layers)
| # | Mechanism | What it prevents |
|---|-----------|------------------|
| 1 | **Pre-allocate** `np.zeros((max_id+1, 512))` | Array size mismatch |
| 2 | **Direct assignment** `embeddings[id] = vector` | Index shifting |
| 3 | **Verification** at end | Confirms 100% alignment |
| 4 | **Failed log** `embedding_failed.txt` | Can retry only failed |
| 5 | **Backup** before each save | Can restore if corrupted |

### How it works
- Creates array of size `max_id + 1` filled with zeros
- For each image: `embeddings[image_id] = vector` (direct position)
- Failed images stay as zeros, logged to file
- Progress saved every 1000 images with backup
- Final verification confirms all IDs match positions

**Data integrity:**
| Data | Location | Needs Embeddings? |
|------|----------|-------------------|
| Settlement semantic_score | gallery.db, Supabase | No (already computed) |
| Gallery ratings | Supabase | No |
| Duplicate detection | perceptual hash | No |
| New text searches | embeddings.npy | Yes |
| New image searches | embeddings.npy | Yes |

## Lessons Learned (2026-02-02)

1. **Always verify index alignment** before trusting search results
   - Test: compute fresh embedding, compare to stored (should be >0.95 similarity)
   - Found that 300K-3.4M range is completely broken

2. **Index bugs cause phantom results** - high similarity scores but wrong images displayed

3. **mapping_info.json is unreliable** - said 0-350K is valid, actually only 0-300K works

4. **Seed-based search works well** when index is valid - found ~5K new settlement images

5. **Save computed scores separately** - semantic_score stored in DB means regenerating embeddings doesn't lose gallery work
