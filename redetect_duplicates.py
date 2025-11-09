#!/usr/bin/env python3
"""
Re-detect duplicates with a different threshold.

This script re-runs duplicate detection without recomputing hashes.
Edit duplicate_hash_threshold in config.yaml to change the threshold.
"""

from pathlib import Path
from src.config import Config, load_config
from src.database import ImageDatabase


def redetect_duplicates():
    """Re-detect duplicates using current config threshold."""
    # Load config
    config_path = Path("config.yaml")
    if config_path.exists():
        config = load_config(config_path)
    else:
        config = Config()

    # Initialize database
    db = ImageDatabase(config.db_path)
    cursor = db.conn.cursor()

    # Get current threshold
    threshold = config.duplicate_hash_threshold
    similarity_pct = (64 - threshold) / 64 * 100

    print("=" * 60)
    print("RE-DETECTING DUPLICATES")
    print("=" * 60)
    print(f"Threshold: {threshold} hamming distance (≈{similarity_pct:.1f}% similarity)")
    print()

    # Clear existing duplicate markings
    print("Clearing existing duplicate markings...")
    cursor.execute("""
        UPDATE images
        SET is_duplicate = 0, duplicate_of = NULL
        WHERE is_duplicate = 1
    """)
    db.conn.commit()

    # Re-detect duplicates
    print("Detecting duplicates...")
    num_duplicates = db.mark_duplicates(hash_threshold=threshold)
    print(f"Found and marked {num_duplicates} duplicate images")
    print()

    # Show duplicate groups
    groups = db.get_duplicate_groups()
    if groups:
        print(f"{len(groups)} original images have duplicates:")
        for orig_id, dup_ids in groups.items():
            cursor.execute("SELECT file_name FROM images WHERE id = ?", (orig_id,))
            orig_name = cursor.fetchone()['file_name']
            print(f"  {orig_name} (ID {orig_id}): {len(dup_ids)} duplicate(s)")
    else:
        print("No duplicates found!")

    print()
    print("=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print()
    print("Threshold guide:")
    print("  0 = 100% identical")
    print("  5 = ~92% similar (default)")
    print("  10 = ~84% similar")
    print("  15 = ~77% similar")
    print()
    print("To change: Edit 'duplicate_hash_threshold' in config.yaml")

    db.close()


if __name__ == "__main__":
    redetect_duplicates()
