#!/usr/bin/env python3
"""
Regenerate embeddings.npy file based on embedding_index values from database.

This script:
1. Reads all embedding_index values from database
2. Gets corresponding images
3. Generates embeddings for those images
4. Saves embeddings to embeddings.npy in the correct order
"""

import sqlite3
import numpy as np
from pathlib import Path
from typing import Optional
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def regenerate_embeddings_by_index(
    db_path: Path,
    embeddings_path: Path,
    config_path: Optional[Path] = None,
    batch_size: int = 32,
    start_from_index: Optional[int] = None,
    max_images: Optional[int] = None
):
    """
    Regenerate embeddings.npy file based on embedding_index from database.
    
    Args:
        db_path: Path to metadata.db
        embeddings_path: Path to save embeddings.npy
        config_path: Path to config file (for model loading)
        batch_size: Batch size for embedding generation
        start_from_index: Start from this embedding_index (for resuming)
        max_images: Maximum number of images to process (for testing)
    """
    from src.config import load_config
    from src.embeddings import EmbeddingModel
    from src.image_processor import ImageProcessor
    
    logger.info("=" * 70)
    logger.info("  🔄 Regenerating Embeddings Based on embedding_index")
    logger.info("=" * 70)
    
    # Load config
    if config_path:
        config = load_config(config_path)
    else:
        config_path = Path("config_optimized.yaml")
        config = load_config(config_path)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get embedding_index range
    cursor.execute("""
        SELECT 
            MIN(embedding_index) as min_idx,
            MAX(embedding_index) as max_idx,
            COUNT(DISTINCT embedding_index) as unique_indices,
            COUNT(*) as total_images
        FROM images 
        WHERE embedding_index IS NOT NULL
    """)
    stats = cursor.fetchone()
    
    min_idx = stats['min_idx']
    max_idx = stats['max_idx']
    unique_indices = stats['unique_indices']
    total_images = stats['total_images']
    
    logger.info(f"\n📊 Database Statistics:")
    logger.info(f"  embedding_index range: {min_idx} to {max_idx}")
    logger.info(f"  Unique indices: {unique_indices:,}")
    logger.info(f"  Total images with index: {total_images:,}")
    
    # Determine which indices to process
    if start_from_index is not None:
        start_idx = start_from_index
    else:
        start_idx = min_idx
    
    end_idx = max_idx
    if max_images:
        end_idx = min(start_idx + max_images - 1, max_idx)
    
    logger.info(f"\n🎯 Processing Plan:")
    logger.info(f"  Processing indices: {start_idx} to {end_idx}")
    logger.info(f"  Expected embeddings: {end_idx - start_idx + 1:,}")
    
    # Initialize model and processor
    logger.info(f"\n⚙️  Initializing model...")
    embedding_model = EmbeddingModel(
        model_name=config.model_name,
        device=config.device
    )
    image_processor = ImageProcessor()
    
    # Prepare output array
    embedding_dim = embedding_model.get_embedding_dim()
    expected_count = end_idx - start_idx + 1
    
    logger.info(f"\n📦 Preparing output array...")
    logger.info(f"  Shape: ({expected_count}, {embedding_dim})")
    logger.info(f"  Size: ~{expected_count * embedding_dim * 4 / (1024**2):.2f} MB")
    
    # Load existing embeddings if resuming
    if embeddings_path.exists() and start_from_index is not None:
        logger.info(f"  Loading existing embeddings from {embeddings_path}")
        existing_embeddings = np.load(embeddings_path)
        logger.info(f"  Existing embeddings: {len(existing_embeddings)}")
        output_embeddings = existing_embeddings.copy()
    else:
        output_embeddings = np.zeros((expected_count, embedding_dim), dtype=np.float32)
    
    # Process in batches
    processed = 0
    failed = 0
    batch_images = []
    batch_indices = []
    batch_paths = []
    
    logger.info(f"\n🚀 Starting embedding generation...")
    
    # Get all images ordered by embedding_index
    cursor.execute("""
        SELECT id, file_path, embedding_index
        FROM images
        WHERE embedding_index IS NOT NULL
          AND embedding_index >= ?
          AND embedding_index <= ?
        ORDER BY embedding_index
    """, (start_idx, end_idx))
    
    all_records = cursor.fetchall()
    logger.info(f"  Found {len(all_records)} images to process")
    
    # Handle duplicates: group by embedding_index and take first image
    # Use dictionary to ensure we only process each embedding_index once
    records_by_index = {}
    duplicate_count = 0
    
    for record in all_records:
        emb_idx = record['embedding_index']
        if emb_idx not in records_by_index:
            records_by_index[emb_idx] = record
        else:
            duplicate_count += 1
    
    unique_records = list(records_by_index.values())
    unique_records.sort(key=lambda x: x['embedding_index'])
    
    if duplicate_count > 0:
        logger.warning(f"  ⚠️  Found {duplicate_count} duplicate embedding_index values (using first image per index)")
    
    logger.info(f"  Processing {len(unique_records)} unique embedding indices")
    
    for record in tqdm(unique_records, desc="Generating embeddings"):
        try:
            img_path = Path(record['file_path'])
            emb_idx = record['embedding_index']
            relative_idx = emb_idx - start_idx
            
            # Check if embedding already exists
            if output_embeddings[relative_idx].any():
                continue
            
            if not img_path.exists():
                logger.warning(f"  ⚠️  Image not found: {img_path}")
                failed += 1
                continue
            
            # Load image
            img = image_processor.load_image(img_path)
            if img is None:
                logger.warning(f"  ⚠️  Failed to load: {img_path}")
                failed += 1
                continue
            
            batch_images.append(img)
            batch_indices.append(relative_idx)
            batch_paths.append(img_path)
            
            # Process batch when full
            if len(batch_images) >= batch_size:
                # Generate embeddings
                embeddings = embedding_model.encode_images(
                    batch_images,
                    batch_size=len(batch_images)
                )
                
                # Save to output array
                for i, rel_idx in enumerate(batch_indices):
                    output_embeddings[rel_idx] = embeddings[i]
                
                processed += len(batch_images)
                
                # Clear batch
                batch_images = []
                batch_indices = []
                batch_paths = []
                
                # Periodic save
                if processed % 1000 == 0:
                    logger.info(f"  Progress: {processed}/{len(unique_records)} embeddings generated")
                    # Save intermediate results
                    np.save(embeddings_path, output_embeddings)
                    logger.info(f"  💾 Saved intermediate checkpoint")
        
        except Exception as e:
            logger.error(f"  ❌ Error processing {record['file_path']}: {e}")
            failed += 1
    
    # Process remaining batch
    if batch_images:
        embeddings = embedding_model.encode_images(
            batch_images,
            batch_size=len(batch_images)
        )
        for i, rel_idx in enumerate(batch_indices):
            output_embeddings[rel_idx] = embeddings[i]
        processed += len(batch_images)
    
    # Final save
    logger.info(f"\n💾 Saving embeddings to {embeddings_path}...")
    np.save(embeddings_path, output_embeddings)
    
    # Verify
    saved_embeddings = np.load(embeddings_path)
    logger.info(f"✅ Saved {len(saved_embeddings)} embeddings")
    logger.info(f"   Shape: {saved_embeddings.shape}")
    logger.info(f"   File size: {embeddings_path.stat().st_size / (1024**2):.2f} MB")
    
    logger.info(f"\n📊 Summary:")
    logger.info(f"  Processed: {processed}")
    logger.info(f"  Failed: {failed}")
    
    conn.close()
    
    return processed, failed


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Regenerate embeddings based on embedding_index")
    parser.add_argument("--db", type=Path, default=Path("data/metadata.db"), help="Database path")
    parser.add_argument("--output", type=Path, default=Path("data/embeddings.npy"), help="Output embeddings path")
    parser.add_argument("--config", type=Path, default=Path("config_optimized.yaml"), help="Config path")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--start-from", type=int, help="Start from this embedding_index")
    parser.add_argument("--max-images", type=int, help="Maximum images to process (for testing)")
    
    args = parser.parse_args()
    
    regenerate_embeddings_by_index(
        db_path=args.db,
        embeddings_path=args.output,
        config_path=args.config,
        batch_size=args.batch_size,
        start_from_index=args.start_from,
        max_images=args.max_images
    )

