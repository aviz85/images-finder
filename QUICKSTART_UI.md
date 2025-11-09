# Quick Start: Web UI

Get the Image Explorer web interface up and running in 3 minutes!

## Step 1: Ensure Your Images Are Indexed

If you haven't already indexed your images:

```bash
# Index images from a directory
python cli.py run-pipeline /path/to/your/images

# Or if already registered, just check stats
python cli.py stats
```

You should see output like:
```
Indexing Statistics:
  Total images: 1000
  Processed: 1000
  FAISS index: data/faiss.index (exists)
```

## Step 2: Start the Web Server

```bash
python server.py
```

You should see:
```
Initializing search engine...
Loading model ViT-B-32 with openai weights on cpu...
Model loaded. Embedding dimension: 512
Loading embeddings...
Loaded 1000 embeddings from data/embeddings.npy
Loading FAISS index...
Index loaded from data/faiss.index with 1000 vectors
Initializing hybrid search...
Search engine ready!
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Step 3: Open the Web UI

Open your browser and go to:
```
http://localhost:8000/ui
```

## What You'll See

### Browse Mode (Default)
- Grid of image thumbnails
- Star ratings below each image
- Pagination controls at bottom
- Total image count in header

### Features to Try

**1. Search for Images**
```
Type in search box: "cat sitting on couch"
Results appear in real-time with relevance scores
```

**2. Rate an Image**
```
Click any image → Rate with stars → Add comment → Save
```

**3. Filter by Rating**
```
Min Rating dropdown → Select "4 Stars" → Only 4+ rated images show
```

**4. Sort Images**
```
Sort by: Rating → Order: DESC → See highest rated first
```

**5. Browse Pages**
```
Use pagination controls or page numbers at bottom
Change "Per page" to 48 for more images
```

## Quick Reference Card

### Search Examples
| Query | What It Finds |
|-------|---------------|
| `sunset over ocean` | Sunset scenes with water |
| `person wearing glasses` | People with eyewear |
| `dog playing in park` | Dogs in outdoor settings |
| `red sports car` | Red colored sports vehicles |
| `food on plate` | Meal/food photos |

### Controls
| Control | Options |
|---------|---------|
| Sort by | Date, Rating, Name, Size, Width, Height |
| Order | Ascending, Descending |
| Min Rating | Any, 1-5 stars |
| Per Page | 12, 24, 48, 96 images |

### Rating System
- ⭐ (1 star) = Poor
- ⭐⭐ (2 stars) = Below Average
- ⭐⭐⭐ (3 stars) = Average
- ⭐⭐⭐⭐ (4 stars) = Good
- ⭐⭐⭐⭐⭐ (5 stars) = Excellent

## Keyboard Tips

- Type `/` to focus search box
- Press `Esc` to close image details modal
- Click anywhere outside modal to close it

## Common Tasks

### Find Your Best Photos
```
1. Filter: Min Rating = 5 stars
2. Sort by: Rating (DESC)
3. Browse your favorites!
```

### Review Unrated Images
```
1. Sort by: Date Added (DESC)
2. Browse recent images
3. Click each to rate
```

### Search for Specific Content
```
1. Type query in search box
2. Review results with match %
3. Click to see full details
4. Rate to save favorites
```

## Troubleshooting

**"No images found"**
- Run `python cli.py stats` to check if images are indexed
- Make sure you ran `python cli.py run-pipeline /path/to/images` first

**Search returns no results**
- Verify FAISS index exists: `ls data/faiss.index`
- Rebuild if needed: `python cli.py build-index`
- Check embeddings: `ls data/embeddings.npy`

**Server won't start**
- Check if port 8000 is already in use
- Install dependencies: `pip install -r requirements.txt`
- Try a different port: Edit `server.py` and change `port=8000`

**Images load slowly**
- Reduce "Per page" to 12 or 24
- Check thumbnail generation completed
- Verify disk I/O performance

## Next Steps

- **Explore**: Browse all your images
- **Search**: Try semantic search queries
- **Rate**: Build your collection of favorites
- **Filter**: Find images by rating or criteria
- **Organize**: Use comments to add context

## API Access

The same server provides a REST API:

**Browse Images (JSON)**
```bash
curl "http://localhost:8000/browse?page=1&per_page=10"
```

**Search Images (JSON)**
```bash
curl "http://localhost:8000/search/text?q=sunset&top_k=10"
```

**Get Statistics**
```bash
curl "http://localhost:8000/stats"
curl "http://localhost:8000/rating-stats"
```

**Interactive API Docs**
```
http://localhost:8000/docs
```

## Configuration

To change the data directory or model settings:

1. Create `config.yaml`:
```yaml
data_dir: /path/to/your/data
model_name: "ViT-B-32"
pretrained: "openai"
device: "cuda"  # or "cpu"
```

2. Update server to load config:
```python
config = load_config(Path("config.yaml"))
```

---

**Enjoy exploring your images with semantic search and ratings!** 🎨

For detailed information, see [UI_GUIDE.md](UI_GUIDE.md)
