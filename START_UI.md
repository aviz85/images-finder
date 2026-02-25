# 🎨 Quick Start: UI for Similarity Search

## ✅ You Have 2 UI Options:

### Option 1: Similarity Demo (Quick Test)
**Perfect for testing if embeddings work!**

```bash
# Start the demo server
python similarity_demo.py
```

Then open: **http://localhost:5555**

**What it does:**
- Shows a random image from your collection
- Searches through 200 random images
- Displays the 10 most similar images
- Shows similarity scores (% match)

**Note:** Requires Flask (install if needed: `pip install flask`)

---

### Option 2: Full Web Server (Complete UI)
**Full-featured search interface!**

```bash
# Start the server
python server.py
```

Then open: **http://localhost:8000/ui**

**Features:**
- 🔍 **Text Search**: "sunset over ocean", "cat sitting on couch"
- 🖼️ **Image Similarity**: Click any image → Find similar images
- 📊 **Browse**: Grid view with pagination
- ⭐ **Ratings**: Rate your favorite images
- 🎯 **Filters**: Filter by rating, sort by date/size

**Uses FAISS** for fast similarity search across millions of images!

---

## 🔍 Yes, It Uses FAISS!

**FAISS** (Facebook AI Similarity Search) is used for:
- Fast similarity search (millions of images in milliseconds)
- Memory-efficient indexing (IVF-PQ compression)
- Scalable to your 3M+ image collection

**Current Status:**
- ✅ 624,017 images have embeddings
- ✅ FAISS index exists (may need rebuilding if outdated)
- ✅ Ready to test!

---

## 🚀 Recommended: Start with Similarity Demo

```bash
cd /Users/aviz/images-finder
python similarity_demo.py
```

Then click "Random + Search" button to see similar images!

---

## 📝 Notes

- **Similarity Demo**: Works with any number of embeddings (uses simple numpy comparison)
- **Full Server**: Requires FAISS index (runs faster, handles millions)
- Both prove that embeddings work and similarity search functions correctly!


