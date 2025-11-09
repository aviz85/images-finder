# Complete Setup Guide - From Zero to Running

This guide will take you from nothing to a fully working image search system.

## Prerequisites

- Python 3.9 or higher
- A folder with images (JPEG, PNG, etc.)
- At least 2GB free disk space
- (Optional) NVIDIA GPU for faster processing

---

## Step 1: Install Dependencies

### Option A: Automatic Setup (Recommended)

```bash
./setup.sh
```

This will:
- Create a virtual environment
- Install all dependencies
- Create necessary directories

### Option B: Manual Setup

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On Mac/Linux
# OR
venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Step 2: Prepare Your Images

### Where to Put Images?

**Your images can be ANYWHERE!** They don't need to be in the project folder.

For example, you might have images at:
- `/Users/aviz/Pictures/` (Mac)
- `/home/user/photos/` (Linux)
- `C:\Users\John\Pictures\` (Windows)
- External hard drive at `/Volumes/Photos/`

### Supported Formats

- `.jpg`, `.jpeg`
- `.png`
- `.webp`
- `.bmp`
- `.gif`

### Folder Structure

Your images can be in any structure:

```
/your/photos/folder/
├── 2023/
│   ├── vacation/
│   │   ├── beach1.jpg
│   │   ├── beach2.jpg
│   └── family/
│       ├── birthday.jpg
├── 2024/
│   ├── IMG_001.jpg
│   ├── IMG_002.jpg
└── random/
    └── screenshot.png
```

The system will scan **recursively** and find all images!

---

## Step 3: Configure the System (Optional)

### Basic Usage - No Configuration Needed!

By default, data is stored in `./data/` directory.

### Advanced - Custom Configuration

Create `config.yaml`:

```yaml
# Where to store the database, index, and thumbnails
data_dir: data
db_path: data/metadata.db
index_path: data/faiss.index
embeddings_path: data/embeddings.npy
thumbnails_dir: data/thumbnails

# Model settings (default is fine for most users)
model_name: "ViT-B-32"
pretrained: "openai"
device: "cpu"  # Change to "cuda" if you have NVIDIA GPU
batch_size: 32

# Search settings
top_k_ivf: 1000
top_k_refined: 100
```

Then load it in your code or just use defaults!

---

## Step 4: Index Your Images

This is the main preparation step - it scans your images and creates the search index.

### Option A: All-in-One Command (Recommended)

```bash
# Replace /path/to/your/images with your actual image folder
python cli.py run-pipeline /Users/aviz/Pictures/MyPhotos
```

This single command will:
1. ✅ Scan all images in the folder
2. ✅ Register them in the database
3. ✅ Create thumbnails
4. ✅ Generate AI embeddings
5. ✅ Build the search index

**Time estimate:**
- 100 images: ~1-2 minutes
- 1,000 images: ~10-15 minutes
- 10,000 images: ~1-2 hours
- 100,000 images: ~10-15 hours (overnight)

### Option B: Step-by-Step (For Understanding)

#### 4.1. Scan and Register Images

```bash
python cli.py index /Users/aviz/Pictures/MyPhotos
```

This scans your folder and adds all images to the database.

**Output:**
```
Scanning for images in /Users/aviz/Pictures/MyPhotos...
Found 1500 images
Registered 1500 new images, 0 failed
```

#### 4.2. Generate Embeddings

```bash
python cli.py embed
```

This downloads the AI model (first time only) and creates embeddings for each image.

**Output:**
```
Processing 1500 images in batches of 32
Generating embeddings: 100%|████████| 1500/1500
Generated 1500 embeddings, 0 failed
```

**First-time download:** The model (~350MB) downloads automatically on first run.

#### 4.3. Build Search Index

```bash
python cli.py build-index
```

Creates the FAISS index for fast searching.

**Output:**
```
Building FAISS IVF-PQ index for 1500 embeddings...
Index built with 1500 vectors
Index saved to data/faiss.index
```

---

## Step 5: Verify Everything Works

Check the status:

```bash
python cli.py stats
```

**Expected output:**
```
Indexing Statistics:
  Total images: 1500
  Processed: 1500
  Unprocessed: 0
  Embedding cache size: 1500
  FAISS index: data/faiss.index (exists)
