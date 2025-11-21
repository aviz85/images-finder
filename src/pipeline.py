"""Batch processing pipeline for indexing images."""

from pathlib import Path
from typing import Optional, List
from tqdm import tqdm
import numpy as np
import logging
import time
from datetime import timedelta

from .config import Config
from .database import ImageDatabase
from .image_processor import ImageProcessor
from .smart_scanner import scan_images_smart
from .embeddings import EmbeddingModel, EmbeddingCache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class IndexingPipeline:
    """Pipeline for processing images and building search index."""

    def __init__(self, config: Config):
        """
        Initialize the indexing pipeline.

        Args:
            config: Configuration object
        """
        self.config = config
        self.db = ImageDatabase(config.db_path)
        self.image_processor = ImageProcessor(
            config.thumbnails_dir,
            config.thumbnail_size
        )
        self.embedding_model = None
        self.embedding_cache = EmbeddingCache(config.embeddings_path)

    def initialize_model(self):
        """Lazy load the embedding model."""
        if self.embedding_model is None:
            self.embedding_model = EmbeddingModel(
                model_name=self.config.model_name,
                pretrained=self.config.pretrained,
                device=self.config.device
            )

    def scan_and_register_images(self, image_dir: Path) -> int:
        """
        Scan directory and register all images in database.

        Args:
            image_dir: Directory containing images

        Returns:
            Number of images registered
        """
        logger.info(f"Scanning for images in {image_dir}...")
        start_time = time.time()

        # Use smart scanner with caching and database integration
        image_files = scan_images_smart(
            root_dir=image_dir,
            extensions=self.config.image_extensions,
            db_connection=self.db.conn
        )
        logger.info(f"Found {len(image_files)} images to process")

        registered = 0
        failed = 0
        skipped = 0
        start_processing = time.time()

        for idx, file_path in enumerate(tqdm(image_files, desc="Registering images", unit="img")):
            try:
                # Double-check if already registered (smart scanner should filter these out)
                existing = self.db.get_image_by_path(str(file_path))
                if existing:
                    skipped += 1
                    continue

                # Get image info
                info = self.image_processor.get_image_info(file_path)
                if not info:
                    self.db.add_failed_image(str(file_path), "Invalid image format")
                    failed += 1
                    continue

                # Generate thumbnail - DISABLED for performance (filesystem issues on external drive)
                # thumbnail_path = self.image_processor.generate_thumbnail(file_path)
                thumbnail_path = None  # Skip thumbnails for speed

                # Compute perceptual hash for visual duplicate detection
                perceptual_hash = self.image_processor.compute_perceptual_hash(file_path)
                
                # Compute SHA-256 hash for exact file duplicate detection
                sha256_hash = self.image_processor.compute_sha256_hash(file_path)

                # Add to database
                self.db.add_image(
                    file_path=str(file_path),
                    file_name=file_path.name,
                    file_size=file_path.stat().st_size,
                    width=info['width'],
                    height=info['height'],
                    format=info['format'],
                    thumbnail_path=str(thumbnail_path) if thumbnail_path else None,
                    perceptual_hash=perceptual_hash,
                    sha256_hash=sha256_hash
                )
                registered += 1

                # Log progress every 10000 images
                if (idx + 1) % 10000 == 0:
                    elapsed = time.time() - start_processing
                    rate = (idx + 1) / elapsed
                    remaining = len(image_files) - (idx + 1)
                    eta_seconds = remaining / rate if rate > 0 else 0
                    eta = timedelta(seconds=int(eta_seconds))
                    logger.info(f"Progress: {idx+1}/{len(image_files)} | Rate: {rate:.1f} img/s | ETA: {eta}")

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                self.db.add_failed_image(str(file_path), str(e))
                failed += 1

        total_time = time.time() - start_time
        logger.info(f"Registration complete in {timedelta(seconds=int(total_time))}")
        logger.info(f"Registered: {registered} new images | Skipped: {skipped} | Failed: {failed}")
        return registered

    def generate_embeddings(self, resume: bool = True) -> int:
        """
        Generate embeddings for all unprocessed images.

        Args:
            resume: Whether to resume from previous checkpoint

        Returns:
            Number of embeddings generated
        """
        logger.info("Initializing embedding model...")
        self.initialize_model()

        job_name = "embedding_generation"

        # Get processing status
        status = self.db.get_processing_status(job_name)
        if not resume or not status:
            # Start fresh
            unprocessed = self.db.get_unprocessed_images()
            start_idx = 0
            logger.info("Starting fresh embedding generation")
        else:
            # Resume from checkpoint
            unprocessed = self.db.get_unprocessed_images()
            start_idx = status.get('processed_files', 0)
            logger.info(f"Resuming from checkpoint: {start_idx} images already processed")

        if not unprocessed:
            logger.info("No unprocessed images found")
            return 0

        total = len(unprocessed)
        logger.info(f"Processing {total} images in batches of {self.config.batch_size}")
        logger.info(f"Device: {self.config.device} | Model: {self.config.model_name}")

        # Update status
        self.db.update_processing_status(
            job_name=job_name,
            total_files=total,
            processed_files=start_idx
        )

        all_embeddings = []
        processed = 0
        failed = 0
        start_time = time.time()

        # Get next embedding index
        next_embedding_idx = self.db.get_processed_count()

        # Process in batches
        batch_images = []
        batch_records = []

        for i, record in enumerate(tqdm(unprocessed, desc="Generating embeddings", unit="img")):
            try:
                # Load image
                img_path = Path(record['file_path'])
                img = self.image_processor.load_image(img_path)

                if img is None:
                    self.db.add_failed_image(str(img_path), "Failed to load image")
                    failed += 1
                    continue

                batch_images.append(img)
                batch_records.append(record)

                # Process batch when full or at end
                if len(batch_images) >= self.config.batch_size or i == len(unprocessed) - 1:
                    # Generate embeddings
                    embeddings = self.embedding_model.encode_images(
                        batch_images,
                        batch_size=len(batch_images)
                    )

                    # Update database with embedding indices
                    for j, rec in enumerate(batch_records):
                        self.db.add_image(
                            file_path=rec['file_path'],
                            file_name=rec['file_name'],
                            file_size=rec['file_size'],
                            width=rec['width'],
                            height=rec['height'],
                            format=rec['format'],
                            thumbnail_path=rec['thumbnail_path'],
                            embedding_index=next_embedding_idx + j
                        )

                    all_embeddings.append(embeddings)
                    next_embedding_idx += len(batch_images)
                    processed += len(batch_images)

                    # Clear batch
                    batch_images = []
                    batch_records = []

                    # Checkpoint
                    if processed % self.config.checkpoint_interval == 0:
                        elapsed = time.time() - start_time
                        rate = processed / elapsed
                        remaining = total - processed
                        eta_seconds = remaining / rate if rate > 0 else 0
                        eta = timedelta(seconds=int(eta_seconds))

                        logger.info(f"Checkpoint: {processed}/{total} | Rate: {rate:.1f} img/s | ETA: {eta} | Failed: {failed}")

                        self.db.update_processing_status(
                            job_name=job_name,
                            total_files=total,
                            processed_files=start_idx + processed,
                            failed_files=failed,
                            last_checkpoint=str(i)
                        )

                    # Log progress every 5000 images
                    if processed % 5000 == 0 and processed % self.config.checkpoint_interval != 0:
                        elapsed = time.time() - start_time
                        rate = processed / elapsed
                        remaining = total - processed
                        eta_seconds = remaining / rate if rate > 0 else 0
                        eta = timedelta(seconds=int(eta_seconds))
                        logger.info(f"Progress: {processed}/{total} | Rate: {rate:.1f} img/s | ETA: {eta}")

            except Exception as e:
                logger.error(f"Error processing {record['file_path']}: {e}")
                self.db.add_failed_image(record['file_path'], str(e))
                failed += 1

        # Combine all embeddings
        if all_embeddings:
            logger.info("Combining and saving embeddings...")
            final_embeddings = np.vstack(all_embeddings)

            # Load existing embeddings if they exist
            try:
                existing_embeddings = self.embedding_cache.load()
                logger.info(f"Merging with {len(existing_embeddings)} existing embeddings")
                final_embeddings = np.vstack([existing_embeddings, final_embeddings])
            except FileNotFoundError:
                logger.info("No existing embeddings found, saving fresh")

            # Save combined embeddings
            self.embedding_cache.save(final_embeddings)
            logger.info(f"Saved {len(final_embeddings)} total embeddings")

        # Mark job as completed
        self.db.update_processing_status(
            job_name=job_name,
            total_files=total,
            processed_files=start_idx + processed,
            failed_files=failed,
            completed=True
        )

        total_time = time.time() - start_time
        logger.info(f"Embedding generation complete in {timedelta(seconds=int(total_time))}")
        logger.info(f"Generated: {processed} embeddings | Failed: {failed}")
        if processed > 0:
            logger.info(f"Average rate: {processed/total_time:.1f} img/s")

        return processed

    def get_stats(self) -> dict:
        """Get indexing statistics."""
        total = self.db.get_total_images()
        processed = self.db.get_processed_count()

        return {
            'total_images': total,
            'processed_images': processed,
            'unprocessed_images': total - processed,
            'embedding_cache_size': len(self.embedding_cache) if self.embedding_cache.embeddings is not None else 0
        }

    def close(self):
        """Clean up resources."""
        self.db.close()
