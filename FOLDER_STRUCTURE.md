# Folder Structure & Data Flow

## 📁 Your Images (Original Files)

**Location:** Anywhere on your computer!

```
Your Computer
│
├── /Users/aviz/Pictures/             ← Your original images live here!
│   ├── Vacation/
│   │   ├── beach1.jpg
│   │   ├── beach2.jpg
│   │   └── sunset.jpg
│   ├── Family/
│   │   ├── birthday.jpg
│   │   └── wedding.jpg
│   └── Work/
│       └── screenshots/
│           ├── pic1.png
│           └── pic2.png
│
└── /Users/aviz/images-finder/        ← This project
    ├── data/                         ← Generated files (safe to delete)
    │   ├── metadata.db
    │   ├── embeddings.npy
    │   ├── faiss.index
    │   └── thumbnails/
    ├── src/
    ├── static/
    └── ...
```

**Important:**
- ✅ Your original images stay where they are
- ✅ They are NEVER moved or modified
- ✅ The system only reads them to create thumbnails and embeddings

---

## 🔄 Complete Workflow

### Phase 1: Setup (One Time)

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Install                                             │
│ $ ./setup.sh                                                │
│                                                              │
│ Creates:                                                     │
│ ├── venv/           (Python virtual environment)            │
│ └── data/           (Empty data directory)                  │
└─────────────────────────────────────────────────────────────┘
```

### Phase 2: Indexing Your Images

```
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Index Images                                        │
│ $ python cli.py run-pipeline /Users/aviz/Pictures/         │
│                                                              │
│ What happens:                                               │
│                                                              │
│ Your Images          →  Processing  →  Generated Data       │
│ ┌─────────┐              ┌─────┐       ┌──────────┐        │
│ │ *.jpg   │  ──scan──→   │ 1/4 │       │ Database │        │
│ │ *.png   │              └─────┘       └──────────┘        │
│ └─────────┘                                                 │
│     ↓                     ┌─────┐       ┌──────────┐        │
│     └────thumbnails───→   │ 2/4 │       │Thumbnails│        │
│                           └─────┘       └──────────┘        │
│                                                              │
│                           ┌─────┐       ┌──────────┐        │
│     ┌────AI model────→    │ 3/4 │       │Embeddings│        │
│     │                     └─────┘       └──────────┘        │
│     │                                                        │
│     │                     ┌─────┐       ┌──────────┐        │
│     └────build index──→   │ 4/4 │       │  Index   │        │
│                           └─────┘       └──────────┘        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Phase 3: Using the System

```
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Start Server                                        │
│ $ python server.py                                          │
│                                                              │
│ Server loads:                                               │
│ ├── Database    (metadata.db)                               │
│ ├── Embeddings  (embeddings.npy)                            │
│ └── Index       (faiss.index)                               │
│                                                              │
│ Open browser: http://localhost:8000/ui                      │
│                                                              │
│ ┌───────────────────────────────────────────────┐           │
│ │  🖼️ Image Explorer                            │           │
│ │  [Search: sunset beach ____________] 🔍       │           │
│ │  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐         │           │
│ │  │img1│ │img2│ │img3│ │img4│ │img5│         │           │
│ │  └────┘ └────┘ └────┘ └────┘ └────┘         │           │
│ └───────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Storage

### What Gets Created

```
images-finder/
└── data/                           ← All generated files here
    ├── metadata.db                 ← SQLite database
    │   └── Tables:
    │       ├── images             (file paths, sizes, dimensions)
    │       ├── ratings            (your star ratings)
    │       └── processing_status  (job tracking)
    │
    ├── embeddings.npy             ← AI vectors (4.5KB per image)
    │
    ├── faiss.index                ← Search index (~300 bytes per image)
    │
    └── thumbnails/                ← Small previews (~50KB per image)
        ├── a1b2c3d4e5f6.jpg
        ├── 1a2b3c4d5e6f.jpg
        └── ...