```

✅ All good! You're ready to search!

---

## Step 6: Start Using!

### Option A: Web UI (Visual Interface)

```bash
python server.py
```

Then open browser:
```
http://localhost:8000/ui
```

You'll see:
- Image grid with all your photos
- Search box for semantic search
- Rating system
- Filters and sorting

### Option B: Command Line (Quick Searches)

**Text search:**
```bash
python cli.py search-text "sunset over ocean"
```

**Image search:**
```bash
python cli.py search-image /path/to/query/image.jpg
```

**Get JSON output:**
```bash
python cli.py search-text "cat" --json-output
```

---

## 📂 What Gets Created

After indexing, you'll have:

```
images-finder/
├── data/                      # Created automatically
│   ├── metadata.db           # SQLite database
│   ├── embeddings.npy        # AI embeddings (4.5KB per image)
│   ├── faiss.index           # Search index (~300 bytes per image)
│   └── thumbnails/           # JPEG thumbnails (~50KB per image)
│       ├── a1b2c3d4.jpg
│       ├── e5f6g7h8.jpg
│       └── ...
```

**Disk space estimate:**
- 1,000 images: ~55 MB
- 10,000 images: ~550 MB
- 100,000 images: ~5.5 GB

**Your original images are NEVER modified or moved!**

---

## 🔄 Adding More Images Later

Got new photos? Just run the pipeline again:

```bash
python cli.py run-pipeline /path/to/new/photos
```

Or add to existing folder and re-scan:

```bash
python cli.py run-pipeline /Users/aviz/Pictures/MyPhotos
```

**It's smart!** Only new images are processed.

---

## 💡 Real-World Example

Let's say you have vacation photos:

```bash
# Your photos are here
ls /Users/aviz/Pictures/Vacation2024
# Output: beach1.jpg, beach2.jpg, sunset.jpg, ...

# Go to project directory
cd /Users/aviz/images-finder

# Activate virtual environment (if not already)
source venv/bin/activate

# Index all your vacation photos
python cli.py run-pipeline /Users/aviz/Pictures/Vacation2024

# Wait for processing (grab a coffee ☕)
# Output: "Generated 250 embeddings..."

# Start the web interface
python server.py

# Open http://localhost:8000/ui in browser
# Search: "sunset on the beach" 🏖️
# See your photos instantly!
```

---

## 🎯 Quick Reference Commands

```bash
# Activate environment
source venv/bin/activate

# Index images (all-in-one)
python cli.py run-pipeline /path/to/images

# Check status
python cli.py stats

# Search (CLI)
python cli.py search-text "your query"

# Start web UI
python server.py

# Run tests
pytest

# Get help
python cli.py --help
python cli.py search-text --help
```

---

## 🔧 Troubleshooting

### Problem: "Command not found: python"

**Solution:** Try `python3` instead:
```bash
python3 cli.py stats
```

### Problem: "No module named 'torch'"

**Solution:** Activate virtual environment:
```bash
source venv/bin/activate
```

### Problem: "CUDA out of memory"

**Solution:** Use CPU or reduce batch size:
```yaml
# In config.yaml
device: "cpu"
batch_size: 16
```

### Problem: "No images found"

**Solution:** Check your path and file extensions:
```bash
# List images in directory
ls /path/to/images/*.jpg

# Check supported extensions
python cli.py --help
```

### Problem: Model download fails

**Solution:** Check internet connection or download manually:
1. Model downloads from HuggingFace automatically
2. Stored in `~/.cache/open_clip/`
3. Retry if network interrupted

### Problem: Images not showing in UI

**Solution:**
1. Check indexing completed: `python cli.py stats`
2. Verify server running: `python server.py`
3. Check browser console for errors
4. Try refreshing the page

---

## 📊 Performance Tips

### For Fast Processing (with GPU)

```yaml
# config.yaml
device: "cuda"
batch_size: 64
```

Install GPU version of FAISS:
```bash
pip uninstall faiss-cpu
pip install faiss-gpu
```

### For Large Collections (100K+ images)

```yaml
# config.yaml
nlist: 16384         # More clusters
nprobe: 64           # Better accuracy
checkpoint_interval: 500  # Save progress often
```

### For Limited RAM

```yaml
# config.yaml
batch_size: 8        # Smaller batches
device: "cpu"        # Use CPU
```

---

## 🎓 Understanding the Process

### What Happens During Indexing?

1. **Scan** - Find all images in your folder
2. **Register** - Add metadata to database (filename, size, etc.)
3. **Thumbnails** - Create small previews (384x384)
4. **Embeddings** - AI model converts images to vectors
5. **Index** - Build fast search structure (FAISS)

### What Are Embeddings?

- AI representation of image content
- 512-dimensional vector (list of numbers)
- Similar images have similar vectors
- Enables semantic search

### How Does Search Work?

1. Your query → AI converts to vector
2. FAISS finds similar vectors (fast!)
3. Returns matching images
4. Sorted by similarity score

---

## ✅ Checklist

Before starting:
- [ ] Python 3.9+ installed
- [ ] Images in a folder somewhere
- [ ] ~2GB free disk space
- [ ] Internet connection (for model download)

Setup steps:
- [ ] Run `./setup.sh` or install manually
- [ ] Activate virtual environment
- [ ] Index images with `run-pipeline`
- [ ] Verify with `stats` command
- [ ] Start server with `python server.py`
- [ ] Open `http://localhost:8000/ui`

---

## 🎉 You're Done!

You now have a fully functional semantic image search system!

**Next steps:**
- Browse your images in the web UI
- Try semantic searches
- Rate your favorite photos
- Share the URL with others on your network

**Need help?** Check:
- `README.md` - Complete documentation
- `QUICKSTART.md` - Quick reference
- `UI_GUIDE.md` - Web interface guide
- GitHub issues - Report problems

Enjoy exploring your images! 📸✨
