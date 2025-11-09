"""Integration tests for the complete system."""

import pytest
from pathlib import Path
from PIL import Image
import numpy as np

from src.config import Config
from src.pipeline import IndexingPipeline
from src.search import ImageSearchEngine
from src.faiss_index import FAISSIndex
from src.embeddings import EmbeddingCache


@pytest.mark.integration
@pytest.mark.requires_model
@pytest.mark.skip(reason="Requires downloading large CLIP model - run manually with --run-requires-model")
def test_end_to_end_indexing_and_search(test_config, temp_dir):
    """Test complete workflow: scan -> register -> search (with mock embeddings)."""
    # Create test images
    img_dir = temp_dir / "test_images"
    img_dir.mkdir()

    image_paths = []
    colors = ['red', 'green', 'blue']
    for i, color in enumerate(colors):
        img_path = img_dir / f"image_{i}.jpg"
        img = Image.new('RGB', (256, 256), color=color)
        img.save(img_path)
        image_paths.append(img_path)

    # Step 1: Scan and register images
    pipeline = IndexingPipeline(test_config)
    num_registered = pipeline.scan_and_register_images(img_dir)

    assert num_registered == 3
    assert pipeline.db.get_total_images() == 3

    # Step 2: Create mock embeddings (since we can't download models in tests)
    np.random.seed(42)
    embeddings = np.random.randn(3, 128).astype(np.float32)
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

    # Update database with embedding indices
    for i, img_path in enumerate(image_paths):
        pipeline.db.add_image(
            file_path=str(img_path),
            file_name=img_path.name,
            file_size=img_path.stat().st_size,
            width=256,
            height=256,
            format="JPEG",
            thumbnail_path=str(img_path),
            embedding_index=i
        )

    # Save embeddings
    cache = EmbeddingCache(test_config.embeddings_path)
    cache.save(embeddings)

    # Step 3: Build FAISS index
    faiss_index = FAISSIndex(test_config.embedding_dim, test_config.index_path)
    faiss_index.build_flat_index(embeddings, use_gpu=False)
    faiss_index.save()

    # Step 4: Search
    engine = ImageSearchEngine(test_config, use_hybrid=False)
    engine.initialize()

    # Search by embedding (simulate text/image search)
    query_embedding = embeddings[0]
    results = engine.search_by_embedding(query_embedding, top_k=3)

    assert len(results) == 3
    assert results[0].score > 0.99  # Should find itself first

    pipeline.close()
    engine.close()


@pytest.mark.integration
def test_database_and_faiss_consistency(test_config, temp_dir):
    """Test that database and FAISS index stay consistent."""
    # Create images
    img_dir = temp_dir / "images"
    img_dir.mkdir()

    num_images = 10
    for i in range(num_images):
        img_path = img_dir / f"img_{i}.jpg"
        img = Image.new('RGB', (128, 128), color='red')
        img.save(img_path)

    # Index images
    pipeline = IndexingPipeline(test_config)
    pipeline.scan_and_register_images(img_dir)

    # Create mock embeddings
    embeddings = np.random.randn(num_images, 128).astype(np.float32)
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

    # Update database
    for i in range(num_images):
        img_path = img_dir / f"img_{i}.jpg"
        pipeline.db.add_image(
            file_path=str(img_path),
            file_name=img_path.name,
            file_size=1024,
            width=128,
            height=128,
            format="JPEG",
            embedding_index=i
        )

    # Save embeddings and build index
    cache = EmbeddingCache(test_config.embeddings_path)
    cache.save(embeddings)

    faiss_index = FAISSIndex(test_config.embedding_dim, test_config.index_path)
    faiss_index.build_flat_index(embeddings, use_gpu=False)

    # Verify consistency
    assert pipeline.db.get_total_images() == num_images
    assert pipeline.db.get_processed_count() == num_images
    assert faiss_index.index.ntotal == num_images
    assert len(cache) == num_images

    pipeline.close()


@pytest.mark.integration
def test_resumable_processing(test_config, temp_dir):
    """Test that processing can be resumed after interruption."""
    img_dir = temp_dir / "images"
    img_dir.mkdir()

    # Create images
    for i in range(5):
        img_path = img_dir / f"img_{i}.jpg"
        img = Image.new('RGB', (128, 128), color='red')
        img.save(img_path)

    pipeline = IndexingPipeline(test_config)

    # First run: register all images
    pipeline.scan_and_register_images(img_dir)
    assert pipeline.db.get_total_images() == 5

    # Simulate partial processing: only process 3 images
    for i in range(3):
        img_path = img_dir / f"img_{i}.jpg"
        pipeline.db.add_image(
            file_path=str(img_path),
            file_name=img_path.name,
            file_size=1024,
            width=128,
            height=128,
            format="JPEG",
            embedding_index=i
        )

    # Update processing status
    pipeline.db.update_processing_status(
        job_name="test_job",
        total_files=5,
        processed_files=3,
        failed_files=0
    )

    # Check we can identify unprocessed images
    unprocessed = pipeline.db.get_unprocessed_images()
    assert len(unprocessed) == 2

    # Process remaining
    for i, record in enumerate(unprocessed, start=3):
        pipeline.db.add_image(
            file_path=record['file_path'],
            file_name=record['file_name'],
            file_size=record['file_size'],
            width=record['width'],
            height=record['height'],
            format=record['format'],
            embedding_index=i
        )

    # Verify all processed
    assert pipeline.db.get_processed_count() == 5

    pipeline.close()


