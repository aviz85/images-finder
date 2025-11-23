# 🤖 Claude AI Assistant - Project Context

**Last Updated:** November 23, 2025  
**Purpose:** Context document for AI assistants working on this project

---

## 📋 Project Overview

**Project:** Local Semantic Image Search Engine  
**Scale:** 3.17 million images across 15.7 TB  
**Location:** External drive `/Volumes/My Book/`  
**System:** Apple M1, 8 cores, 16 GB RAM, USB 2.0 connection

### Current Status (as of Nov 23, 2025 - 3:35 PM)
- **Registered:** 571,464 images (18.0%)
- **SHA-256 Hashes:** Processing in background
- **Embeddings:** 2,562 (0.4% of registered)
- **Processing Rate:** ~16 images/sec (registration)
- **Processing Time:** ~2-3 days remaining
- **Status:** ✅ All processes running + caffeinate active
- **Search Demo:** ✅ Working! (text & image similarity search)

---

## 🗂️ Project Structure

### **Core Application (`src/`)**
- `config.py` - Configuration management
- `database.py` - SQLite database with WAL mode, UNIQUE constraints
- `pipeline.py` - Batch processing with smart scanner, resume support
- `embeddings.py` - OpenCLIP (ViT-B-32) embedding generation
- `faiss_index.py` - FAISS IVF-PQ indexing for search
- `image_processor.py` - Image processing, hashing (thumbnails disabled)
- `search.py` - Text-to-image and image-to-image search
- `smart_scanner.py` - Database-backed scanner to avoid re-scanning

### **Entry Points**
- `cli.py` - Command-line interface (Click framework)
- `server.py` - FastAPI HTTP server
- `live_dashboard.py` - Real-time dashboard on port 8888

---

## 🚀 Active Scripts (Use These)

### **Main Processing:**
1. **`start_everything.sh`** ⭐
   - Entry point for all processing
   - Starts: hash computation + parallel processing + dashboard
   - Uses: `config_optimized.yaml`

2. **`run_parallel_optimized.sh`**
   - Called by start_everything.sh
   - Runs 5 parallel processes (3 registration + 2 embedding)
   - Optimal for M1 + SQLite concurrency

### **Monitoring:**
3. **`check_status.sh`** ⭐
   - Simple, reliable status checker (use this one!)
   - Shows: active processes, database stats, disk space, dashboard status

4. **`check_parallel_progress.sh`**
   - Comprehensive progress monitoring (requires PID files)
   - Alternative to check_status.sh

5. **`check_sha256_duplicates.sh`**
   - SHA-256 duplicate detection progress and statistics

6. **`show_duplicates.sh`**
   - Perceptual hash duplicate statistics

### **Utilities:**
6. **`restart_hash_computation.sh`**
   - Restarts `compute_hashes_simple.py` in background

7. **`restart_embeddings.sh`**
   - Restarts 2 embedding workers

8. **`open_duplicate_group.sh`**
   - Opens specific duplicate group in Preview

---

## 🗑️ Recently Deleted Scripts (Nov 22, 2025)

### Why We Cleaned Up:
User wanted to avoid accidentally running wrong scripts when resuming after moving computer or shutting down.

### Deleted Files:
**Pipeline Scripts (3):**
- `process_all_overnight.sh` - Sequential version, slower
- `process_external_drive.sh` - Interactive version, outdated
- `run_pipeline_parallel.sh` - 6-process version (too many, caused DB locks)

**Monitoring Scripts (2):**
- `monitor_progress.sh` - Duplicate functionality
- `list_duplicates.sh` - File export version

**Note:** `check_status.sh` was later recreated (Nov 22) as a simpler alternative to `check_parallel_progress.sh`

**Config Files (2):**
- `config_external.yaml` - Duplicate of config_optimized.yaml
- `config_benchmark.yaml` - Testing only

---

## ⚙️ Configuration

### **Active Config: `config_optimized.yaml`**
```yaml
Database: /Volumes/My Book/images-finder-data/metadata.db
Embeddings: /Volumes/My Book/images-finder-data/embeddings.npy
Index: /Volumes/My Book/images-finder-data/faiss.index
Model: ViT-B-32 (OpenAI CLIP)
Device: CPU (M1)
Batch Size: 32
Thumbnails: DISABLED (filesystem issues + performance)
Checkpoints: Every 500 images
```

### Other Configs:
- `config.example.yaml` - Template for new users
- `config.yaml` - Local development (not used for production)

---

## 🔐 Duplicate Prevention Architecture

### **Three-Layer Protection:**

**Layer 1: Smart Scanner**
- Queries database for all registered `file_path` entries
- Filters them out before processing starts
- Located: `src/smart_scanner.py`