```

### Size Examples

| Images | Database | Embeddings | Index | Thumbnails | Total |
|--------|----------|------------|-------|------------|-------|
| 100    | 100 KB   | 450 KB     | 30 KB | 5 MB       | ~6 MB |
| 1,000  | 1 MB     | 4.5 MB     | 300 KB| 50 MB      | ~56 MB |
| 10,000 | 10 MB    | 45 MB      | 3 MB  | 500 MB     | ~560 MB |
| 100,000| 100 MB   | 450 MB     | 30 MB | 5 GB       | ~5.6 GB |

---

## 🔍 How Search Works

```
┌─────────────────────────────────────────────────────────────┐
│ User Types: "sunset on beach"                              │
│      ↓                                                       │
│ ┌─────────────────────────────────────────────────┐         │
│ │ 1. Text → AI Model → Vector                     │         │
│ │    "sunset beach" → [0.23, -0.45, 0.67, ...]   │         │
│ └─────────────────────────────────────────────────┘         │
│      ↓                                                       │
│ ┌─────────────────────────────────────────────────┐         │
│ │ 2. Search FAISS Index                           │         │
│ │    Find vectors similar to query vector         │         │
│ │    (This is VERY fast - milliseconds!)          │         │
│ └─────────────────────────────────────────────────┘         │
│      ↓                                                       │
│ ┌─────────────────────────────────────────────────┐         │
│ │ 3. Get Top Matches                              │         │
│ │    [image_45.jpg: 0.92 match]                   │         │
│ │    [image_12.jpg: 0.89 match]                   │         │
│ │    [image_67.jpg: 0.85 match]                   │         │
│ └─────────────────────────────────────────────────┘         │
│      ↓                                                       │
│ ┌─────────────────────────────────────────────────┐         │
│ │ 4. Load Thumbnails & Display                    │         │
│ │    Show results in grid with scores             │         │
│ └─────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Example: Full Process

Let's index your vacation photos!

### Your Files (Before)

```
/Users/aviz/Pictures/Vacation2024/
├── Day1/
│   ├── IMG_001.jpg    (beach photo, 3.2 MB)
│   ├── IMG_002.jpg    (sunset photo, 2.8 MB)
│   └── IMG_003.jpg    (food photo, 2.1 MB)
├── Day2/
│   ├── IMG_004.jpg    (hiking photo, 3.5 MB)
│   └── IMG_005.jpg    (mountain photo, 3.0 MB)
└── Day3/
    ├── IMG_006.jpg    (city photo, 2.9 MB)
    └── IMG_007.jpg    (night photo, 2.4 MB)

Total: 7 images, ~20 MB
```

### Run Indexing

```bash
cd /Users/aviz/images-finder
source venv/bin/activate
python cli.py run-pipeline /Users/aviz/Pictures/Vacation2024
```

### System Creates (After)

```
/Users/aviz/images-finder/data/
├── metadata.db                    (7 KB - contains info about 7 images)
├── embeddings.npy                 (31.5 KB - 7 × 4.5KB)
├── faiss.index                    (2 KB - tiny search index)
└── thumbnails/                    (350 KB - 7 × 50KB)
    ├── a1b2c3d4.jpg              (thumbnail of IMG_001.jpg)
    ├── e5f6g7h8.jpg              (thumbnail of IMG_002.jpg)
    ├── i9j0k1l2.jpg              (thumbnail of IMG_003.jpg)
    ├── m3n4o5p6.jpg              (thumbnail of IMG_004.jpg)
    ├── q7r8s9t0.jpg              (thumbnail of IMG_005.jpg)
    ├── u1v2w3x4.jpg              (thumbnail of IMG_006.jpg)
    └── y5z6a7b8.jpg              (thumbnail of IMG_007.jpg)

Total generated: ~385 KB
```

**Original images:** Untouched in `/Users/aviz/Pictures/Vacation2024/`

---

## 📝 Database Schema

What's stored in `metadata.db`:

