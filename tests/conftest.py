"""Pytest configuration and shared fixtures."""

import pytest
import tempfile
import shutil
from pathlib import Path
import numpy as np
from PIL import Image
import sqlite3

from src.config import Config
from src.database import ImageDatabase
from src.embeddings import EmbeddingCache


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir)


@pytest.fixture
def test_config(temp_dir):
    """Create a test configuration."""
    config = Config(
        data_dir=temp_dir / "data",
        db_path=temp_dir / "data" / "test.db",
        index_path=temp_dir / "data" / "test.index",
        embeddings_path=temp_dir / "data" / "embeddings.npy",
        thumbnails_dir=temp_dir / "data" / "thumbnails",
        device="cpu",  # Always use CPU for tests
        batch_size=4,
        embedding_dim=128,  # Use smaller dim for faster tests
        nlist=10,
        m_pq=16,
        nbits_pq=8,
        nprobe=4,
        checkpoint_interval=10
    )
    return config


@pytest.fixture
def test_db(test_config):
    """Create a test database."""
    db = ImageDatabase(test_config.db_path)
    yield db
    db.close()


@pytest.fixture
def sample_image(temp_dir):
    """Create a sample test image."""
    img_path = temp_dir / "test_image.jpg"
    img = Image.new('RGB', (256, 256), color='red')
    img.save(img_path)
    return img_path


@pytest.fixture
def sample_images(temp_dir):
    """Create multiple sample test images."""
    images = []
    colors = ['red', 'green', 'blue', 'yellow', 'cyan']

    for i, color in enumerate(colors):
        img_path = temp_dir / f"test_image_{i}.jpg"
        img = Image.new('RGB', (256, 256), color=color)
        img.save(img_path)
        images.append(img_path)

    return images


@pytest.fixture
def sample_embeddings():
    """Create sample embeddings for testing."""
    np.random.seed(42)
    embeddings = np.random.randn(500, 128).astype(np.float32)  # Increased from 100 to 500
    # Normalize to unit length
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    return embeddings


@pytest.fixture
def embedding_cache(test_config, sample_embeddings):
    """Create an embedding cache with sample data."""
    cache = EmbeddingCache(test_config.embeddings_path)
    cache.save(sample_embeddings)
    return cache


@pytest.fixture
def populated_db(test_db, sample_images):
    """Create a database populated with sample images."""
    for i, img_path in enumerate(sample_images):
        test_db.add_image(
            file_path=str(img_path),
            file_name=img_path.name,
            file_size=img_path.stat().st_size,
            width=256,
            height=256,
            format="JPEG",
            thumbnail_path=str(img_path),
            embedding_index=i
        )
    return test_db


@pytest.fixture
def mock_clip_model(mocker):
    """Mock the OpenCLIP model for faster tests."""
    mock_model = mocker.MagicMock()
    mock_model.encode_image.return_value = np.random.randn(1, 128).astype(np.float32)
    mock_model.encode_text.return_value = np.random.randn(1, 128).astype(np.float32)
    return mock_model
