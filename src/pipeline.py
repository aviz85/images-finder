"""Batch processing pipeline for indexing images."""

from pathlib import Path
from typing import Optional, List
from tqdm import tqdm
import numpy as np

from .config import Config
from .database import ImageDatabase
from .image_processor import ImageProcessor, scan_images
from .embeddings import EmbeddingModel, EmbeddingCache


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
        print(f"Scanning for images in {image_dir}...")
        image_files = scan_images(image_dir, self.config.image_extensions)
        print(f"Found {len(image_files)} images")

        registered = 0
        failed = 0

        for file_path in tqdm(image_files, desc="Registering images"):
            try:
                # Check if already registered
                existing = self.db.get_image_by_path(str(file_path))
                if existing:
                    continue

                # Get image info
                info = self.image_processor.get_image_info(file_path)
                if not info:
                    self.db.add_failed_image(str(file_path), "Invalid image format")
                    failed += 1
                    continue

                # Generate thumbnail
                thumbnail_path = self.image_processor.generate_thumbnail(file_path)

                # Compute perceptual hash for duplicate detection
                perceptual_hash = self.image_processor.compute_perceptual_hash(file_path)

                # Add to database
                self.db.add_image(
                    file_path=str(file_path),
                    file_name=file_path.name,
                    file_size=file_path.stat().st_size,
                    width=info['width'],
                    height=info['height'],
                    format=info['format'],
                    thumbnail_path=str(thumbnail_path) if thumbnail_path else None,
                    perceptual_hash=perceptual_hash
                )
                registered += 1

            except Exception as e:
                self.db.add_failed_image(str(file_path), str(e))
                failed += 1

        print(f"Registered {registered} new images, {failed} failed")
        return registered

    def generate_embeddings(self, resume: bool = True) -> int:
        """
        Generate embeddings for all unprocessed images.

        Args:
            resume: Whether to resume from previous checkpoint

        Returns:
            Number of embeddings generated
        """
        self.initialize_model()

        job_name = "embedding_generation"

        # Get processing status
        status = self.db.get_processing_status(job_name)
        if not resume or not status:
            # Start fresh
            unprocessed = self.db.get_unprocessed_images()
            start_idx = 0
        else:
            # Resume from checkpoint
            unprocessed = self.db.get_unprocessed_images()
            start_idx = status.get('processed_files', 0)
            print(f"Resuming from {start_idx} processed images")

        if not unprocessed:
            print("No unprocessed images found")
            return 0

        total = len(unprocessed)
        print(f"Processing {total} images in batches of {self.config.batch_size}")

        # Update status
        self.db.update_processing_status(
            job_name=job_name,
            total_files=total,
            processed_files=start_idx
        )

        all_embeddings = []
        processed = 0
        failed = 0

        # Get next embedding index
        next_embedding_idx = self.db.get_processed_count()

        # Process in batches
        batch_images = []
        batch_records = []

        for i, record in enumerate(tqdm(unprocessed, desc="Generating embeddings")):
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
                        self.db.update_processing_status(
                            job_name=job_name,
                            total_files=total,
                            processed_files=start_idx + processed,
                            failed_files=failed,
                            last_checkpoint=str(i)
                        )

            except Exception as e:
                print(f"Error processing {record['file_path']}: {e}")
                self.db.add_failed_image(record['file_path'], str(e))
                failed += 1

        # Combine all embeddings
        if all_embeddings:
            final_embeddings = np.vstack(all_embeddings)

            # Load existing embeddings if they exist
            try:
                existing_embeddings = self.embedding_cache.load()
                final_embeddings = np.vstack([existing_embeddings, final_embeddings])
            except FileNotFoundError:
                pass

            # Save combined embeddings
            self.embedding_cache.save(final_embeddings)

        # Mark job as completed
        self.db.update_processing_status(
            job_name=job_name,
            total_files=total,
            processed_files=start_idx + processed,
            failed_files=failed,
            completed=True
        )

        print(f"Generated {processed} embeddings, {failed} failed")
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
