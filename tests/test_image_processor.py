"""Tests for image processor module."""

import pytest
from pathlib import Path
from PIL import Image

from src.image_processor import ImageProcessor, scan_images


def test_image_processor_initialization(test_config):
    """Test ImageProcessor initialization."""
    processor = ImageProcessor(test_config.thumbnails_dir)

    assert processor.thumbnail_dir == test_config.thumbnails_dir
    assert processor.thumbnail_dir.exists()


def test_is_valid_image(test_config, sample_image):
    """Test image validation."""
    processor = ImageProcessor(test_config.thumbnails_dir)

    assert processor.is_valid_image(sample_image) is True


def test_is_valid_image_invalid(test_config, temp_dir):
    """Test validation of invalid image."""
    processor = ImageProcessor(test_config.thumbnails_dir)

    # Create a non-image file
    invalid_file = temp_dir / "invalid.jpg"
    invalid_file.write_text("not an image")

    assert processor.is_valid_image(invalid_file) is False


def test_get_image_info(test_config, sample_image):
    """Test getting image metadata."""
    processor = ImageProcessor(test_config.thumbnails_dir)

    info = processor.get_image_info(sample_image)

    assert info is not None
    assert info['width'] == 256
    assert info['height'] == 256
    assert info['format'] == 'JPEG'
    assert 'mode' in info


def test_get_image_info_invalid(test_config, temp_dir):
    """Test getting info from invalid image."""
    processor = ImageProcessor(test_config.thumbnails_dir)

    invalid_file = temp_dir / "invalid.jpg"
    invalid_file.write_text("not an image")

    info = processor.get_image_info(invalid_file)
    assert info is None


def test_generate_thumbnail(test_config, sample_image):
    """Test thumbnail generation."""
    processor = ImageProcessor(test_config.thumbnails_dir, thumbnail_size=(128, 128))

    thumbnail_path = processor.generate_thumbnail(sample_image)

    assert thumbnail_path is not None
    assert thumbnail_path.exists()

    # Check thumbnail size
    with Image.open(thumbnail_path) as thumb:
        assert thumb.width <= 128
        assert thumb.height <= 128


def test_generate_thumbnail_caching(test_config, sample_image):
    """Test that thumbnails are cached."""
    processor = ImageProcessor(test_config.thumbnails_dir)

    # Generate first time
    thumbnail_path1 = processor.generate_thumbnail(sample_image)

    # Generate again - should return same path without regenerating
    thumbnail_path2 = processor.generate_thumbnail(sample_image)

    assert thumbnail_path1 == thumbnail_path2


def test_load_image(test_config, sample_image):
    """Test loading an image."""
    processor = ImageProcessor(test_config.thumbnails_dir)

    img = processor.load_image(sample_image)

    assert img is not None
    assert isinstance(img, Image.Image)
    assert img.mode == 'RGB'


def test_load_image_invalid(test_config, temp_dir):
    """Test loading invalid image."""
    processor = ImageProcessor(test_config.thumbnails_dir)

    invalid_file = temp_dir / "invalid.jpg"
    invalid_file.write_text("not an image")

    img = processor.load_image(invalid_file)
    assert img is None


def test_create_centered_thumbnail(test_config, temp_dir):
    """Test creating centered square thumbnail."""
    # Create a non-square image
    img_path = temp_dir / "rect_image.jpg"
    img = Image.new('RGB', (400, 200), color='blue')
    img.save(img_path)

    processor = ImageProcessor(test_config.thumbnails_dir, thumbnail_size=(128, 128))
    thumbnail_path = processor.create_centered_thumbnail(img_path)

    assert thumbnail_path is not None
    assert thumbnail_path.exists()

    # Check thumbnail is square
    with Image.open(thumbnail_path) as thumb:
        assert thumb.width == 128
        assert thumb.height == 128


def test_scan_images(temp_dir):
    """Test scanning directory for images."""
    # Create some image files
    (temp_dir / "image1.jpg").write_text("fake")
    (temp_dir / "image2.png").write_text("fake")
    (temp_dir / "image3.gif").write_text("fake")
    (temp_dir / "not_image.txt").write_text("fake")

    # Create subdirectory with images
    subdir = temp_dir / "subdir"
    subdir.mkdir()
    (subdir / "image4.jpg").write_text("fake")

    extensions = ['.jpg', '.png', '.gif']
    images = scan_images(temp_dir, extensions)

    assert len(images) == 4
    assert all(img.suffix.lower() in extensions for img in images)


def test_scan_images_empty_directory(temp_dir):
    """Test scanning empty directory."""
    images = scan_images(temp_dir, ['.jpg', '.png'])
    assert len(images) == 0


def test_scan_images_case_insensitive(temp_dir):
    """Test that file extension matching is case-insensitive."""
    (temp_dir / "image1.JPG").write_text("fake")
    (temp_dir / "image2.Png").write_text("fake")

    images = scan_images(temp_dir, ['.jpg', '.png'])
    assert len(images) == 2


def test_thumbnail_different_modes(test_config, temp_dir):
    """Test thumbnail generation for images with different color modes."""
    # Create RGBA image
    rgba_path = temp_dir / "rgba.png"
    img = Image.new('RGBA', (256, 256), color=(255, 0, 0, 128))
    img.save(rgba_path)

    processor = ImageProcessor(test_config.thumbnails_dir)
    thumbnail_path = processor.generate_thumbnail(rgba_path)

    assert thumbnail_path is not None

    # Verify it was converted to RGB
    with Image.open(thumbnail_path) as thumb:
        assert thumb.mode == 'RGB'