@pytest.mark.integration
def test_hybrid_search_integration(test_config, sample_embeddings):
    """Test hybrid search with IVF-PQ and exact re-ranking."""
    # Build IVF-PQ index
    ivf_index = FAISSIndex(test_config.embedding_dim, test_config.index_path)
    ivf_index.build_ivf_pq_index(
        sample_embeddings,
        nlist=test_config.nlist,
        m=test_config.m_pq,
        nbits=test_config.nbits_pq,
        use_gpu=False
    )

    # Save embeddings
    cache = EmbeddingCache(test_config.embeddings_path)
    cache.save(sample_embeddings)

    # Save index
    ivf_index.save()

    # Load and search
    loaded_index = FAISSIndex(test_config.embedding_dim, test_config.index_path)
    loaded_index.load()

    from src.faiss_index import HybridSearch
    hybrid = HybridSearch(loaded_index, sample_embeddings)

    # Search with query
    query = sample_embeddings[10]
    distances, indices = hybrid.search(
        query,
        k=10,
        k_approximate=50,
        nprobe=test_config.nprobe
    )

    assert len(distances) == 10
    assert len(indices) == 10
    assert indices[0] == 10  # Should find itself


@pytest.mark.integration
def test_pipeline_statistics(test_config, temp_dir):
    """Test that pipeline statistics are accurate."""
    img_dir = temp_dir / "images"
    img_dir.mkdir()

    # Create test images
    for i in range(7):
        img_path = img_dir / f"img_{i}.jpg"
        img = Image.new('RGB', (128, 128), color='red')
        img.save(img_path)

    pipeline = IndexingPipeline(test_config)

    # Initial stats
    stats = pipeline.get_stats()
    assert stats['total_images'] == 0
    assert stats['processed_images'] == 0

    # After registration
    pipeline.scan_and_register_images(img_dir)
    stats = pipeline.get_stats()
    assert stats['total_images'] == 7
    assert stats['processed_images'] == 0
    assert stats['unprocessed_images'] == 7

    # After partial processing
    for i in range(4):
        img_path = img_dir / f"img_{i}.jpg"
        pipeline.db.add_image(
            file_path=str(img_path),
            file_name=img_path.name,
            file_size=1024,
            width=128,
            height=128,
            format="JPEG",
            embedding_index=i
        )

    stats = pipeline.get_stats()
    assert stats['total_images'] == 7
    assert stats['processed_images'] == 4
    assert stats['unprocessed_images'] == 3

    pipeline.close()


@pytest.mark.integration
def test_index_persistence(test_config, sample_embeddings):
    """Test that index can be saved and loaded correctly."""
    # Build and save index
    index1 = FAISSIndex(test_config.embedding_dim, test_config.index_path)
    index1.build_flat_index(sample_embeddings, use_gpu=False)
    index1.save()

    # Search with original index
    query = sample_embeddings[5]
    distances1, indices1 = index1.search(query, k=10)

    # Load index in new instance
    index2 = FAISSIndex(test_config.embedding_dim, test_config.index_path)
    index2.load()

    # Search with loaded index
    distances2, indices2 = index2.search(query, k=10)

    # Results should be identical
    np.testing.assert_array_equal(indices1, indices2)
    np.testing.assert_array_almost_equal(distances1, distances2, decimal=5)


@pytest.mark.integration
def test_thumbnail_generation_integration(test_config, temp_dir):
    """Test thumbnail generation during indexing pipeline."""
    img_dir = temp_dir / "images"
    img_dir.mkdir()

    # Create large image
    img_path = img_dir / "large.jpg"
    img = Image.new('RGB', (2000, 1500), color='blue')
    img.save(img_path)

    pipeline = IndexingPipeline(test_config)
    pipeline.scan_and_register_images(img_dir)

    # Verify thumbnail was created
    image_record = pipeline.db.get_image_by_path(str(img_path))
    assert image_record['thumbnail_path'] is not None

    thumb_path = Path(image_record['thumbnail_path'])
    assert thumb_path.exists()

    # Verify thumbnail size
    with Image.open(thumb_path) as thumb:
        assert thumb.width <= test_config.thumbnail_size[0]
        assert thumb.height <= test_config.thumbnail_size[1]

    pipeline.close()
