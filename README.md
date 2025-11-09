# Local Semantic Image Search

A fully local, privacy-preserving semantic image search engine for up to 4 million images. Built with OpenCLIP (SigLIP-2), FAISS, and SQLite.

## Features

- **Fully Local**: No cloud services, all processing happens on your machine
- **Semantic Search**: Find images using natural language descriptions
- **Image-to-Image Search**: Find similar images using a query image
- **Scalable**: Handles millions of images efficiently with FAISS IVF-PQ indexing
- **Resumable**: Batch processing with checkpoints for interruption recovery
- **Dual Interface**: CLI and HTTP API (FastAPI)
- **Privacy-First**: All data stays on your machine
- **Duplicate Detection**: Perceptual-hash matching surfaces near-identical images for cleanup

## Architecture

- **Embeddings**: SigLIP-2 (ViT-SO400M-14) via OpenCLIP
- **Vector Index**: FAISS IVF-PQ for memory-efficient approximate search
- **Metadata**: SQLite database for image information
- **Search**: Hybrid approach (IVF-PQ + exact re-ranking)

## Installation

### Prerequisites

- Python 3.9+
- CUDA-capable GPU (recommended for large datasets)
- ~10GB free disk space for models and indices

### Setup

```bash
# Clone or navigate to the project directory
cd images-finder

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For GPU support, install FAISS with GPU
pip uninstall faiss-cpu
pip install faiss-gpu
```

## Quick Start

### 1. Index Your Images

Run the complete pipeline to index a directory of images:

```bash
python cli.py run-pipeline /path/to/your/images
```

This will:
1. Scan and register all images
2. Generate embeddings (SigLIP-2)
3. Build FAISS search index

### 2. Search

**Text-to-Image Search:**

```bash
python cli.py search-text "a cat sitting on a couch"
```

**Image-to-Image Search:**

```bash
python cli.py search-image /path/to/query/image.jpg
```

### 3. Handle Duplicates

Duplicate detection runs automatically as part of the pipeline. The system hashes every image, marks near-identical files, and ensures browse/search views only surface the canonical copy while still letting you review duplicates.

- In the web explorer, click the red duplicate badge on any card to inspect the alternate files and jump to them in Finder/Explorer.
- Tune sensitivity by changing `duplicate_hash_threshold` in `config.yaml` (lower = stricter match, higher = looser).
- To re-run detection after tweaking the threshold without rebuilding embeddings or the index:
  ```bash
  source venv/bin/activate
  python redetect_duplicates.py
  ```

## CLI Usage

### Index Management

```bash
# Scan and register images
python cli.py index /path/to/images

# Generate embeddings for registered images
python cli.py embed

# Build FAISS index
python cli.py build-index

# Force rebuild index
python cli.py build-index --force

# View statistics
python cli.py stats
```

### Search

```bash
# Text search with custom number of results
python cli.py search-text "sunset over mountains" --top-k 50

# Image search with JSON output
python cli.py search-image query.jpg --top-k 20 --json-output

# Search using a custom config file
python cli.py --config config.yaml search-text "beach"
```

### Complete Pipeline

```bash
# Run all steps at once
python cli.py run-pipeline /path/to/images

# Resume from checkpoint
python cli.py run-pipeline /path/to/images --resume
```

## HTTP API Usage

### Start the Server

```bash
python server.py
```

Or with uvicorn:

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

### API Endpoints

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Text Search:**
```bash
curl "http://localhost:8000/search/text?q=cat+on+couch&top_k=20"
```

**Image Search:**
```bash
curl -X POST -F "file=@query.jpg" "http://localhost:8000/search/image?top_k=20"
```

**Stats:**
```bash
curl http://localhost:8000/stats
```

**Get Thumbnail:**
```bash
curl http://localhost:8000/thumbnail/123 --output thumbnail.jpg
```

**Interactive API Docs:**
Visit `http://localhost:8000/docs` for Swagger UI

## Configuration

Create a `config.yaml` file to customize settings:

```yaml
# Paths
data_dir: data
db_path: data/metadata.db
index_path: data/faiss.index
embeddings_path: data/embeddings.npy
thumbnails_dir: data/thumbnails

# Model settings
model_name: "hf-hub:timm/ViT-SO400M-14-SigLIP-384"
pretrained: "webli"
device: "cuda"  # or "cpu"
batch_size: 32

# FAISS index settings
embedding_dim: 1152
nlist: 4096
m_pq: 64
nbits_pq: 8
nprobe: 32

# Search settings
top_k_ivf: 1000
top_k_refined: 100

# Processing
num_workers: 4
checkpoint_interval: 1000
```

Use with:
```bash
python cli.py --config config.yaml run-pipeline /images
```

## Performance Tips

### For Large Datasets (1M+ images)

1. **Use GPU**: Install `faiss-gpu` for 10-100x faster indexing
2. **Adjust Batch Size**: Increase for GPUs with more VRAM
3. **Tune FAISS Parameters**:
   - `nlist`: More clusters = better accuracy, slower search (4096-16384)
   - `nprobe`: More probes = better accuracy, slower search (32-256)
   - `m_pq`: More sub-vectors = better accuracy, more memory

### For Small Datasets (<100K images)

1. Use flat index for exact search:
   ```python
   faiss_index.build_flat_index(embeddings)
   ```

2. Reduce checkpoint interval for faster processing

## Project Structure

```
images-finder/
├── src/
│   ├── config.py           # Configuration management
│   ├── database.py         # SQLite database interface
│   ├── embeddings.py       # OpenCLIP embedding generation
│   ├── faiss_index.py      # FAISS index management
│   ├── image_processor.py  # Image loading and thumbnails
│   ├── pipeline.py         # Batch processing pipeline
│   └── search.py           # Search engine
├── cli.py                  # Command-line interface
├── server.py               # FastAPI HTTP server
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Troubleshooting

### Out of Memory

- Reduce `batch_size` in config
- Use CPU instead of GPU for embedding generation
- Process images in smaller batches

### Slow Search

- Increase `nprobe` (accuracy vs speed tradeoff)
- Use GPU version of FAISS
- Reduce `top_k_ivf` for faster approximate search

### FAISS Not Found

```bash
# For CPU
pip install faiss-cpu

# For GPU (requires CUDA)
pip install faiss-gpu
```

### Model Download Issues

Models are downloaded automatically from HuggingFace Hub. If you have network issues:

1. Download manually from https://huggingface.co/timm/ViT-SO400M-14-SigLIP-384
2. Place in `~/.cache/open_clip/`

## Advanced Usage

### Custom Embedding Model

```python
from src.config import Config
from src.embeddings import EmbeddingModel

config = Config()
config.model_name = "hf-hub:laion/CLIP-ViT-B-32-laion2B-s34B-b79K"
config.embedding_dim = 512

model = EmbeddingModel(
    model_name=config.model_name,
    device="cuda"
)
```

### Programmatic Search

```python
from src.config import Config
from src.search import ImageSearchEngine

config = Config()
engine = ImageSearchEngine(config, use_hybrid=True)
engine.initialize()

# Text search
results = engine.search_by_text("cats playing", top_k=20)
for result in results:
    print(f"{result.file_path}: {result.score:.4f}")

# Image search
results = engine.search_by_image("query.jpg", top_k=20)
```

## Performance Benchmarks

Approximate performance on a machine with RTX 3090 (24GB VRAM):

| Operation | 100K images | 1M images | 4M images |
|-----------|-------------|-----------|-----------|
| Indexing (embed) | 5 min | 50 min | 3.5 hours |
| Build index | 10 sec | 2 min | 10 min |
| Text search | 50 ms | 100 ms | 200 ms |
| Image search | 100 ms | 150 ms | 250 ms |

## License

MIT License

## Credits

- **OpenCLIP**: https://github.com/mlfoundations/open_clip
- **FAISS**: https://github.com/facebookresearch/faiss
- **SigLIP**: https://arxiv.org/abs/2303.15343

## Contributing

Contributions welcome! Please open an issue or PR.

## Support

For issues and questions:
- Check the Troubleshooting section
- Review existing GitHub issues
- Open a new issue with details about your setup
