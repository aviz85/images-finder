"""Tests for embeddings module."""

import pytest
import numpy as np
from PIL import Image

from src.embeddings import EmbeddingCache


def test_embedding_cache_save_and_load(test_config, sample_embeddings):
    """Test saving and loading embeddings."""
    cache = EmbeddingCache(test_config.embeddings_path)

    # Save embeddings
    cache.save(sample_embeddings)

    # Load embeddings
    loaded = cache.load()

    assert np.array_equal(loaded, sample_embeddings)
    assert len(cache) == len(sample_embeddings)


def test_embedding_cache_add_embeddings(test_config, sample_embeddings):
    """Test adding embeddings to cache."""
    cache = EmbeddingCache(test_config.embeddings_path)

    # Save initial embeddings
    initial_embeddings = sample_embeddings[:50]
    cache.save(initial_embeddings)

    # Add more embeddings
    new_embeddings = sample_embeddings[50:]
    cache.add_embeddings(new_embeddings)

    # Verify combined embeddings
    assert len(cache) == len(sample_embeddings)
    assert np.array_equal(cache.embeddings[:50], initial_embeddings)
    assert np.array_equal(cache.embeddings[50:], new_embeddings)


def test_embedding_cache_get_embeddings(test_config, sample_embeddings):
    """Test retrieving embeddings by indices."""
    cache = EmbeddingCache(test_config.embeddings_path)
    cache.save(sample_embeddings)

    # Get specific embeddings
    indices = [0, 5, 10, 15]
    retrieved = cache.get_embeddings(indices)

    assert len(retrieved) == len(indices)
    for i, idx in enumerate(indices):
        assert np.array_equal(retrieved[i], sample_embeddings[idx])


def test_embedding_cache_load_nonexistent(test_config):
    """Test loading from nonexistent file."""
    cache = EmbeddingCache(test_config.embeddings_path)

    with pytest.raises(FileNotFoundError):
        cache.load()


def test_embedding_cache_length(test_config, sample_embeddings):
    """Test cache length property."""
    cache = EmbeddingCache(test_config.embeddings_path)

    assert len(cache) == 0

    cache.save(sample_embeddings)
    assert len(cache) == len(sample_embeddings)


def test_embedding_cache_get_without_load(test_config):
    """Test getting embeddings without loading first."""
    cache = EmbeddingCache(test_config.embeddings_path)

    with pytest.raises(RuntimeError):
        cache.get_embeddings([0, 1, 2])


# Note: Full EmbeddingModel tests require downloading models
# which is slow and not suitable for unit tests.
# Integration tests should cover the full model functionality.


def test_embedding_model_mock_initialization(mocker):
    """Test EmbeddingModel initialization with mocked model."""
    # Mock open_clip functions
    mock_model = mocker.MagicMock()
    mock_preprocess = mocker.MagicMock()
    mock_tokenize = mocker.MagicMock()

    mocker.patch(
        'open_clip.create_model_and_transforms',
        return_value=(mock_model, None, mock_preprocess)
    )
    mocker.patch('open_clip.tokenize', mock_tokenize)

    # Mock model output for embedding dimension detection
    import torch
    mock_model.encode_image.return_value = torch.zeros(1, 128)

    from src.embeddings import EmbeddingModel

    model = EmbeddingModel(device='cpu')

    assert model.embedding_dim == 128
    assert model.device == 'cpu'


def test_embedding_cache_add_to_empty(test_config, sample_embeddings):
    """Test adding embeddings to empty cache."""
    cache = EmbeddingCache(test_config.embeddings_path)

    cache.add_embeddings(sample_embeddings)

    assert len(cache) == len(sample_embeddings)
    assert np.array_equal(cache.embeddings, sample_embeddings)


def test_embedding_cache_file_format(test_config, sample_embeddings):
    """Test that embeddings are saved in correct numpy format."""
    cache = EmbeddingCache(test_config.embeddings_path)
    cache.save(sample_embeddings)

    # Load directly with numpy
    loaded = np.load(test_config.embeddings_path)

    assert loaded.shape == sample_embeddings.shape
    assert loaded.dtype == sample_embeddings.dtype
