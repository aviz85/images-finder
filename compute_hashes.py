#!/usr/bin/env python3
"""Compute perceptual hashes for all existing images."""

from pathlib import Path
from tqdm import tqdm
from src.config import Config, load_config
from src.database import ImageDatabase
from src.image_processor import ImageProcessor

def compute_hashes_for_existing():
    """Compute hashes for all images that don't have one yet."""
    # Load config
    config_path = Path("config.yaml")
    if config_path.exists():
        config = load_config(config_path)
    else:
        config = Config()

    # Initialize database and image processor
    db = ImageDatabase(config.db_path)
    processor = ImageProcessor(config.thumbnails_dir, tuple(config.thumbnail_size))

    # Get all images without hashes
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT id, file_path
        FROM images
        WHERE perceptual_hash IS NULL
    """)
    images = cursor.fetchall()

    print(f"Found {len(images)} images without perceptual hashes")

    if len(images) == 0:
        print("All images already have hashes!")
        return

    # Compute hashes
    success = 0
    failed = 0

    for img in tqdm(images, desc="Computing hashes"):
        try:
            file_path = Path(img['file_path'])
            if not file_path.exists():
                print(f"\nWarning: File not found: {file_path}")
                failed += 1
                continue

            # Compute hash
            phash = processor.compute_perceptual_hash(file_path)

            if phash:
                # Update database
                cursor.execute("""
                    UPDATE images
                    SET perceptual_hash = ?
                    WHERE id = ?
                """, (phash, img['id']))
                success += 1
            else:
                failed += 1

        except Exception as e:
            print(f"\nError processing {img['file_path']}: {e}")
            failed += 1

    db.conn.commit()

    print(f"\nComputed hashes for {success} images ({failed} failed)")

    # Now detect and mark duplicates
    print("\nDetecting duplicates...")
    num_duplicates = db.mark_duplicates(hash_threshold=5)
    print(f"Found and marked {num_duplicates} duplicate images")

    # Show duplicate groups
    groups = db.get_duplicate_groups()
    if groups:
        print(f"\n{len(groups)} original images have duplicates:")
        for orig_id, dup_ids in groups.items():
            cursor.execute("SELECT file_name FROM images WHERE id = ?", (orig_id,))
            orig_name = cursor.fetchone()['file_name']
            print(f"  {orig_name} (ID {orig_id}): {len(dup_ids)} duplicate(s)")

    db.close()


if __name__ == "__main__":
    compute_hashes_for_existing()