**Layer 2: Pipeline Check**
```python
# src/pipeline.py line 88-92
existing = self.db.get_image_by_path(str(file_path))
if existing:
    skipped += 1
    continue
```

**Layer 3: Database UNIQUE Constraint**
```sql
CREATE TABLE images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,  -- Enforces uniqueness
    ...
)
```

**Plus: ON CONFLICT UPDATE**
```python
# src/database.py line 220
ON CONFLICT(file_path) DO UPDATE SET
    file_size=excluded.file_size,
    ...
```

### Result:
- ✅ **Impossible to create duplicate entries**
- ✅ Safe to stop/start anytime
- ✅ Safe to run different scripts (all use same DB)
- ✅ Safe to move computer and resume

---

## 🔄 Resume/Restart Workflow

### User Can:
1. Stop processing anytime (Ctrl+C, shutdown, unplug drive)
2. Move computer
3. Plug drive back in
4. Run `./start_everything.sh`
5. Processing continues exactly where it left off

### How It Works:
- Database tracks all registered images
- Processing status table tracks checkpoints
- Smart scanner excludes already-registered images
- Embedding generation only processes unprocessed images
- Batch commits every 100 images (safe if process crashes)

---

## 🐛 Known Issues & Solutions

### **Issue 1: Thumbnail Generation**
- **Problem:** Filesystem errors on external NTFS/exFAT drive
- **Solution:** ✅ DISABLED in code (line 101-103 of `src/pipeline.py`)
- **Status:** Working as intended, no thumbnails generated

### **Issue 2: SQLite Database Locks**
- **Problem:** 6+ concurrent processes cause "database is locked" errors
- **Solution:** ✅ Reduced to 5 processes, enabled WAL mode, batch commits
- **Status:** Stable with current configuration

### **Issue 3: USB 2.0 Bottleneck**
- **Problem:** Limited to ~40 MB/s, slows embedding generation
- **Solution:** ⏳ Recommend USB 3.0 cable ($10-20, 3-4x faster)
- **Status:** Working but slow, can upgrade cable for 2x speedup

### **Issue 4: Scanning Takes Time**
- **Problem:** Initial directory scan takes 30-60 minutes
- **Solution:** ✅ Smart scanner caches results (implemented)
- **Status:** First scan slow, subsequent scans fast

---

## 📊 Database Schema (Key Tables)

### **`images` Table**
```sql
- id (PRIMARY KEY)
- file_path (UNIQUE NOT NULL)  -- Full path, enforces no duplicates
- file_name
- file_size, width, height, format
- thumbnail_path (always NULL, disabled)
- embedding_index (position in embeddings.npy)
- perceptual_hash (phash for visual duplicate detection)
- sha256_hash (for exact duplicate detection)
- is_duplicate, duplicate_of (duplicate tracking)
- processed_at, created_at, updated_at
```

### **`processing_status` Table**
- Tracks checkpoint state for resumable jobs
- job_name (UNIQUE)
- total_files, processed_files, failed_files
- last_checkpoint timestamp

### **`failed_images` Table**
- Logs images that failed to process
- file_path, error_message, failed_at

---

## 🔧 Performance Characteristics

### Current Setup:
- **Registration:** 6-8 img/s (3 parallel processes)
- **Embedding:** 2-3 img/s per worker (2 workers, USB 2.0 limited)
- **Total:** ~5-6 img/s combined
- **Time:** 6-7 days for 3.17M images

### With USB 3.0:
- **Registration:** 15-20 img/s
- **Embedding:** 5-7 img/s per worker
- **Total:** 10-12 img/s combined
- **Time:** 3-4 days for 3.17M images

### Process Layout:
```
Process 1: Register Dir D    ~10% CPU (I/O bound)
Process 2: Register Dir E    ~10% CPU (I/O bound)
Process 3: Register Dir F    ~10% CPU (I/O bound)
Process 4: Embed Worker 1    ~80% CPU (CPU bound)
Process 5: Embed Worker 2    ~80% CPU (CPU bound)
---------------------------------------------------
Total:     ~220% CPU (~27% of 8 cores)
           ~10 GB RAM
           SQLite handles 5 connections well
```

---

## 🎯 User Workflow

### Daily Workflow:
```bash
# Start/Resume
cd /Users/aviz/images-finder
./start_everything.sh

# Check Progress (simple & reliable)
./check_status.sh

# Check Progress (detailed)
./check_parallel_progress.sh

# Dashboard
open http://localhost:8888

# Stop (when needed)
pkill -f "cli.py"
pkill -f "compute_hashes"
pkill -f "live_dashboard"
```

