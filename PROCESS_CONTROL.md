# 🎮 Process Control Guide

## How to Stop and Resume Processes

---

## 🛑 **STOP Hash Computation**

### Stop the hash computation process:
```bash
# Kill hash computation processes
pkill -f "compute_hashes"

# Verify they're stopped
ps aux | grep compute_hashes
```

**What happens:**
- ✅ Already computed hashes are SAFE in database
- ✅ Progress is saved
- ✅ Can resume anytime

---

## 🔄 **RESUME Hash Computation**

### Restart hash computation:
```bash
cd /Users/aviz/images-finder
nohup python compute_hashes_simple.py > hash_computation.log 2>&1 &
```

**Or use this shortcut:**
```bash
cd /Users/aviz/images-finder
./restart_hash_computation.sh
```

**What happens:**
- ✅ Continues from where it stopped
- ✅ Only processes images without SHA-256 hash
- ✅ Skips already processed images automatically

---

## 🛑 **STOP Embedding/Registration Processes**

### Stop all image processing:
```bash
# Stop all cli.py processes (registration + embedding)
pkill -f "cli.py"

# Verify they're stopped
ps aux | grep cli.py
```

**What happens:**
- ✅ All registered images SAFE in database
- ✅ Progress saved at last checkpoint (every 500 images)
- ✅ Can resume anytime

---

## 🔄 **RESUME Embedding/Registration**

### Restart parallel processing:
```bash
cd /Users/aviz/images-finder
./run_parallel_optimized.sh
```

**What happens:**
- ✅ Automatically resumes from last checkpoint
- ✅ Skips already registered images
- ✅ Continues embedding generation
- ✅ 3 registration + 2 embedding workers start

---

## 📊 **CHECK What's Running**

### See all active processes:
```bash
# Hash computation
ps aux | grep "[c]ompute_hashes"

# Image processing  
ps aux | grep "[c]li.py"

# Dashboard
ps aux | grep "[l]ive_dashboard"
```

---

## 🖥️ **DASHBOARD Control**

### Stop Dashboard:
```bash
pkill -f "live_dashboard.py"
```

### Start Dashboard:
```bash
cd /Users/aviz/images-finder
python3 live_dashboard.py > dashboard.log 2>&1 &

# Opens on: http://localhost:8888
```

---

## 🎯 **Quick Commands**

### Stop Everything:
```bash
pkill -f "compute_hashes"
pkill -f "cli.py"
pkill -f "live_dashboard"
```

### Start Everything:
```bash
cd /Users/aviz/images-finder

# Start hash computation
nohup python compute_hashes_simple.py > hash_computation.log 2>&1 &

# Start image processing
./run_parallel_optimized.sh

# Start dashboard
python3 live_dashboard.py > dashboard.log 2>&1 &
```

### Check Everything:
```bash
cd /Users/aviz/images-finder
./check_parallel_progress.sh
./check_sha256_duplicates.sh
```

---

## ⚠️ **Important Notes**

### Safe to Stop:
✅ **Hash computation** - Progress saved, resumes automatically  
✅ **Registration** - Database commits after each image  
✅ **Embeddings** - Checkpoints every 500 images  
✅ **Dashboard** - Just viewing data, no processing

### What's Lost if Stopped:
⚠️ **Embedding vectors** - In-memory until saved (every 500 images)  
⚠️ **Current batch** - Last <500 embeddings might need regeneration  
✅ **Everything else** - SAFE!

### Best Practice:
- Let processes run to completion when possible
- If must stop: Wait for checkpoint (every 500 images)
- Monitor logs to see checkpoint timing
- Dashboard shows real-time progress

---

## 📝 **Process Status Files**

```
hash_computation.log       - Hash computation progress
logs/register_D.log        - Registration process D
logs/register_E.log        - Registration process E  
logs/register_F.log        - Registration process F
logs/embed_1.log           - Embedding worker 1
logs/embed_2.log           - Embedding worker 2
dashboard.log              - Dashboard server log
```

---

## 🔍 **Troubleshooting**

### If processes won't stop:
```bash
# Force kill
pkill -9 -f "compute_hashes"
pkill -9 -f "cli.py"
```

### If can't resume:
```bash
# Check database isn't locked
lsof "/Volumes/My Book/images-finder-data/metadata.db"

# Wait 10 seconds and try again
sleep 10
./run_parallel_optimized.sh
```

### If dashboard won't start:
```bash
# Check if port 8888 is in use
lsof -i :8888

# Kill whatever's using it
kill $(lsof -t -i :8888)

# Restart
python3 live_dashboard.py > dashboard.log 2>&1 &
```

---

**Summary: Everything is resumable and safe to stop/start! ✅**



