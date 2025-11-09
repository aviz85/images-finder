"""Tests for database module."""

import pytest
from datetime import datetime

from src.database import ImageDatabase


def test_database_initialization(test_db):
    """Test database initialization and schema creation."""
    cursor = test_db.conn.cursor()

    # Check tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    assert 'images' in tables
    assert 'processing_status' in tables
    assert 'failed_images' in tables


def test_add_image(test_db, sample_image):
    """Test adding an image to the database."""
    image_id = test_db.add_image(
        file_path=str(sample_image),
        file_name=sample_image.name,
        file_size=1024,
        width=256,
        height=256,
        format="JPEG",
        thumbnail_path=str(sample_image),
        embedding_index=0
    )

    assert image_id > 0

    # Verify the image was added
    image = test_db.get_image_by_path(str(sample_image))
    assert image is not None
    assert image['file_name'] == sample_image.name
    assert image['width'] == 256
    assert image['height'] == 256


def test_add_duplicate_image(test_db, sample_image):
    """Test adding the same image twice (should update)."""
    # Add first time
    test_db.add_image(
        file_path=str(sample_image),
        file_name=sample_image.name,
        file_size=1024,
        width=256,
        height=256,
        format="JPEG"
    )

    # Add again with different size
    test_db.add_image(
        file_path=str(sample_image),
        file_name=sample_image.name,
        file_size=2048,
        width=512,
        height=512,
        format="JPEG"
    )

    # Should have updated, not created new
    image = test_db.get_image_by_path(str(sample_image))
    assert image['file_size'] == 2048
    assert image['width'] == 512

    # Check only one record exists
    total = test_db.get_total_images()
    assert total == 1


def test_get_image_by_path(test_db, sample_image):
    """Test retrieving image by file path."""
    test_db.add_image(
        file_path=str(sample_image),
        file_name=sample_image.name,
        file_size=1024,
        width=256,
        height=256,
        format="JPEG"
    )

    image = test_db.get_image_by_path(str(sample_image))
    assert image is not None
    assert image['file_path'] == str(sample_image)


def test_get_image_by_embedding_index(test_db, sample_image):
    """Test retrieving image by embedding index."""
    test_db.add_image(
        file_path=str(sample_image),
        file_name=sample_image.name,
        file_size=1024,
        width=256,
        height=256,
        format="JPEG",
        embedding_index=42
    )

    image = test_db.get_image_by_embedding_index(42)
    assert image is not None
    assert image['embedding_index'] == 42
    assert image['file_path'] == str(sample_image)


def test_get_images_by_indices(populated_db):
    """Test retrieving multiple images by indices."""
    indices = [0, 2, 4]
    images = populated_db.get_images_by_indices(indices)

    assert len(images) == 3
    assert all(img['embedding_index'] in indices for img in images)


def test_get_unprocessed_images(test_db, sample_images):
    """Test retrieving unprocessed images."""
    # Add some processed and unprocessed images
    for i, img_path in enumerate(sample_images[:3]):
        test_db.add_image(
            file_path=str(img_path),
            file_name=img_path.name,
            file_size=1024,
            width=256,
            height=256,
            format="JPEG",
            embedding_index=i  # Processed
        )

    for img_path in sample_images[3:]:
        test_db.add_image(
            file_path=str(img_path),
            file_name=img_path.name,
            file_size=1024,
            width=256,
            height=256,
            format="JPEG",
            embedding_index=None  # Unprocessed
        )

    unprocessed = test_db.get_unprocessed_images()
    assert len(unprocessed) == 2


def test_get_total_images(populated_db):
    """Test getting total image count."""
    total = populated_db.get_total_images()
    assert total == 5


def test_get_processed_count(test_db, sample_images):
    """Test getting processed image count."""
    # Add some processed images
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

    processed = test_db.get_processed_count()
    assert processed == 3


def test_add_failed_image(test_db, sample_image):
    """Test logging failed images."""
    test_db.add_failed_image(str(sample_image), "Test error message")

    cursor = test_db.conn.cursor()
    cursor.execute("SELECT * FROM failed_images WHERE file_path = ?", (str(sample_image),))
    row = cursor.fetchone()

    assert row is not None
    assert row['error_message'] == "Test error message"


def test_update_processing_status(test_db):
    """Test updating processing status."""
    test_db.update_processing_status(
        job_name="test_job",
        total_files=100,
        processed_files=50,
        failed_files=5
    )

    status = test_db.get_processing_status("test_job")
    assert status is not None
    assert status['total_files'] == 100
    assert status['processed_files'] == 50
    assert status['failed_files'] == 5


def test_update_processing_status_completion(test_db):
    """Test marking job as completed."""
    test_db.update_processing_status(
        job_name="test_job",
        total_files=100,
        processed_files=100,
        completed=True
    )

    status = test_db.get_processing_status("test_job")
    assert status['completed_at'] is not None


def test_context_manager(test_config):
    """Test database as context manager."""
    with ImageDatabase(test_config.db_path) as db:
        total = db.get_total_images()
        assert total >= 0

    # Database should be closed after context
    # (We can't easily test this without checking internal state)