```sql
-- Images table
CREATE TABLE images (
    id INTEGER PRIMARY KEY,
    file_path TEXT,              -- "/Users/aviz/Pictures/.../IMG_001.jpg"
    file_name TEXT,              -- "IMG_001.jpg"
    file_size INTEGER,           -- 3355443 (bytes)
    width INTEGER,               -- 3024
    height INTEGER,              -- 4032
    format TEXT,                 -- "JPEG"
    thumbnail_path TEXT,         -- "data/thumbnails/a1b2c3d4.jpg"
    embedding_index INTEGER,     -- 0 (position in embeddings array)
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Ratings table
CREATE TABLE ratings (
    id INTEGER PRIMARY KEY,
    image_id INTEGER,            -- Links to images.id
    rating INTEGER,              -- 1-5 stars
    comment TEXT,                -- Optional comment
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

---

## 🗑️ Clean Up / Start Over

Want to re-index everything?

```bash
# Delete all generated data (safe - originals untouched!)
rm -rf data/

# Re-run indexing
python cli.py run-pipeline /path/to/images
```

---

## 📂 Multiple Image Folders

You can index multiple folders:

```bash
# Index family photos
python cli.py run-pipeline /Users/aviz/Pictures/Family

# Index work screenshots
python cli.py run-pipeline /Users/aviz/Documents/Screenshots

# Index vacation photos
python cli.py run-pipeline /Volumes/USB/Vacations

# All images searchable together!
```

---

## 🔒 Privacy & Security

### What Stays Local

- ✅ All your images
- ✅ All thumbnails
- ✅ All embeddings
- ✅ All ratings and comments
- ✅ Search index
- ✅ Database

### What's Downloaded

- ⬇️ AI Model (~350 MB, one-time)
  - Source: HuggingFace (open source)
  - Stored: `~/.cache/open_clip/`
  - Used for: Converting images/text to vectors

### What Goes to Internet

- ❌ Nothing! (after initial model download)
- ❌ Your images never leave your computer
- ❌ Your searches are completely private
- ❌ No analytics, no tracking, no cloud

---

## 💡 Pro Tips

### Organize by Folder

Keep your images organized in folders:
```
/Pictures/
├── 2023/
├── 2024/
├── Work/
├── Personal/
└── Archive/
```

Then index specific folders as needed!

### Backup Your Ratings

Your ratings are valuable! Backup the database:

```bash
cp data/metadata.db ~/Backups/image-ratings-backup.db
```

### Multiple Configurations

Create different setups for different image collections:

```bash
# Work images
python cli.py --config work-config.yaml run-pipeline ~/WorkImages

# Personal images
python cli.py --config personal-config.yaml run-pipeline ~/PersonalImages
```

### External Drives

Index images on external drives:

```bash
python cli.py run-pipeline /Volumes/BackupDrive/Photos
```

Just keep the drive connected when using the UI!

---

## ✅ Quick Checklist

**Setup:**
- [ ] Install Python 3.9+
- [ ] Run `./setup.sh`
- [ ] Verify: `python cli.py --help` works

**Indexing:**
- [ ] Know where your images are (e.g., `/Users/aviz/Pictures/`)
- [ ] Run: `python cli.py run-pipeline /path/to/images`
- [ ] Wait for completion
- [ ] Verify: `python cli.py stats` shows your images

**Using:**
- [ ] Start server: `python server.py`
- [ ] Open browser: `http://localhost:8000/ui`
- [ ] Search, browse, rate!

---

## 🎓 Understanding the Magic

### Why Embeddings?

Traditional search:
```
Search: "sunset"
Finds: Files named "sunset*.jpg"
Misses: sunset-123.jpg, beach_evening.jpg, IMG_4567.jpg
```

Semantic search with embeddings:
```
Search: "sunset"
Converts to: [0.23, -0.45, 0.67, ...]
Finds: ALL sunset images, even if named "IMG_4567.jpg"
Works by: Understanding image CONTENT, not filename
```

### Why FAISS?

Comparing vectors is slow:
```
1,000 images × 512 dimensions = 512,000 comparisons
100,000 images = 51,200,000 comparisons (too slow!)
```

FAISS makes it fast:
```
Uses: Clustering and approximation
Speed: Milliseconds instead of seconds
Trade-off: 99% accuracy vs 100% accuracy
Result: Real-time search on millions of images!
```

---

Enjoy your image search system! 🚀📸