### User's Main Concern:
**"I move my computer a lot and restart processing. Will I create duplicates or inconsistent data?"**

**Answer:** No. All scripts use the same database with UNIQUE constraints. Safe to stop/start anytime with any script.

---

## 📝 Important Files for Context

### **User Guides:**
- `WHICH_SCRIPTS_TO_USE.md` ⭐ - Main reference guide
- `RESUME_AFTER_SHUTDOWN.md` - Resume instructions
- `README.md` - Project overview
- `QUICKSTART.md` - Getting started guide

### **Technical Reports:**
- `OPTIMIZATION_COMPLETE_REPORT.md` - Performance analysis
- `WAL_MODE_FIX.md` - Database concurrency solution
- `EMBEDDING_FIX_COMPLETE.md` - Embedding process fixes
- `SHA256_VS_PERCEPTUAL_HASH.md` - Duplicate detection approaches

### **Status/Progress:**
- `STATUS_SUMMARY.md` - Processing status snapshot
- `PROJECT_SUMMARY.md` - Technical project summary

---

## 💡 Key Insights for AI Assistants

### Architecture Decisions:
1. **SQLite with WAL Mode** - Enables 5 concurrent writers without major conflicts
2. **Batch Commits (100 images)** - 100x fewer lock requests, much faster
3. **Smart Scanner** - Eliminates redundant directory scanning
4. **Thumbnails Disabled** - Filesystem issues + 35% performance drain
5. **5 Processes (not 6)** - SQLite sweet spot, avoids lock contention

### Code Patterns:
- All database writes use `_commit_with_retry()` (exponential backoff)
- All image additions use `ON CONFLICT(file_path) DO UPDATE`
- All pipelines check `get_image_by_path()` before adding
- All embedding generation uses `get_unprocessed_images()`

### Testing Changes:
- Database is on external drive (backup important!)
- Test changes with small sample first
- Monitor `check_parallel_progress.sh` for issues
- Check logs in `logs/` directory

---

## 🚨 What NOT to Do

### Don't:
- ❌ Change database schema without migration (existing data!)
- ❌ Remove UNIQUE constraint on file_path
- ❌ Re-enable thumbnail generation (filesystem issues)
- ❌ Increase to 6+ parallel processes (database locks)
- ❌ Hardcode paths (use config files)
- ❌ Add new scripts without documenting them

### Do:
- ✅ Test with small datasets first
- ✅ Keep duplicate protection layers
- ✅ Document new scripts in `WHICH_SCRIPTS_TO_USE.md`
- ✅ Use batch commits for database writes
- ✅ Check existing progress before suggesting re-processing

---

## 🔮 Future Enhancements (Not Yet Implemented)

