"""Configuration management for the image search system."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip


class Config(BaseModel):
    """Main configuration for the image search system."""

    # Paths
    data_dir: Path = Field(default=Path("data"), description="Root data directory")
    db_path: Path = Field(default=Path("data/metadata.db"), description="SQLite database path")
    index_path: Path = Field(default=Path("data/faiss.index"), description="FAISS index path")
    embeddings_path: Path = Field(default=Path("data/embeddings.npy"), description="Full embeddings cache")
    thumbnails_dir: Path = Field(default=Path("data/thumbnails"), description="Thumbnails directory")

    # Model settings
    model_name: str = Field(default="ViT-B-32", description="CLIP model name")  # Use a commonly available model
    pretrained: str = Field(default="openai", description="Pretrained weights")
    device: str = Field(default="cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") else "cpu", description="Device (cuda/cpu)")
    batch_size: int = Field(default=32, description="Batch size for embedding generation")

    # Image processing
    thumbnail_size: tuple[int, int] = Field(default=(384, 384), description="Thumbnail size")
    image_extensions: list[str] = Field(
        default=[".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"],
        description="Supported image extensions"
    )

    # FAISS index settings
    embedding_dim: int = Field(default=512, description="Embedding dimension (ViT-B-32)")
    nlist: int = Field(default=4096, description="Number of IVF clusters")
    m_pq: int = Field(default=64, description="Number of PQ sub-vectors")
    nbits_pq: int = Field(default=8, description="Bits per PQ code")
    nprobe: int = Field(default=32, description="Number of clusters to search")

    # Search settings
    top_k_ivf: int = Field(default=1000, description="Retrieve from IVF-PQ")
    top_k_refined: int = Field(default=100, description="Re-rank with exact vectors")

    # Processing
    num_workers: int = Field(default=4, description="Number of worker threads")
    checkpoint_interval: int = Field(default=1000, description="Save progress every N images")

    # Duplicate detection
    duplicate_hash_threshold: int = Field(
        default=5,
        description="Hamming distance threshold for duplicate detection (0-64). "
                    "Lower = stricter. 5 ≈ 92% similar, 10 ≈ 84% similar"
    )

    # Embedding API settings
    embedding_mode: str = Field(
        default=os.environ.get("EMBEDDING_MODE", "local"),
        description="Embedding mode: 'local' (CLIP) or 'gemini' (API)"
    )
    gemini_api_key: Optional[str] = Field(
        default=os.environ.get("GEMINI_API_KEY"),
        description="Google Gemini API key for embedding API"
    )
    gemini_embedding_dim: int = Field(
        default=768,
        description="Gemini embedding dimension (768 for gemini-embedding-001)"
    )

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        super().__init__(**data)
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from file or use defaults."""
    if config_path and config_path.exists():
        import yaml
        with open(config_path) as f:
            data = yaml.safe_load(f)
        return Config(**data)
    return Config()


def save_config(config: Config, config_path: Path):
    """Save configuration to YAML file."""
    import yaml
    with open(config_path, 'w') as f:
        yaml.dump(config.model_dump(mode='json'), f, default_flow_style=False)
