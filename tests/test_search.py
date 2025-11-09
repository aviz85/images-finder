"""Tests for search module."""

import pytest
import numpy as np
from PIL import Image

from src.search import SearchResult, ImageSearchEngine


def test_search_result_creation():
    """Test SearchResult initialization."""
    result = SearchResult(
        image_id=1,
        file_path="/path/to/image.jpg",
        score=0.95,
        thumbnail_path="/path/to/thumb.jpg",
        width=800,
        height=600
    )

    assert result.image_id == 1
    assert result.file_path == "/path/to/image.jpg"
    assert result.score == 0.95
    assert result.thumbnail_path == "/path/to/thumb.jpg"
    assert result.width == 800
    assert result.height == 600


def test_search_result_to_dict():
    """Test SearchResult to_dict conversion."""
    result = SearchResult(
        image_id=1,
        file_path="/path/to/image.jpg",
        score=0.95
    )

    result_dict = result.to_dict()

    assert isinstance(result_dict, dict)
    assert result_dict['image_id'] == 1
    assert result_dict['file_path'] == "/path/to/image.jpg"
    assert result_dict['score'] == 0.95


def test_search_result_repr():
    """Test SearchResult string representation."""
    result = SearchResult(
        image_id=1,
        file_path="/path/to/image.jpg",
        score=0.95
    )

    repr_str = repr(result)
    assert "SearchResult" in repr_str
    assert "/path/to/image.jpg" in repr_str
    assert "0.95" in repr_str


def test_search_engine_initialization(test_config):
    """Test ImageSearchEngine initialization."""
    engine = ImageSearchEngine(test_config, use_hybrid=True)

    assert engine.config == test_config
    assert engine.use_hybrid is True
    assert engine.db is not None


def test_build_results(test_config, populated_db, sample_embeddings):
    """Test building search results from indices."""
    # Save embeddings
    test_config.embeddings_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(test_config.embeddings_path, sample_embeddings[:5])

    engine = ImageSearchEngine(test_config, use_hybrid=False)
    engine.db = populated_db

    indices = np.array([0, 2, 4])
    scores = np.array([0.95, 0.85, 0.75])

    results = engine._build_results(indices, scores)

    assert len(results) == 3
    assert results[0].score == 0.95
    assert results[1].score == 0.85
    assert results[2].score == 0.75


def test_build_results_with_invalid_indices(test_config, populated_db):
    """Test building results with invalid indices."""
    engine = ImageSearchEngine(test_config, use_hybrid=False)
    engine.db = populated_db

    # Include invalid index (-1)
    indices = np.array([0, -1, 2])
    scores = np.array([0.95, 0.0, 0.75])

    results = engine._build_results(indices, scores)

    # Should skip invalid index
    assert len(results) == 2


def test_search_engine_close(test_config):
    """Test search engine cleanup."""
    engine = ImageSearchEngine(test_config)
    engine.close()

    # Database should be closed
    # (We can't easily verify without checking internal state)


# Note: Full search tests with real models require model downloads
# Integration tests should cover end-to-end search functionality


def test_search_result_score_conversion():
    """Test that scores are properly converted to float."""
    result = SearchResult(
        image_id=1,
        file_path="/path/to/image.jpg",
        score=np.float32(0.95)
    )

    assert isinstance(result.score, float)
    assert result.score == pytest.approx(0.95, rel=1e-5)


def test_search_result_optional_fields():
    """Test SearchResult with optional fields as None."""
    result = SearchResult(
        image_id=1,
        file_path="/path/to/image.jpg",
        score=0.95,
        thumbnail_path=None,
        width=None,
        height=None
    )

    result_dict = result.to_dict()
    assert result_dict['thumbnail_path'] is None
    assert result_dict['width'] is None
    assert result_dict['height'] is None


def test_build_results_ordering(test_config, populated_db):
    """Test that results maintain score ordering."""
    engine = ImageSearchEngine(test_config, use_hybrid=False)
    engine.db = populated_db

    indices = np.array([4, 2, 0, 1, 3])
    scores = np.array([0.99, 0.85, 0.75, 0.65, 0.55])

    results = engine._build_results(indices, scores)

    # Results should maintain the order
    assert len(results) == 5
    assert results[0].score == 0.99
    assert results[0].embedding_index == 4
    assert results[1].score == 0.85
    assert results[1].embedding_index == 2


def test_build_results_empty(test_config, test_db):
    """Test building results with empty indices."""
    engine = ImageSearchEngine(test_config, use_hybrid=False)
    engine.db = test_db

    indices = np.array([])
    scores = np.array([])

    results = engine._build_results(indices, scores)

    assert len(results) == 0


def test_search_result_metadata_fields():
    """Test that all metadata fields are properly stored."""
    result = SearchResult(
        image_id=42,
        file_path="/test/image.jpg",
        score=0.88,
        thumbnail_path="/test/thumb.jpg",
        width=1920,
        height=1080
    )

    assert result.image_id == 42
    assert result.file_path == "/test/image.jpg"
    assert result.score == pytest.approx(0.88)
    assert result.thumbnail_path == "/test/thumb.jpg"
    assert result.width == 1920
    assert result.height == 1080

    # Check dict conversion includes all fields
    d = result.to_dict()
    assert len(d) == 7
    assert all(key in d for key in ['image_id', 'file_path', 'score', 'thumbnail_path', 'width', 'height', 'embedding_index'])
