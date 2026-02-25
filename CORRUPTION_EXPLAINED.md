# What Does "Corrupted" Mean?

## The Corruption Explained

### What Happened:

1. **File Header vs. Actual Data Mismatch:**
   - File header says: "I contain 928,309 embeddings" (1.8GB worth of data)
   - Actual file contains: Only 72,668 embeddings worth of data (142MB)
   - **Result:** File is INCONSISTENT = CORRUPTED

### How NumPy Files Work:

```
.npy file structure:
┌─────────────────────┐
│  File Header        │  ← Says: "This file has shape (928309, 512)"
│  (metadata)         │     "Total size: 1.8GB"
├─────────────────────┤
│  Embedding 0        │
│  Embedding 1        │
│  Embedding 2        │
│  ...                │
│  Embedding 72668    │  ← File ends here!
│  [MISSING DATA]     │  ← Should have 855k more embeddings
└─────────────────────┘
```

### Why This Happened:

From the logs, we can see:

```
2025-12-04 20:18:57,399 - ERROR - Error saving embeddings: 
  [Errno 28] No space left on device: '/Users/aviz/images-finder/data/embeddings.npy'

2025-12-04 20:18:18,357 - ERROR - Error saving embeddings: 
  475146752 requested and 26490848 written
```

**What happened:**
1. Worker tried to save embeddings
2. Created a huge array (928k embeddings = 1.8GB)
3. Started writing to file
4. **Disk ran out of space** (or process was killed)
5. NumPy wrote the file header first (says "928k embeddings")
6. But couldn't write all the data
7. File ends mid-write = CORRUPTED

## Is Incremental Saving the Problem?

### Short Answer: **NO, but the IMPLEMENTATION is flawed**

### The Problem with Current Incremental Saving:

**Current approach (flawed):**
```
1. Load ENTIRE existing file (1.8GB if exists)
2. Create NEW array of size max_index + 1 (could be 1.8GB)
3. Copy old data into new array
4. Insert new embeddings
5. Save ENTIRE array again (write 1.8GB to disk)
```

**Problems:**
- ❌ Tries to allocate 1.8GB in memory
- ❌ Tries to write 1.8GB to disk at once
- ❌ If interrupted, entire file is corrupted
- ❌ No recovery from database
- ❌ Creates huge arrays even for small batches

### What GOOD Incremental Saving Would Look Like:

**Better approach:**
```
1. Use memory-mapped files (write directly to disk)
2. Only allocate space for what's actually needed
3. Append new embeddings without recreating entire file
4. Or: Save batches to separate files, merge periodically
5. Query database to rebuild if file corrupted
```

## Root Causes

1. **Trying to create huge arrays:** When file is corrupted, it creates array based on max embedding_index from database (928k), not what's actually saved

2. **Disk space issues:** Ran out of space while writing 1.8GB file

3. **Atomic write problem:** NumPy's `np.save()` writes header first, then data. If interrupted, header says one thing, data says another

4. **No recovery mechanism:** When file is corrupted, it doesn't query database to rebuild properly

## Is This Caused by Incremental Saving?

**Direct cause:** No - corruption happened because:
- Disk ran out of space
- Process was interrupted mid-write
- File header written but data incomplete

**Indirect cause:** Yes - the incremental saving design makes it worse:
- Tries to save entire array each time (not truly incremental)
- Creates huge arrays based on database max index
- No proper error recovery
- No way to resume from partial writes

## Solution

Need to fix the incremental saving to:
1. Use memory-mapped files (direct disk writes, no huge arrays)
2. Only save what's new (truly incremental)
3. Query database to rebuild if corrupted
4. Handle disk space errors gracefully
5. Verify saves actually completed