- [ ] USB 3.0 cable upgrade (hardware, user's choice)
- [ ] Web UI for search (server.py exists but not actively used)
- [ ] Automatic duplicate removal workflow
- [ ] Multi-language search support (Hebrew + English)
- [ ] Image clustering and organization
- [ ] Real-time folder watching
- [ ] Distributed processing across multiple machines

---

## 📞 Quick Reference Commands

```bash
# Main workflow
./start_everything.sh                    # Start/resume everything
./check_status.sh                        # Check progress (simple & reliable)
./check_parallel_progress.sh             # Check progress (detailed)
open http://localhost:8888               # Dashboard

# Individual components
./restart_hash_computation.sh            # Restart hashing only
./restart_embeddings.sh                  # Restart embeddings only

# Duplicates
./check_sha256_duplicates.sh             # SHA-256 stats
./show_duplicates.sh                     # Perceptual hash stats
./open_duplicate_group.sh 1              # View group in Preview

# Database queries
sqlite3 "/Volumes/My Book/images-finder-data/metadata.db" \
  "SELECT COUNT(*) FROM images"

# Stop everything
pkill -f "cli.py" && pkill -f "compute_hashes" && pkill -f "live_dashboard"

# Test installation
python test_installation.py

# Run tests
./run_tests.sh
```

---

## 🔄 Stop & Resume Instructions

### **How to Stop Everything Safely:**

```bash
# Stop all processing (safe anytime)
pkill -f "cli.py" && pkill -f "compute_hashes" && pkill -f "live_dashboard"

# Or use keyboard: Ctrl+C in terminal running the processes
```

**✅ ALWAYS SAFE TO STOP:**
- Database commits every 100 images
- WAL mode ensures consistency
- Smart scanner tracks progress
- NO data will be lost!

### **How to Resume After Stopping:**

```bash
# Resume everything
./start_everything.sh

# Or step by step:
./restart_hash_computation.sh    # Hashing only
./run_parallel_optimized.sh      # Registration + embeddings
python3 live_dashboard.py &      # Dashboard
```

**What happens on resume:**
- ✅ Skips already-registered images (smart scanner)
- ✅ Skips images with hashes
- ✅ Skips images with embeddings
- ✅ Continues exactly where you left off
- ✅ No duplicates possible (UNIQUE constraints)

---

## ⚡ Caffeinate - MUST USE!

**CRITICAL:** Always run caffeinate when processing overnight or away from computer!

### **Start Caffeinate:**
```bash
# Prevent display sleep, system sleep, disk sleep, and idle
caffeinate -dims &

# Verify it's running
ps aux | grep caffeinate | grep -v grep
```

### **Why It's Essential:**
- ❌ Without: Mac sleeps → USB disconnects → processing stops → data corruption risk
- ✅ With: Mac stays awake → processing continues → safe completion

### **Caffeinate is Running If You See:**
```bash
aviz    50735   0.0  0.0  caffeinate -dims
```

### **Stop Caffeinate:**
```bash
# Find PID
ps aux | grep caffeinate | grep -v grep

# Kill it
kill <PID>
```

**⚠️  ALWAYS start caffeinate before leaving computer unattended!**

---

## 🔍 Search Demo - Test Similarity Search

### **Text-to-Image Search:**
```bash
# Search by description
python search_demo.py text "beach sunset ocean" -k 5

# With Preview (opens results)
python search_demo.py text "landscape mountains" -k 5 --open
```

### **Image-to-Image Search:**
```bash
# Find similar images
python search_demo.py image "test_images/blue_01.jpg" -k 5

# Open in Preview
python search_demo.py image "/path/to/query.jpg" -k 10 --open
```

### **What It Does:**
- ✅ Works with current 2,562 embeddings
- ✅ Shows similarity scores (0-1, higher = more similar)
- ✅ Regenerates embeddings on-the-fly (slow, for demo)
- ✅ Opens results in Preview app (--open flag)
- ⚠️  Full FAISS search available after processing completes

### **Scores Meaning:**
- **0.6-1.0:** Very similar (image search)
- **0.3-0.6:** Moderately similar
- **0.1-0.3:** Loosely related (text search)
- **< 0.1:** Different content

### **After Processing Completes:**
```bash
python cli.py save-embeddings   # Extract all embeddings
python cli.py build-index       # Build FAISS index
python cli.py search-text "sunset beach"
python cli.py search-image query.jpg
# → Search 3M images in milliseconds!
```

---

## 📊 Current Status (Nov 23, 2025)

### **Progress:**
- **Registered:** 571,464 images (18.0%)
- **With Embeddings:** 2,562 (0.4%)
- **Failed:** 761 images
- **Processing Rate:** ~16 images/sec (registration)

### **Running Processes:**
```bash
ps aux | grep -E "(cli.py|compute_hashes|live_dashboard)" | grep -v grep

# Should see:
# - 3× registration workers (D, E, F)
# - 1× hash computation
# - 1× dashboard
# - 1× caffeinate (MUST!)
```

### **Timeline:**
- **Registration:** ~1.8 days remaining
- **Embeddings:** ~10 hours (if parallel) or ~31 hours (single)
- **Total:** ~2-3 days to completion

### **Database Safety:**
- ✅ WAL mode (multiple readers + one writer)
- ✅ UNIQUE constraints (no duplicates possible)
- ✅ 300-second timeout (no deadlocks)
- ✅ Batch commits (every 100 images)

---

## 🎯 Quick Commands Reference

```bash
# Status
./check_parallel_progress.sh
./check_sha256_duplicates.sh
open http://localhost:8888

# Stop & Resume
pkill -f "cli.py" && pkill -f "compute_hashes"
./start_everything.sh

# Caffeinate (CRITICAL!)
caffeinate -dims &
ps aux | grep caffeinate

# Search Demo
python search_demo.py text "beach sunset" -k 5 --open
python search_demo.py image "path/to/image.jpg" -k 10 --open

# Database Queries
sqlite3 "/Volumes/My Book/images-finder-data/metadata.db" \
  "SELECT COUNT(*), COUNT(embedding_index), COUNT(sha256_hash) FROM images"

# Logs
tail -f logs/process_D.log
tail -f hash_computation.log
tail -f dashboard.log
```

---

**Remember:** 
- 🛡️ User's priority is **NO DUPLICATES** and **SAFE RESUME** - both guaranteed!
- ⚡ **ALWAYS use caffeinate** when leaving computer unattended!
- 🔍 **Search demo** shows similarity search is working perfectly!

