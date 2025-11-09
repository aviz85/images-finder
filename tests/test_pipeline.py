"""Tests for pipeline module."""

import pytest
from pathlib import Path
from PIL import Image

from src.pipeline import IndexingPipeline


def test_pipeline_initialization(test_config):
    """Test pipeline initialization."""
    pipeline = IndexingPipeline(test_config)

    assert pipeline.config == test_config
    assert pipeline.db is not None
    assert pipeline.image_processor is not None


def test_scan_and_register_images(test_config, temp_dir):
    """Test scanning and registering images."""
    # Create test images
    img_dir = temp_dir / "images"
    img_dir.mkdir()

    for i in range(5):
        img_path = img_dir / f"test_{i}.jpg"
        img = Image.new('RGB', (256, 256), color='red')
        img.save(img_path)

    pipeline = IndexingPipeline(test_config)
    num_registered = pipeline.scan_and_register_images(img_dir)

    assert num_registered == 5
    assert pipeline.db.get_total_images() == 5


def test_scan_and_register_skip_existing(test_config, temp_dir):
    """Test that existing images are skipped."""
    img_dir = temp_dir / "images"
    img_dir.mkdir()

    # Create test images
    for i in range(3):
        img_path = img_dir / f"test_{i}.jpg"
        img = Image.new('RGB', (256, 256), color='red')
        img.save(img_path)

    pipeline = IndexingPipeline(test_config)

    # Register first time
    num_registered1 = pipeline.scan_and_register_images(img_dir)
    assert num_registered1 == 3

    # Register again - should skip existing
    num_registered2 = pipeline.scan_and_register_images(img_dir)
    assert num_registered2 == 0


def test_scan_invalid_images(test_config, temp_dir):
    """Test handling of invalid images during scanning."""
    img_dir = temp_dir / "images"
    img_dir.mkdir()

    # Create valid image
    img_path = img_dir / "valid.jpg"
    img = Image.new('RGB', (256, 256), color='red')
    img.save(img_path)

    # Create invalid image
    invalid_path = img_dir / "invalid.jpg"
    invalid_path.write_text("not an image")

    pipeline = IndexingPipeline(test_config)
    num_registered = pipeline.scan_and_register_images(img_dir)

    # Should register only the valid image
    assert num_registered == 1


def test_get_stats(test_config, populated_db):
    """Test getting pipeline statistics."""
    # Override the db with populated one
    pipeline = IndexingPipeline(test_config)
    pipeline.db = populated_db

    stats = pipeline.get_stats()

    assert stats['total_images'] == 5
    assert stats['processed_images'] == 5
    assert stats['unprocessed_images'] == 0


def test_get_stats_partial_processing(test_config, test_db, sample_images):
    """Test stats with partially processed images."""
    # Add some processed and unprocessed images
    for i in range(3):
        test_db.add_image(
            file_path=str(sample_images[i]),
            file_name=sample_images[i].name,
            file_size=1024,
            width=256,
            height=256,
            format="JPEG",
            embedding_index=i
        )

    for i in range(3, 5):
        test_db.add_image(
            file_path=str(sample_images[i]),
            file_name=sample_images[i].name,
            file_size=1024,
            width=256,
            height=256,
            format="JPEG"
        )

    pipeline = IndexingPipeline(test_config)
    pipeline.db = test_db

    stats = pipeline.get_stats()

    assert stats['total_images'] == 5
    assert stats['processed_images'] == 3
    assert stats['unprocessed_images'] == 2


def test_pipeline_close(test_config):
    """Test pipeline cleanup."""
    pipeline = IndexingPipeline(test_config)
    pipeline.close()

    # Database should be closed
    # (We can't easily verify this without checking internal state)


# Note: Full embedding generation tests require downloading models
# which is slow for unit tests. Integration tests should cover this.


def test_scan_nested_directories(test_config, temp_dir):
    """Test scanning nested directory structure."""
    # Create nested structure
    (temp_dir / "images" / "subdir1").mkdir(parents=True)
    (temp_dir / "images" / "subdir2").mkdir(parents=True)

    # Create images in different levels
    for i, path in enumerate([
        temp_dir / "images" / "img1.jpg",
        temp_dir / "images" / "subdir1" / "img2.jpg",
        temp_dir / "images" / "subdir2" / "img3.jpg",
    ]):
        img = Image.new('RGB', (256, 256), color='red')
        img.save(path)

    pipeline = IndexingPipeline(test_config)
    num_registered = pipeline.scan_and_register_images(temp_dir / "images")

    assert num_registered == 3


def test_thumbnail_generation_during_scan(test_config, temp_dir):
    """Test that thumbnails are generated during scanning."""
    img_dir = temp_dir / "images"
    img_dir.mkdir()

    img_path = img_dir / "test.jpg"
    img = Image.new('RGB', (512, 512), color='blue')
    img.save(img_path)

    pipeline = IndexingPipeline(test_config)
    pipeline.scan_and_register_images(img_dir)

    # Check that thumbnail was created
    image_record = pipeline.db.get_image_by_path(str(img_path))
    assert image_record is not None
    assert image_record['thumbnail_path'] is not None
    assert Path(image_record['thumbnail_path']).exists()
