#!/usr/bin/env python3
"""
Thumbnail Generation Pipeline for Gallery Review System.

Reads village_landscape_FULL.txt, generates thumbnails, and tracks progress.
Fully resumable - can be stopped and restarted.

Usage:
    python generate_thumbnails.py [--reset] [--workers N]
"""

import sys
import os
import re
import logging
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import time

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gallery.gallery_db import GalleryDB, path_to_thumbnail_name

# Configuration
INPUT_FILE = Path(__file__).parent.parent / "village_landscape_FULL.txt"
GALLERY_DIR = Path(__file__).parent
THUMBNAILS_DIR = GALLERY_DIR / "thumbnails"
DB_PATH = GALLERY_DIR / "gallery.db"
LOG_FILE = GALLERY_DIR / "logs" / "thumbnail_gen.log"

# Thumbnail settings
THUMBNAIL_SIZE = (384, 384)
JPEG_QUALITY = 85
BATCH_SIZE = 100

# External drive base path
EXTERNAL_DRIVE = Path("/Volumes/My Book")


def setup_logging():
    """Setup logging to file and console."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def parse_input_file(filepath: Path) -> list:
    """
    Parse village_landscape_FULL.txt and extract image paths with scores.
    Returns: [(full_path, score), ...]
    """
    images = []
    pattern = re.compile(r'^\s*\d+\.\s*\[([0-9.]+)\]\s*(.+)$')

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            match = pattern.match(line)
            if match:
                score = float(match.group(1))
                relative_path = match.group(2).strip()
                # Build full path (relative paths start with D/, E/, or F/)
                full_path = EXTERNAL_DRIVE / relative_path
                images.append((str(full_path), score))

    return images


def generate_thumbnail(original_path: str, thumbnail_dir: Path) -> dict:
    """
    Generate a thumbnail for a single image.
    Returns dict with status and metadata.
    """
    result = {
        'original_path': original_path,
        'success': False,
        'thumbnail_path': None,
        'width': None,
        'height': None,
        'file_size': None,
        'error': None
    }

    try:
        # Check if original exists
        if not Path(original_path).exists():
            result['error'] = "File not found"
            return result

        # Generate thumbnail filename
        thumb_name = path_to_thumbnail_name(original_path)
        thumb_path = thumbnail_dir / thumb_name

        # Skip if thumbnail already exists
        if thumb_path.exists():
            # Get existing thumbnail info
            with Image.open(thumb_path) as img:
                result['width'], result['height'] = img.size
            result['file_size'] = thumb_path.stat().st_size
            result['thumbnail_path'] = thumb_name
            result['success'] = True
            return result

        # Open and process image
        with Image.open(original_path) as img:
            # Get original dimensions
            orig_width, orig_height = img.size

            # Convert to RGB if needed (handles RGBA, P, etc.)
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            # Create thumbnail (preserves aspect ratio)
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

            # Save thumbnail
            img.save(thumb_path, 'JPEG', quality=JPEG_QUALITY, optimize=True)

            result['width'], result['height'] = img.size
            result['file_size'] = thumb_path.stat().st_size
            result['thumbnail_path'] = thumb_name
            result['success'] = True

    except Exception as e:
        result['error'] = str(e)

    return result


def run_pipeline(reset: bool = False, num_workers: int = 4):
    """Run the thumbnail generation pipeline."""
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("Starting Thumbnail Generation Pipeline")
    logger.info("=" * 60)

    # Ensure directories exist
    THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize database
    db = GalleryDB(str(DB_PATH))

    if reset:
        logger.info("Resetting progress...")
        db.reset_progress()

    # Parse input file
    logger.info(f"Reading input file: {INPUT_FILE}")
    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        return

    images = parse_input_file(INPUT_FILE)
    total_images = len(images)
    logger.info(f"Found {total_images:,} images in input file")

    # Get existing paths in database
    existing_paths = db.get_all_paths()
    logger.info(f"Database has {len(existing_paths):,} images already")

    # Add new images to database
    new_images = [(path, score) for path, score in images if path not in existing_paths]
    if new_images:
        logger.info(f"Adding {len(new_images):,} new images to database...")
        added = db.bulk_add_images(new_images)
        logger.info(f"Added {added:,} images")

    # Update total in progress
    db.update_progress(total=total_images)

    # Get images that need thumbnails
    stats = db.get_stats()
    processed = stats.get('with_thumbnails', 0)
    logger.info(f"Images with thumbnails: {processed:,} / {total_images:,}")

    # Process in batches
    batch_num = 0
    start_time = time.time()
    last_log_time = start_time

    while True:
        # Get batch of unprocessed images
        unprocessed = db.get_unprocessed_images(limit=BATCH_SIZE)
        if not unprocessed:
            break

        batch_num += 1
        batch_start = time.time()

        # Process batch in parallel
        results = []
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = {
                executor.submit(generate_thumbnail, img['original_path'], THUMBNAILS_DIR): img
                for img in unprocessed
            }

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        # Update database with results
        success_count = 0
        fail_count = 0
        updates = []

        for result in results:
            if result['success']:
                success_count += 1
                updates.append((
                    result['thumbnail_path'],
                    result['original_path'],
                    result['width'],
                    result['height'],
                    result['file_size']
                ))
            else:
                fail_count += 1
                logger.debug(f"Failed: {result['original_path']} - {result['error']}")

        # Bulk update thumbnails
        if updates:
            db.bulk_update_thumbnails(updates)

        # Update progress
        processed += success_count
        db.update_progress(
            processed=processed,
            failed=stats.get('progress', {}).get('failed_images', 0) + fail_count,
            last_path=results[-1]['original_path'] if results else None
        )

        # Log progress periodically
        current_time = time.time()
        if current_time - last_log_time >= 10:  # Log every 10 seconds
            elapsed = current_time - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = total_images - processed
            eta = remaining / rate if rate > 0 else 0

            logger.info(
                f"Progress: {processed:,}/{total_images:,} "
                f"({100*processed/total_images:.1f}%) | "
                f"Rate: {rate:.1f}/s | "
                f"ETA: {eta/60:.0f}m"
            )
            last_log_time = current_time

    # Final stats
    elapsed = time.time() - start_time
    final_stats = db.get_stats()
    logger.info("=" * 60)
    logger.info("Pipeline Complete!")
    logger.info(f"Total images: {final_stats['total_images']:,}")
    logger.info(f"With thumbnails: {final_stats['with_thumbnails']:,}")
    logger.info(f"Elapsed time: {elapsed/60:.1f} minutes")
    logger.info(f"Average rate: {final_stats['with_thumbnails']/elapsed:.1f} img/s")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Generate thumbnails for gallery")
    parser.add_argument('--reset', action='store_true', help="Reset progress and start fresh")
    parser.add_argument('--workers', type=int, default=4, help="Number of parallel workers (default: 4)")
    args = parser.parse_args()

    run_pipeline(reset=args.reset, num_workers=args.workers)


if __name__ == "__main__":
    main()
