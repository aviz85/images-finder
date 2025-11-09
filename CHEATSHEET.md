# Quick Reference Cheat Sheet

## 🚀 Quick Start (5 Minutes)

```bash
# 1. Setup (one time)
./setup.sh

# 2. Index your images (replace path with your folder)
python cli.py run-pipeline ~/Pictures/MyPhotos

# 3. Start web UI
python server.py

# 4. Open browser
# http://localhost:8000/ui
```

---

## 📍 Where Things Are

| What | Where |
|------|-------|
| **Your images** | Anywhere! (e.g., `~/Pictures/`) |
| **Project** | `~/images-finder/` |
| **Generated data** | `~/images-finder/data/` |
| **Thumbnails** | `~/images-finder/data/thumbnails/` |
| **Database** | `~/images-finder/data/metadata.db` |
| **Web UI** | `http://localhost:8000/ui` |

---

## 🔧 Common Commands

### Setup

```bash
# Install everything
./setup.sh

# Or manually
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Indexing

```bash
# All-in-one (recommended)
python cli.py run-pipeline /path/to/images

# Step by step
python cli.py index /path/to/images      # 1. Scan
python cli.py embed                      # 2. Generate embeddings
python cli.py build-index                # 3. Build search index

# Check status
python cli.py stats
```

### Using

```bash
# Web UI (visual)
python server.py
# Then open: http://localhost:8000/ui

# CLI search
python cli.py search-text "sunset beach"
python cli.py search-image query.jpg

# JSON output
python cli.py search-text "cat" --json-output
```

### Maintenance

```bash
# Re-index (add new images)
python cli.py run-pipeline /path/to/images

# Rebuild index
python cli.py build-index --force

# Start fresh
rm -rf data/
python cli.py run-pipeline /path/to/images
```

---

## 🌐 Web UI Features

| Feature | How to Use |
|---------|------------|
| **Browse** | Opens automatically with all images |
| **Search** | Type in search box (e.g., "sunset beach") |
| **Rate** | Click image → Click stars → Save |
| **Filter** | Select "Min Rating" dropdown |
| **Sort** | Select "Sort by" dropdown |
| **Pages** | Click page numbers at bottom |

---

## 🔍 Search Examples

```bash
# Natural language
"sunset over ocean"
"person wearing glasses"
"cat sitting on couch"
"red sports car"
"food on a plate"
"mountain landscape"
"cityscape at night"
"group of people laughing"

# Works even if filenames are:
IMG_1234.jpg, DSC_5678.jpg, photo.png
```

---

## 📊 File Sizes

| Images | Data Generated |
|--------|----------------|
| 100    | ~6 MB          |
| 1,000  | ~56 MB         |
| 10,000 | ~560 MB        |
| 100,000| ~5.6 GB        |

**Your originals: NEVER modified!**

---

## ⚙️ Configuration

Create `config.yaml`:

```yaml
# Basic settings
device: "cpu"           # or "cuda" for GPU
batch_size: 32          # Lower if out of memory

# Paths
data_dir: data
thumbnails_dir: data/thumbnails

# Search tuning
top_k_ivf: 1000        # More = better accuracy
nprobe: 32             # More = slower but better
```

Use it:
```bash
python cli.py --config config.yaml run-pipeline /path
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Command not found | Use `python3` instead of `python` |
| No module named X | Activate venv: `source venv/bin/activate` |
| Out of memory | Reduce batch_size in config |
| No images found | Check path and file extensions |
| Search returns nothing | Verify index built: `cli.py stats` |
| UI won't load | Check server running on port 8000 |
| Slow processing | Use GPU: `device: "cuda"` in config |

---

## 📁 Project Structure

```
images-finder/
├── cli.py              # Command line interface
├── server.py           # Web server
├── src/                # Core modules
├── static/             # Web UI files
├── tests/              # Test suite
├── data/               # Generated (safe to delete)
├── requirements.txt    # Dependencies
└── *.md               # Documentation
```

---

## 🎯 Typical Workflow

```
1. Take/collect photos → Store in ~/Pictures/

2. Index them:
   python cli.py run-pipeline ~/Pictures/

3. Use web UI:
   python server.py
   Open http://localhost:8000/ui

4. Search, browse, rate!

5. Add more photos → Re-index (step 2)
```

---

## 🔐 Privacy

- ✅ Everything runs locally
- ✅ No cloud services
- ✅ No tracking
- ✅ Your images never leave your computer
- ⬇️ Only downloads: AI model (one-time, ~350 MB)

---

## 📊 Performance

| Operation | Time (approx) |
|-----------|---------------|
| Index 100 images | 1-2 min |
| Index 1,000 images | 10-15 min |
| Index 10,000 images | 1-2 hours |
| Search | <100 ms |
| Open UI | Instant |

---

## 🆘 Quick Help

```bash
# Get help
python cli.py --help
python cli.py search-text --help

# Run tests
pytest

# Check version
python --version
pip list | grep torch

# View API docs
python server.py
# Then: http://localhost:8000/docs
```

---

## 📱 Access from Other Devices

```bash
# Find your IP
ifconfig | grep inet  # Mac/Linux
ipconfig              # Windows

# Start server (allow external access)
python server.py

# Access from phone/tablet
http://YOUR_IP:8000/ui
# Example: http://192.168.1.100:8000/ui
```

---

## 💾 Backup Important Data

```bash
# Backup your ratings!
cp data/metadata.db ~/Backups/ratings-backup.db

# Restore
cp ~/Backups/ratings-backup.db data/metadata.db
```

---

## 🎨 Customization

### Change UI colors

Edit `static/index.html`:
```css
:root {
    --primary: #3b82f6;      /* Blue */
    --star-color: #fbbf24;   /* Gold */
}
```

### Change model

Edit `src/config.py`:
```python
model_name: "ViT-L-14"      # Larger model
device: "cuda"              # Use GPU
```

---

## 📈 Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus search |
| `Esc` | Close modal |
| `←` | Previous page |
| `→` | Next page |

---

## ✅ Pre-flight Checklist

Before indexing:
- [ ] Python 3.9+ installed
- [ ] Virtual environment activated
- [ ] Know path to your images
- [ ] 2GB+ free disk space
- [ ] Internet connection (model download)

After indexing:
- [ ] `cli.py stats` shows images
- [ ] Server starts: `python server.py`
- [ ] UI loads: `http://localhost:8000/ui`
- [ ] Search works
- [ ] Can rate images

---

## 🔗 Useful Links

- API Docs: `http://localhost:8000/docs`
- UI: `http://localhost:8000/ui`
- Health: `http://localhost:8000/health`
- Stats: `http://localhost:8000/stats`

---

## 📚 Full Documentation

- `README.md` - Complete guide
- `SETUP_GUIDE.md` - Step-by-step setup
- `FOLDER_STRUCTURE.md` - Understanding files
- `UI_GUIDE.md` - Web interface guide
- `QUICKSTART_UI.md` - UI quick start
- `TEST_REPORT.md` - Test coverage

---

**Remember: Your original images are NEVER modified! Everything happens in the `data/` folder.**

Happy searching! 🔍✨
