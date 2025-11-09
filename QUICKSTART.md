# Quick Start Guide

Get up and running with Local Semantic Image Search in 5 minutes!

## Step 1: Install

```bash
# Run the setup script
./setup.sh

# Or manually:
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Step 2: Index Your Images

Choose the directory containing your images and run:

```bash
python cli.py run-pipeline /path/to/your/images
```

This will:
- Scan all images in the directory (recursively)
- Generate embeddings using SigLIP-2
- Build a FAISS search index

For a large image collection (100K+ images), this may take a while. The process is resumable, so you can stop and restart anytime.

### Example with a small test dataset:

```bash
# Create a test directory with some images
mkdir -p test_images
# Copy some images to test_images/

# Index them
python cli.py run-pipeline test_images
```

## Step 3: Search!

### Text-to-Image Search

Find images using natural language:

```bash
python cli.py search-text "a cat sitting on a couch"
python cli.py search-text "sunset over mountains"
python cli.py search-text "person wearing a red shirt"
```

### Image-to-Image Search

Find similar images:

```bash
python cli.py search-image test_images/example.jpg
```

### Get More Results

```bash
python cli.py search-text "beach" --top-k 50
```

### JSON Output

```bash
python cli.py search-text "cat" --json-output
```

## Step 4: Try the HTTP API (Optional)

Start the server:

```bash
python server.py
```

Then visit http://localhost:8000/docs for interactive API documentation.

### API Examples

**Text Search:**
```bash
curl "http://localhost:8000/search/text?q=cat&top_k=10"
```

**Image Search:**
```bash
curl -X POST -F "file=@image.jpg" http://localhost:8000/search/image
```

## Performance Tips

### For faster indexing:
- Use a GPU (install `faiss-gpu` instead of `faiss-cpu`)
- Increase batch size in config: `batch_size: 64`

### For better search quality:
- Increase nprobe: `python cli.py search-text "cat" --top-k 20`
- Use hybrid search (enabled by default)

### For large datasets (1M+ images):
- Adjust FAISS parameters in config.yaml
- Use GPU for indexing
- Enable checkpoints (enabled by default every 1000 images)

## Troubleshooting

**Out of memory?**
- Reduce batch_size in config.yaml
- Use CPU instead of GPU: set `device: "cpu"`

**Slow search?**
- Increase nprobe in config (accuracy vs speed tradeoff)
- Use smaller top_k_ivf value

**Module not found?**
```bash
# Make sure you activated the virtual environment
source venv/bin/activate
```

## What's Next?

- Read the full [README.md](README.md) for advanced usage
- Customize [config.yaml](config.example.yaml) for your needs
- Integrate the search engine into your application

## Example Python Script

```python
from src.config import Config
from src.search import ImageSearchEngine

# Initialize
config = Config()
engine = ImageSearchEngine(config, use_hybrid=True)
engine.initialize()

# Search
results = engine.search_by_text("cat on couch", top_k=10)

# Print results
for i, result in enumerate(results, 1):
    print(f"{i}. {result.file_path}")
    print(f"   Score: {result.score:.4f}\n")

# Clean up
engine.close()
```

## Need Help?

- Check the [README.md](README.md) troubleshooting section
- Review the example config: [config.example.yaml](config.example.yaml)
- Ensure all dependencies are installed correctly

Happy searching!
