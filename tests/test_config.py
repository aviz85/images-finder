"""Tests for config module."""

import pytest
from pathlib import Path
import yaml

from src.config import Config, load_config, save_config


def test_config_defaults():
    """Test default configuration values."""
    config = Config()

    assert config.data_dir == Path("data")
    assert config.device in ["cuda", "cpu"]
    assert config.batch_size == 32
    assert config.embedding_dim == 512  # ViT-B-32
    assert config.nlist == 4096


def test_config_custom_values(temp_dir):
    """Test configuration with custom values."""
    config = Config(
        data_dir=temp_dir,
        batch_size=64,
        device="cpu"
    )

    assert config.data_dir == temp_dir
    assert config.batch_size == 64
    assert config.device == "cpu"


def test_config_creates_directories(temp_dir):
    """Test that config creates necessary directories."""
    data_dir = temp_dir / "custom_data"
    thumbnails_dir = temp_dir / "custom_thumbnails"

    config = Config(
        data_dir=data_dir,
        thumbnails_dir=thumbnails_dir
    )

    assert data_dir.exists()
    assert thumbnails_dir.exists()


def test_save_and_load_config(temp_dir):
    """Test saving and loading configuration."""
    config_path = temp_dir / "config.yaml"

    # Create and save config
    original_config = Config(
        data_dir=temp_dir / "data",
        batch_size=64,
        device="cpu"
    )
    save_config(original_config, config_path)

    # Load config
    loaded_config = load_config(config_path)

    assert loaded_config.batch_size == 64
    assert loaded_config.device == "cpu"


def test_load_config_nonexistent():
    """Test loading config when file doesn't exist."""
    config = load_config(Path("nonexistent.yaml"))
    assert isinstance(config, Config)  # Should return default config


def test_config_paths(test_config):
    """Test that all paths are properly set."""
    assert test_config.db_path.parent == test_config.data_dir
    assert test_config.index_path.parent == test_config.data_dir
    assert test_config.embeddings_path.parent == test_config.data_dir
    assert test_config.thumbnails_dir.parent == test_config.data_dir


def test_config_image_extensions():
    """Test default image extensions."""
    config = Config()
    assert ".jpg" in config.image_extensions
    assert ".png" in config.image_extensions
    assert ".jpeg" in config.image_extensions


def test_config_faiss_parameters():
    """Test FAISS-related parameters."""
    config = Config()
    assert config.nlist > 0
    assert config.m_pq > 0
    assert config.nbits_pq > 0
    assert config.nprobe > 0
