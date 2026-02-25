#!/usr/bin/env python3
"""
Optimized Parallel Embedding Generation
- Maximizes resource usage (80% CPU, 20% reserved)
- Saves embeddings incrementally to prevent loss
- Works with multiple workers simultaneously
"""

import sys
import os
from pathlib import Path
import numpy as np
import multiprocessing
import psutil
import argparse
import time
from typing import List, Tuple, Optional
import filelock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_config, Config
from src.database import ImageDatabase
from src.image_processor import ImageProcessor
from src.embeddings import EmbeddingModel, EmbeddingCache
from tqdm import tqdm
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('embedding_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def calculate_optimal_workers() -> int:
    """Calculate optimal number of workers based on CPU cores (80% usage, 20% reserved)."""
    cpu_count = multiprocessing.cpu_count()
    optimal = int(cpu_count * 0.8)
    return max(1, optimal)  # At least 1 worker


def save_embeddings_thread_safe(
    embeddings_path: Path,
    new_embeddings: np.ndarray,
    embedding_indices: List[int],
    lock_path: Optional[Path] = None
) -> None:
    """
    Thread-safe embedding save operation.
    Uses file locking to prevent conflicts between workers.
    """
    if lock_path is None:
        lock_path = embeddings_path.with_suffix('.npy.lock')
    
    # Use file lock to prevent concurrent writes
    lock = filelock.FileLock(str(lock_path))
    
    with lock.acquire(timeout=300):  # Wait up to 5 minutes for lock
        # Load existing embeddings if they exist
        if embeddings_path.exists():
            existing_embeddings = np.load(embeddings_path)
            logger.info(f"Loaded {len(existing_embeddings)} existing embeddings")
        else:
            existing_embeddings = None
            logger.info("No existing embeddings found, creating new file")
        
        # Create full array with proper size
        if existing_embeddings is not None:
            max_idx = max(embedding_indices)
            current_size = len(existing_embeddings)
            
            if max_idx >= current_size:
                # Need to resize array
                new_size = max_idx + 1
                logger.info(f"Resizing embeddings array from {current_size} to {new_size}")
                
                # Create new larger array
                embedding_dim = existing_embeddings.shape[1]
                full_embeddings = np.zeros((new_size, embedding_dim), dtype=existing_embeddings.dtype)
                full_embeddings[:current_size] = existing_embeddings
            else:
                full_embeddings = existing_embeddings.copy()
        else:
            # Create new array
            max_idx = max(embedding_indices)
            embedding_dim = new_embeddings.shape[1]
            full_embeddings = np.zeros((max_idx + 1, embedding_dim), dtype=new_embeddings.dtype)
        
        # Insert new embeddings at their indices
        for emb, idx in zip(new_embeddings, embedding_indices):
            full_embeddings[idx] = emb
        
        # Save updated embeddings
        np.save(embeddings_path, full_embeddings)
        logger.info(f"Saved embeddings: {len(new_embeddings)} new, total size: {len(full_embeddings)}")


def worker_process(
    worker_id: int,
    num_workers: int,
    config_path: Path,
    checkpoint_interval: int = 1000,
    batch_size: int = 32
) -> Tuple[int, int]:
    """
    Worker process that generates embeddings for assigned images.
    
    Returns:
        (processed_count, failed_count)
    """
    logger.info(f"Worker {worker_id}/{num_workers}: Starting...")
    
    # Load config
    config = load_config(config_path)
    
    # Initialize components
    db = ImageDatabase(config.db_path)
    image_processor = ImageProcessor(config.thumbnails_dir)
    
    # Initialize embedding model
    logger.info(f"Worker {worker_id}: Loading embedding model...")
    embedding_model = EmbeddingModel(
        model_name=config.model_name,
        pretrained=config.pretrained,
        device=config.device
    )
    
    # Get assigned images using modulo partitioning
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT * FROM images 
        WHERE embedding_index IS NULL 
        AND id % ? = ?
        ORDER BY id
    """, (num_workers, worker_id))
    unprocessed = [dict(row) for row in cursor.fetchall()]
    
    if not unprocessed:
        logger.info(f"Worker {worker_id}: No unprocessed images found")
        db.close()
        return (0, 0)
    
    total = len(unprocessed)
    logger.info(f"Worker {worker_id}: Processing {total} images")
    
    processed = 0
    failed = 0
    start_time = time.time()
    
    # Process in batches
    batch_images = []
    batch_records = []
    batch_embeddings = []
    batch_indices = []
    
    for i, record in enumerate(unprocessed):
        try:
            # Load image
            img_path = Path(record['file_path'])
            img = image_processor.load_image(img_path)
            
            if img is None:
                db.add_failed_image(str(img_path), "Failed to load image")
                failed += 1
                continue
            
            batch_images.append(img)
            batch_records.append(record)
            
            # Process batch when full or at end
            if len(batch_images) >= batch_size or i == len(unprocessed) - 1:
                # Generate embeddings
                embeddings = embedding_model.encode_images(
                    batch_images,
                    batch_size=len(batch_images)
                )
                
                # Assign embedding indices
                for j, rec in enumerate(batch_records):
                    cursor.execute("SELECT COALESCE(MAX(embedding_index), -1) + 1 FROM images")
                    emb_idx = cursor.fetchone()[0]
                    
                    # Update database
                    db.add_image(
                        file_path=rec['file_path'],
                        file_name=rec['file_name'],
                        file_size=rec['file_size'],
                        width=rec['width'],
                        height=rec['height'],
                        format=rec['format'],
                        thumbnail_path=rec.get('thumbnail_path'),
                        embedding_index=emb_idx,
                        auto_commit=False
                    )
                    
                    batch_indices.append(emb_idx)
                
                db.commit()
                
                # Save embeddings to batch
                batch_embeddings.append(embeddings)
                
                # Save embeddings periodically (thread-safe)
                if processed % checkpoint_interval == 0 or i == len(unprocessed) - 1:
                    all_batch_embeddings = np.vstack(batch_embeddings)
                    save_embeddings_thread_safe(
                        config.embeddings_path,
                        all_batch_embeddings,
                        batch_indices
                    )
                    batch_embeddings = []
                    batch_indices = []
                
                processed += len(batch_images)
                
                # Clear batch
                batch_images = []
                batch_records = []
                
                # Log progress
                if processed % 1000 == 0:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed if elapsed > 0 else 0
                    remaining = total - processed
                    eta = remaining / rate if rate > 0 else 0
                    logger.info(
                        f"Worker {worker_id}: {processed}/{total} | "
                        f"Rate: {rate:.1f} img/s | ETA: {eta/60:.1f} min | Failed: {failed}"
                    )
        
        except Exception as e:
            logger.error(f"Worker {worker_id}: Error processing {record.get('file_path', 'unknown')}: {e}")
            db.add_failed_image(record.get('file_path', ''), str(e))
            failed += 1
    
    # Save any remaining embeddings
    if batch_embeddings:
        all_batch_embeddings = np.vstack(batch_embeddings)
        save_embeddings_thread_safe(
            config.embeddings_path,
            all_batch_embeddings,
            batch_indices
        )
    
    total_time = time.time() - start_time
    logger.info(
        f"Worker {worker_id}: Complete in {total_time/60:.1f} min | "
        f"Processed: {processed} | Failed: {failed}"
    )
    
    db.close()
    return (processed, failed)


def main():
    parser = argparse.ArgumentParser(description='Generate embeddings with optimal parallel processing')
    parser.add_argument('--config', type=Path, default='config_optimized.yaml',
                       help='Path to config file')
    parser.add_argument('--workers', type=int, default=None,
                       help='Number of workers (default: auto-calculate for 80% CPU usage)')
    parser.add_argument('--batch-size', type=int, default=32,
                       help='Batch size for processing')
    parser.add_argument('--checkpoint-interval', type=int, default=1000,
                       help='Save embeddings every N images')
    
    args = parser.parse_args()
    
    # Calculate optimal workers
    if args.workers is None:
        args.workers = calculate_optimal_workers()
        logger.info(f"Auto-calculated {args.workers} workers (80% of {multiprocessing.cpu_count()} CPU cores)")
    else:
        logger.info(f"Using {args.workers} workers (user-specified)")
    
    # Check system resources
    cpu_count = multiprocessing.cpu_count()
    mem = psutil.virtual_memory()
    logger.info(f"System: {cpu_count} CPU cores, {mem.total / (1024**3):.1f} GB RAM")
    logger.info(f"Available: {mem.available / (1024**3):.1f} GB RAM")
    
    # Load config
    config = load_config(args.config)
    
    # Check database
    db = ImageDatabase(config.db_path)
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM images WHERE embedding_index IS NULL")
    unprocessed_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM images")
    total_count = cursor.fetchone()[0]
    db.close()
    
    logger.info(f"Images to process: {unprocessed_count:,} / {total_count:,}")
    
    if unprocessed_count == 0:
        logger.info("✅ All images already have embeddings!")
        return
    
    # Start worker processes
    logger.info(f"🚀 Starting {args.workers} parallel workers...")
    processes = []
    
    for worker_id in range(args.workers):
        p = multiprocessing.Process(
            target=worker_process,
            args=(worker_id, args.workers, args.config, args.checkpoint_interval, args.batch_size)
        )
        p.start()
        processes.append(p)
        logger.info(f"Started worker {worker_id} (PID: {p.pid})")
        time.sleep(2)  # Stagger startup
    
    # Wait for all workers to complete
    logger.info("Waiting for all workers to complete...")
    for i, p in enumerate(processes):
        p.join()
        logger.info(f"Worker {i} completed")
    
    logger.info("✅ All workers completed!")
    
    # Verify embeddings
    if config.embeddings_path.exists():
        embeddings = np.load(config.embeddings_path)
        logger.info(f"✅ Final embeddings file: {len(embeddings):,} embeddings saved")
    else:
        logger.warning("⚠️ No embeddings file created!")


if __name__ == '__main__':
    main()

