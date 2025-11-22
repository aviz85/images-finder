# ✅ Script Reference Guide

**Last Updated:** November 22, 2025  
**Cleanup:** Removed 8 duplicate/outdated scripts and configs

---

## 🚀 Main Scripts - USE THESE

### **To Start/Resume Processing:**
```bash
./start_everything.sh
```
**What it does:**
- Starts SHA-256 hash computation
- Starts parallel image processing (5 processes: 3 registration + 2 embedding)
- Starts live dashboard
- Uses `config_optimized.yaml`

**Use this every time you resume after shutdown!**

---

### **To Monitor Progress:**
```bash
./check_parallel_progress.sh
```
**Shows:**
- Process status (PID, CPU, memory, runtime)
- Database statistics (registered, with embeddings, failed)
- System load and disk space
- Recent activity from each process

---

### **To Check Duplicates:**
```bash
# SHA-256 duplicates (exact copies)
./check_sha256_duplicates.sh

# Perceptual duplicates (visually similar)
./show_duplicates.sh

# View a specific duplicate group in Preview
./open_duplicate_group.sh 1
```

---

### **To Restart Individual Components:**
```bash
# Restart SHA-256 hash computation
./restart_hash_computation.sh

# Restart embedding workers only
./restart_embeddings.sh
```

---

## ⚙️ Configuration

**Active Config:** `config_optimized.yaml`

**Settings:**
- Database: `/Volumes/My Book/images-finder-data/metadata.db`
- Thumbnails: Disabled (performance optimization)
- Model: ViT-B-32 (OpenAI CLIP)
- Processes: 5 parallel (optimized for M1 + SQLite)
- Checkpoints: Every 500 images

---

## 📊 Dashboard

**While processing runs:**
```bash
open http://localhost:8888
```

Shows real-time:
- Progress counters
- Processing speed
- SHA-256 duplicate statistics
- System status

---

## 🗑️ Deleted Scripts (Nov 22, 2025)

These were removed to prevent confusion:

**Older Pipeline Scripts:**
- ❌ `process_all_overnight.sh` - Sequential version
- ❌ `process_external_drive.sh` - Interactive version  
- ❌ `run_pipeline_parallel.sh` - 6-process version (too many)

**Older Monitoring:**
- ❌ `check_status.sh` - Basic monitoring
- ❌ `monitor_progress.sh` - Duplicate functionality
- ❌ `list_duplicates.sh` - File export version

**Duplicate Configs:**
- ❌ `config_external.yaml` - Same as optimized
- ❌ `config_benchmark.yaml` - Testing only

---

## 💡 Common Tasks

### Resume After Shutdown
```bash
cd /Users/aviz/images-finder
./start_everything.sh
```

### Check If Still Running
```bash
./check_parallel_progress.sh
```

### Stop Everything
```bash
pkill -f "cli.py"
pkill -f "compute_hashes"
pkill -f "live_dashboard"
```

---

## 🛡️ Important Notes

### No Duplicates Will Be Created
- Database has UNIQUE constraint on `file_path`
- Smart scanner filters already-registered images
- Pipeline double-checks before adding
- **Safe to stop/start anytime!**

### Resumability
- All progress saved in database
- Can stop anytime (Ctrl+C, shutdown, unplug drive)
- Resume from exactly where you left off
- No data loss, no re-processing

### Performance
- Current: ~5-6 img/s with USB 2.0
- With USB 3.0: ~10-12 img/s (2x faster)
- Completion: ~6-7 days (current), ~3-4 days (with USB 3.0)

---

**Remember: Always use `./start_everything.sh` to resume!** 🎯

