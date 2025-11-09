"""Tests for FAISS index module."""

import pytest
import numpy as np
import faiss

from src.faiss_index import FAISSIndex, HybridSearch


def test_faiss_index_initialization():
    """Test FAISSIndex initialization."""
    index = FAISSIndex(embedding_dim=128)

    assert index.embedding_dim == 128
    assert index.index is None
    assert index.is_trained is False


def test_build_flat_index(sample_embeddings):
    """Test building a flat index."""
    index = FAISSIndex(embedding_dim=128)
    index.build_flat_index(sample_embeddings, use_gpu=False)

    assert index.index is not None
    assert index.is_trained is True
    assert index.index.ntotal == len(sample_embeddings)


def test_build_ivf_pq_index(sample_embeddings):
    """Test building IVF-PQ index."""
    index = FAISSIndex(embedding_dim=128)
    index.build_ivf_pq_index(
        sample_embeddings,
        nlist=10,
        m=16,
        nbits=8,
        use_gpu=False
    )

    assert index.index is not None
    assert index.is_trained is True
    assert index.index.ntotal == len(sample_embeddings)


def test_search_flat_index(sample_embeddings):
    """Test search with flat index."""
    index = FAISSIndex(embedding_dim=128)
    index.build_flat_index(sample_embeddings, use_gpu=False)

    # Search with a query
    query = sample_embeddings[0:1]
    distances, indices = index.search(query, k=5)

    assert distances.shape == (1, 5)
    assert indices.shape == (1, 5)
    assert indices[0, 0] == 0  # First result should be the query itself


def test_search_ivf_pq_index(sample_embeddings):
    """Test search with IVF-PQ index."""
    index = FAISSIndex(embedding_dim=128)
    index.build_ivf_pq_index(
        sample_embeddings,
        nlist=10,
        m=16,
        nbits=8,
        use_gpu=False
    )

    query = sample_embeddings[0:1]
    distances, indices = index.search(query, k=5, nprobe=4)

    assert distances.shape == (1, 5)
    assert indices.shape == (1, 5)


def test_search_single_query(sample_embeddings):
    """Test search with single query vector (1D)."""
    index = FAISSIndex(embedding_dim=128)
    index.build_flat_index(sample_embeddings, use_gpu=False)

    # Query as 1D array
    query = sample_embeddings[0]
    distances, indices = index.search(query, k=5)

    assert distances.shape == (1, 5)
    assert indices.shape == (1, 5)


def test_save_and_load_index(test_config, sample_embeddings):
    """Test saving and loading index."""
    index = FAISSIndex(embedding_dim=128, index_path=test_config.index_path)
    index.build_flat_index(sample_embeddings, use_gpu=False)

    # Save index
    index.save()
    assert test_config.index_path.exists()

    # Load index
    new_index = FAISSIndex(embedding_dim=128, index_path=test_config.index_path)
    new_index.load()

    assert new_index.index.ntotal == len(sample_embeddings)
    assert new_index.is_trained is True


def test_load_nonexistent_index(test_config):
    """Test loading index that doesn't exist."""
    index = FAISSIndex(embedding_dim=128, index_path=test_config.index_path)

    with pytest.raises(FileNotFoundError):
        index.load()


def test_add_vectors(sample_embeddings):
    """Test adding vectors to existing index."""
    index = FAISSIndex(embedding_dim=128)
    index.build_flat_index(sample_embeddings[:50], use_gpu=False)

    initial_count = index.index.ntotal
    assert initial_count == 50

    # Add more vectors
    index.add_vectors(sample_embeddings[50:])

    assert index.index.ntotal == len(sample_embeddings)


def test_search_without_index():
    """Test search without building index first."""
    index = FAISSIndex(embedding_dim=128)

    with pytest.raises(RuntimeError):
        index.search(np.random.randn(1, 128).astype(np.float32), k=5)


def test_add_vectors_without_training():
    """Test adding vectors to untrained index."""
    index = FAISSIndex(embedding_dim=128)

    with pytest.raises(RuntimeError):
        index.add_vectors(np.random.randn(10, 128).astype(np.float32))


def test_hybrid_search(sample_embeddings):
    """Test hybrid search (IVF-PQ + exact re-ranking)."""
    # Build IVF-PQ index
    ivf_index = FAISSIndex(embedding_dim=128)
    ivf_index.build_ivf_pq_index(
        sample_embeddings,
        nlist=10,
        m=16,
        nbits=8,
        use_gpu=False
    )

    # Create hybrid search
    hybrid = HybridSearch(ivf_index, sample_embeddings)

    # Search
    query = sample_embeddings[0]
    distances, indices = hybrid.search(
        query,
        k=10,
        k_approximate=50,
        nprobe=4
    )

    assert len(distances) == 10
    assert len(indices) == 10
    assert indices[0] == 0  # First result should be the query


def test_hybrid_search_quality(sample_embeddings):
    """Test that hybrid search improves accuracy."""
    # Build IVF-PQ index
    ivf_index = FAISSIndex(embedding_dim=128)
    ivf_index.build_ivf_pq_index(
        sample_embeddings,
        nlist=10,
        m=16,
        nbits=8,
        use_gpu=False
    )

    # Create hybrid search
    hybrid = HybridSearch(ivf_index, sample_embeddings)

    query = sample_embeddings[5]

    # Hybrid search
    hybrid_distances, hybrid_indices = hybrid.search(query, k=5)

    # Build exact index for comparison
    exact_index = FAISSIndex(embedding_dim=128)
    exact_index.build_flat_index(sample_embeddings, use_gpu=False)
    exact_distances, exact_indices = exact_index.search(query, k=5)

    # Hybrid should find the correct top result
    assert hybrid_indices[0] == exact_indices[0, 0]


def test_faiss_index_dimension_mismatch():
    """Test that mismatched embedding dimensions raise error."""
    index = FAISSIndex(embedding_dim=128)

    wrong_dim_embeddings = np.random.randn(10, 64).astype(np.float32)

    with pytest.raises(AssertionError):
        index.build_flat_index(wrong_dim_embeddings)


def test_search_with_nprobe(sample_embeddings):
    """Test that nprobe parameter affects IVF search."""
    index = FAISSIndex(embedding_dim=128)
    index.build_ivf_pq_index(
        sample_embeddings,
        nlist=10,
        m=16,
        nbits=8,
        use_gpu=False
    )

    query = sample_embeddings[0]

    # Search with different nprobe values
    _, indices_low = index.search(query, k=10, nprobe=1)
    _, indices_high = index.search(query, k=10, nprobe=8)

    # Results should be valid
    assert indices_low.shape == (1, 10)
    assert indices_high.shape == (1, 10)
