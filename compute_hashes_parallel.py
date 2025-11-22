#!/usr/bin/env python3
"""Compute SHA-256 and perceptual hashes for all existing images in parallel."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config, load_config
from src.database import ImageDatabase
from src.image_processor import ImageProcessor
import logging
from tqdm import tqdm
import time
from datetime import timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def compute_hashes_for_images(config_path: str = "config_optimized.yaml"):
    """Compute hashes for all images that don't have them yet."""
    
    logger.info("Loading configuration...")
    config = load_config(Path(config_path))
    
    logger.info("Connecting to database...")
    db = ImageDatabase(config.db_path)
    
    logger.info("Initializing image processor...")
    image_processor = ImageProcessor(config.thumbnails_dir)
    
    # Get all images
    logger.info("Fetching images from database...")
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT id, file_path, perceptual_hash, sha256_hash
        FROM images
        WHERE perceptual_hash IS NULL OR sha256_hash IS NULL
    """)
    images_to_process = cursor.fetchall()
    
    total = len(images_to_process)
    logger.info(f"Found {total} images needing hash updates")
    
    if total == 0:
        logger.info("All images already have hashes! Nothing to do.")
        return
    
    processed = 0
    failed = 0
    start_time = time.time()
    
    for img in tqdm(images_to_process, desc="Computing hashes", unit="img"):
        img_id = img['id']
        file_path = Path(img['file_path'])
        current_phash = img['perceptual_hash']
        current_sha256 = img['sha256_hash']
        
        try:
            # Compute perceptual hash if missing or old average_hash
            if current_phash is None:
                perceptual_hash = image_processor.compute_perceptual_hash(file_path)
            else:
                perceptual_hash = current_phash
            
            # Compute SHA-256 if missing
            if current_sha256 is None:
                sha256_hash = image_processor.compute_sha256_hash(file_path)
            else:
                sha256_hash = current_sha256
            
            # Update database
            update_cursor = db.conn.cursor()
            update_cursor.execute("""
                UPDATE images
                SET perceptual_hash = ?, sha256_hash = ?
                WHERE id = ?
            """, (perceptual_hash, sha256_hash, img_id))
            
            db._commit_with_retry()
            processed += 1
            
            # Log progress
            if processed % 1000 == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed
                remaining = total - processed
                eta_seconds = remaining / rate if rate > 0 else 0
                eta = timedelta(seconds=int(eta_seconds))
                logger.info(f"Progress: {processed}/{total} | Rate: {rate:.1f} img/s | ETA: {eta}")
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            failed += 1
    
    total_time = time.time() - start_time
    logger.info(f"Hash computation complete in {timedelta(seconds=int(total_time))}")
    logger.info(f"Processed: {processed} | Failed: {failed}")
    logger.info(f"Average rate: {processed/total_time:.1f} img/s")

if __name__ == "__main__":
    import sys
    config_file = sys.argv[1] if len(sys.argv) > 1 else "config_optimized.yaml"
    
    print("=" * 60)
    print("  SHA-256 & Perceptual Hash Computation")
    print("=" * 60)
    print("")
    
    compute_hashes_for_images(config_file)
    
    print("")
    print("=" * 60)
    print("✓ Done!")
    print("=" * 60)



