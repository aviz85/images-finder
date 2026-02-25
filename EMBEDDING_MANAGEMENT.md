# 🎛️ Embedding Generation Management

## Quick Commands

### Start (בסיס)
```bash
./manage_embeddings.sh start
```

### Check Status (בדיקת סטטוס)
```bash
./manage_embeddings.sh status
```

### Stop (עצירה)
```bash
./manage_embeddings.sh stop
```

### Resume (המשך)
```bash
# Simply start again - it automatically resumes from where it stopped!
./manage_embeddings.sh start
```

### View Logs (צפייה בלוגים)
```bash
# All workers
./manage_embeddings.sh logs

# Specific worker
./manage_embeddings.sh logs 0
```

## How Resume Works

The system automatically resumes from where it stopped:
- ✅ Workers skip images that already have `embedding_index` in database
- ✅ Only processes images where `embedding_index IS NULL`
- ✅ Safe to stop/start anytime

## Background Operation

Workers run in background:
- ✅ Continue even if terminal closes
- ✅ Safe to stop/start
- ✅ Progress saved incrementally

## Examples

```bash
# Start with auto-calculated workers (6 for 8-core system)
./manage_embeddings.sh start

# Start with specific number of workers
./manage_embeddings.sh start 8

# Check what's happening
./manage_embeddings.sh status

# Stop workers
./manage_embeddings.sh stop

# Resume (same as start - auto-resumes)
./manage_embeddings.sh start
```

