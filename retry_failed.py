#!/usr/bin/env python3
"""Retry processing images that failed due to transient errors."""

import sqlite3
from pathlib import Path
from src.config import Config
from src.pipeline import IndexingPipeline
import sys

def get_retryable_failures(db_path):
    """Get images that failed due to transient errors (like database locks)."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get failures that are NOT invalid image format (those are permanent)
    cursor.execute("""
        SELECT DISTINCT file_path, error_message 
        FROM failed_images 
        WHERE error_message LIKE '%locked%'
           OR error_message LIKE '%timeout%'
           OR error_message LIKE '%connection%'
        ORDER BY failed_at DESC
    """)
    
    failures = cursor.fetchall()
    conn.close()
    
    return failures


def clear_failed_entries(db_path, file_paths):
    """Remove entries from failed_images table so they can be reprocessed."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    for file_path in file_paths:
        cursor.execute("DELETE FROM failed_images WHERE file_path = ?", (file_path,))
    
    conn.commit()
    conn.close()
    print(f"✅ Cleared {len(file_paths)} entries from failed_images table")


def main():
    # Load config
    config = Config.from_yaml("config_optimized.yaml")
    
    print("=" * 70)
    print("  Retry Failed Images")
    print("=" * 70)
    print()
    
    # Get retryable failures
    print("📋 Checking for retryable failures...")
    failures = get_retryable_failures(config.db_path)
    
    if not failures:
        print("✅ No retryable failures found!")
        return
    
    print(f"Found {len(failures)} images with transient errors:")
    print()
    
    # Show error types
    error_types = {}
    for _, error in failures:
        error_types[error] = error_types.get(error, 0) + 1
    
    for error, count in error_types.items():
        print(f"  - {error}: {count} images")
    print()
    
    # Ask for confirmation
    response = input(f"Retry processing these {len(failures)} images? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Cancelled.")
        return
    
    # Clear failed entries so they can be reprocessed
    file_paths = [f[0] for f in failures]
    clear_failed_entries(config.db_path, file_paths)
    
    # Create temporary file list
    temp_list = Path("/tmp/retry_images.txt")
    with open(temp_list, 'w') as f:
        for file_path in file_paths:
            f.write(f"{file_path}\n")
    
    print()
    print("=" * 70)
    print(f"  Ready to Retry {len(failures)} Images")
    print("=" * 70)
    print()
    print("To process these images, run:")
    print()
    print("  python retry_failed.py --process")
    print()
    print("Or manually process them by running your normal pipeline")
    print("(they're no longer marked as failed, so they'll be picked up)")
    print()
    
    # If --process flag, actually process them
    if "--process" in sys.argv:
        print("🔄 Starting reprocessing...")
        print()
        
        pipeline = IndexingPipeline(config)
        
        # Process each file
        success = 0
        failed = 0
        
        for file_path in file_paths:
            path = Path(file_path)
            
            try:
                # Check if already registered
                existing = pipeline.db.get_image_by_path(str(path))
                if existing:
                    print(f"✓ Already registered: {path.name}")
                    success += 1
                    continue
                
                # Try to register
                info = pipeline.image_processor.get_image_info(path)
                if not info:
                    print(f"✗ Invalid: {path.name}")
                    pipeline.db.add_failed_image(str(path), "Invalid image format")
                    failed += 1
                    continue
                
                # Compute hashes
                perceptual_hash = pipeline.image_processor.compute_perceptual_hash(path)
                sha256_hash = pipeline.image_processor.compute_sha256_hash(path)
                
                # Add to database
                pipeline.db.add_image(
                    file_path=str(path),
                    file_name=path.name,
                    file_size=path.stat().st_size,
                    width=info['width'],
                    height=info['height'],
                    format=info['format'],
                    thumbnail_path=None,
                    perceptual_hash=perceptual_hash,
                    sha256_hash=sha256_hash
                )
                
                print(f"✓ Registered: {path.name}")
                success += 1
                
            except Exception as e:
                print(f"✗ Failed: {path.name} - {e}")
                pipeline.db.add_failed_image(str(path), str(e))
                failed += 1
        
        print()
        print("=" * 70)
        print(f"  Reprocessing Complete")
        print("=" * 70)
        print(f"  Success: {success}")
        print(f"  Failed: {failed}")
        print("=" * 70)
        
        pipeline.close()


if __name__ == "__main__":
    main()

