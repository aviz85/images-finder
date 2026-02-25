# 🚀 Optimal Embedding Generation Guide

## Overview

This guide explains how to generate embeddings efficiently using maximum system resources while keeping 20% reserved for system stability.

## System Requirements

- **CPU Cores Detected:** Automatically calculated
- **Optimal Workers:** 80% of CPU cores (20% reserved)
- **Example:** 8 cores → 6 workers (80% usage, 20% reserved)

## Quick Start

### 1. Generate Embeddings (Optimal Settings)

```bash
# Auto-calculate optimal workers (80% CPU usage)
./generate_embeddings_optimized.sh

# Or specify number of workers manually
./generate_embeddings_optimized.sh 6
```

### 2. Monitor Progress

```bash
# Check worker logs
tail -f logs/embed_worker_*.log

# Check overall status
./check_status.sh
```

### 3. Merge Worker Embeddings (After All Workers Complete)

```bash
# Merge all worker embedding files into main embeddings.npy
python merge_worker_embeddings.py
```

## How It Works

### Worker Architecture

1. **Parallel Processing:**
   - Each worker processes a different subset of images
   - Uses modulo partitioning: `id % num_workers = worker_id`
   - No overlap between workers

2. **Embedding Storage:**
   - Each worker saves embeddings to temporary file:
     - `embeddings_worker_0.npy`
     - `embeddings_worker_1.npy`
     - etc.
   - Each worker saves embedding indices mapping:
     - `indices_worker_0.npy`
     - `indices_worker_1.npy`
     - etc.

3. **Merging:**
   - After all workers complete, run merge script
   - Combines all worker files into single `embeddings.npy`
   - Preserves embedding_index mapping from database

### Resource Usage

- **CPU:** 80% utilization (20% reserved)
- **RAM:** Shared across workers
- **Disk I/O:** Distributed across workers

## Performance

### Estimated Times (8-core system, 6 workers)

- **Single Worker:** ~4.5 img/sec → **10+ days** for 624K images
- **6 Workers:** ~6-12 img/sec per worker = **~36-72 img/sec total**
- **Time for 624K images:** ~2-4 days (vs 10+ days single worker)

### Speedup

- **6 workers:** ~6× faster than single worker
- **Optimal for 8-core system:** 6 workers (80% CPU usage)

## Troubleshooting

### Workers Not Saving Embeddings?

1. Check logs: `tail -f logs/embed_worker_*.log`
2. Look for "Saving embeddings..." messages
3. Verify worker files exist: `ls -lh data/embeddings_worker_*.npy`

### Need to Stop Workers?

```bash
# Stop all embedding workers
pkill -f "generate_embeddings_parallel"
```

### Resume After Crash?

Workers automatically resume from where they left off:
- Skips images that already have `embedding_index` in database
- Only processes images where `embedding_index IS NULL`

### Merge Fails?

1. Check that all workers completed successfully
2. Verify worker files exist: `ls -lh data/embeddings_worker_*.npy`
3. Check that indices files exist: `ls -lh data/indices_worker_*.npy`

## Next Steps

After generating embeddings:

1. **Merge worker files:**
   ```bash
   python merge_worker_embeddings.py
   ```

2. **Build FAISS index:**
   ```bash
   python cli.py build-index
   ```

3. **Start searching!**
   ```bash
   python cli.py search-text "sky"
   ```

## Files Created

### Worker Files (Temporary)
- `data/embeddings_worker_0.npy` - Embeddings from worker 0
- `data/embeddings_worker_1.npy` - Embeddings from worker 1
- etc.

### Final Files
- `data/embeddings.npy` - Merged embeddings (for search)
- `data/faiss.index` - FAISS search index (after building)

## Notes

- **Safe to interrupt:** Workers save progress incrementally
- **Resumable:** Can restart workers anytime
- **Database safe:** Uses WAL mode for concurrent access
- **Memory efficient:** Processes in batches

