"""Image processing utilities including thumbnail generation."""

from PIL import Image
from pathlib import Path
from typing import Tuple, Optional
import hashlib
import imagehash


class ImageProcessor:
    """Handles image loading, validation, and thumbnail generation."""

    def __init__(self, thumbnail_dir: Path, thumbnail_size: Tuple[int, int] = (384, 384)):
        """
        Initialize image processor.

        Args:
            thumbnail_dir: Directory to store thumbnails
            thumbnail_size: Target size for thumbnails (width, height)
        """
        self.thumbnail_dir = thumbnail_dir
        self.thumbnail_size = thumbnail_size
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)

    def is_valid_image(self, file_path: Path) -> bool:
        """
        Check if file is a valid image.

        Args:
            file_path: Path to image file

        Returns:
            True if valid image, False otherwise
        """
        try:
            with Image.open(file_path) as img:
                img.verify()
            return True
        except Exception:
            return False

    def get_image_info(self, file_path: Path) -> Optional[dict]:
        """
        Get image metadata.

        Args:
            file_path: Path to image file

        Returns:
            Dictionary with image info or None if invalid
        """
        try:
            with Image.open(file_path) as img:
                return {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode
                }
        except Exception:
            return None

    def generate_thumbnail(self, file_path: Path, quality: int = 85) -> Optional[Path]:
        """
        Generate and save a thumbnail for an image.

        Args:
            file_path: Path to source image
            quality: JPEG quality for thumbnail (1-100)

        Returns:
            Path to saved thumbnail or None if failed
        """
        try:
            # Generate unique filename using hash of original path
            path_hash = hashlib.md5(str(file_path).encode()).hexdigest()
            thumbnail_name = f"{path_hash}.jpg"
            thumbnail_path = self.thumbnail_dir / thumbnail_name

            # Skip if thumbnail already exists
            if thumbnail_path.exists():
                return thumbnail_path

            # Open and convert to RGB
            with Image.open(file_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Calculate aspect-preserving thumbnail size
                img.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)

                # Save as JPEG
                img.save(thumbnail_path, 'JPEG', quality=quality, optimize=True)

            return thumbnail_path

        except Exception as e:
            print(f"Failed to generate thumbnail for {file_path}: {e}")
            return None

    def load_image(self, file_path: Path) -> Optional[Image.Image]:
        """
        Load an image file.

        Args:
            file_path: Path to image

        Returns:
            PIL Image or None if failed
        """
        try:
            img = Image.open(file_path).convert('RGB')
            return img
        except Exception as e:
            print(f"Failed to load image {file_path}: {e}")
            return None

    def compute_perceptual_hash(self, file_path: Path) -> Optional[str]:
        """
        Compute perceptual hash for duplicate detection.
        Uses phash which is precise for detecting visual duplicates.

        Args:
            file_path: Path to image

        Returns:
            Hex string representation of perceptual hash or None if failed
        """
        try:
            with Image.open(file_path) as img:
                # Use perceptual hash (phash) - better precision for true duplicates
                # Detects images with identical visual content across formats/compressions
                phash = imagehash.phash(img, hash_size=8)
                return str(phash)
        except Exception as e:
            print(f"Failed to compute perceptual hash for {file_path}: {e}")
            return None

    def compute_sha256_hash(self, file_path: Path) -> Optional[str]:
        """
        Compute SHA-256 hash of file for exact duplicate detection.
        Finds byte-for-byte identical files.

        Args:
            file_path: Path to file

        Returns:
            Hex string representation of SHA-256 hash or None if failed
        """
        try:
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                # Read file in chunks for memory efficiency
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            print(f"Failed to compute SHA-256 for {file_path}: {e}")
            return None

    def create_centered_thumbnail(self, file_path: Path, quality: int = 85) -> Optional[Path]:
        """
        Create a center-cropped square thumbnail.

        Args:
            file_path: Path to source image
            quality: JPEG quality (1-100)

        Returns:
            Path to saved thumbnail or None if failed
        """
        try:
            # Generate unique filename
            path_hash = hashlib.md5(str(file_path).encode()).hexdigest()
            thumbnail_name = f"{path_hash}_square.jpg"
            thumbnail_path = self.thumbnail_dir / thumbnail_name

            # Skip if exists
            if thumbnail_path.exists():
                return thumbnail_path

            with Image.open(file_path) as img:
                # Convert to RGB
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Calculate crop box for center square
                width, height = img.size
                size = min(width, height)
                left = (width - size) // 2
                top = (height - size) // 2
                right = left + size
                bottom = top + size

                # Crop to square
                img = img.crop((left, top, right, bottom))

                # Resize to target size
                img = img.resize(self.thumbnail_size, Image.Resampling.LANCZOS)

                # Save
                img.save(thumbnail_path, 'JPEG', quality=quality, optimize=True)

            return thumbnail_path

        except Exception as e:
            print(f"Failed to create square thumbnail for {file_path}: {e}")
            return None


def scan_images(root_dir: Path, extensions: list[str]) -> list[Path]:
    """
    Recursively scan directory for image files.

    Args:
        root_dir: Root directory to scan
        extensions: List of file extensions to include (e.g., ['.jpg', '.png'])

    Returns:
        List of image file paths
    """
    image_files = []
    extensions_lower = [ext.lower() for ext in extensions]

    for file_path in root_dir.rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in extensions_lower:
            image_files.append(file_path)

    return sorted(image_files)
