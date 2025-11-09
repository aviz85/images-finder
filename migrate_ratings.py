#!/usr/bin/env python3
"""
Migrate existing ratings to canonical images.

This script consolidates ratings from duplicate images to their canonical (original) images.
Strategy: Keep the most recent rating (based on updated_at timestamp).
"""

from pathlib import Path
from datetime import datetime
from src.config import Config, load_config
from src.database import ImageDatabase


def migrate_ratings():
    """Consolidate ratings from duplicates to canonical images."""
    config_path = Path("config.yaml")
    if config_path.exists():
        config = load_config(config_path)
    else:
        config = Config()

    db = ImageDatabase(config.db_path)
    cursor = db.conn.cursor()

    print("=" * 60)
    print("RATING MIGRATION SCRIPT")
    print("=" * 60)
    print()

    # Step 1: Find all images with ratings
    cursor.execute("""
        SELECT r.id as rating_id, r.image_id, r.rating, r.comment,
               r.created_at, r.updated_at,
               i.is_duplicate, i.duplicate_of, i.file_name
        FROM ratings r
        JOIN images i ON r.image_id = i.id
        ORDER BY r.image_id
    """)
    all_ratings = cursor.fetchall()

    print(f"Total ratings in database: {len(all_ratings)}")

    # Count ratings on duplicates
    duplicate_ratings = [r for r in all_ratings if r['is_duplicate'] == 1]
    print(f"Ratings on duplicate images: {len(duplicate_ratings)}")
    print()

    if len(duplicate_ratings) == 0:
        print("✅ No ratings on duplicates found. Migration not needed!")
        db.close()
        return

    # Step 2: Process each duplicate rating
    print("Processing duplicate ratings...")
    print()

    migrated_count = 0
    deleted_count = 0
    conflict_count = 0

    for dup_rating in duplicate_ratings:
        duplicate_id = dup_rating['image_id']
        canonical_id = dup_rating['duplicate_of']

        # Check if canonical image already has a rating
        cursor.execute("""
            SELECT id, rating, comment, updated_at
            FROM ratings
            WHERE image_id = ?
        """, (canonical_id,))
        canonical_rating = cursor.fetchone()

        if canonical_rating:
            # Conflict: both duplicate and canonical have ratings
            # Keep the most recent one
            dup_updated = datetime.fromisoformat(dup_rating['updated_at'])
            can_updated = datetime.fromisoformat(canonical_rating['updated_at'])

            if dup_updated > can_updated:
                # Duplicate rating is newer, update canonical
                print(f"⚠️  Conflict for image ID {canonical_id} (keeping newer rating)")
                print(f"   Duplicate rating (ID {duplicate_id}): {dup_rating['rating']} stars - {dup_updated}")
                print(f"   Canonical rating (ID {canonical_id}): {canonical_rating['rating']} stars - {can_updated}")
                print(f"   → Keeping duplicate's rating (newer)")

                cursor.execute("""
                    UPDATE ratings
                    SET rating = ?, comment = ?, updated_at = ?
                    WHERE image_id = ?
                """, (dup_rating['rating'], dup_rating['comment'],
                      dup_rating['updated_at'], canonical_id))

                conflict_count += 1
            else:
                # Canonical rating is newer or same, keep it
                print(f"⚠️  Conflict for image ID {canonical_id} (keeping existing rating)")
                print(f"   Duplicate rating (ID {duplicate_id}): {dup_rating['rating']} stars - {dup_updated}")
                print(f"   Canonical rating (ID {canonical_id}): {canonical_rating['rating']} stars - {can_updated}")
                print(f"   → Keeping canonical's rating (newer or same)")
                conflict_count += 1

            # Delete duplicate's rating (it's been merged or discarded)
            cursor.execute("DELETE FROM ratings WHERE image_id = ?", (duplicate_id,))
            deleted_count += 1
        else:
            # No conflict: move duplicate rating to canonical
            print(f"✓ Migrating rating from duplicate ID {duplicate_id} to canonical ID {canonical_id}")
            print(f"  {dup_rating['file_name']}: {dup_rating['rating']} stars")

            cursor.execute("""
                UPDATE ratings
                SET image_id = ?
                WHERE image_id = ?
            """, (canonical_id, duplicate_id))

            migrated_count += 1

        print()

    # Commit all changes
    db.conn.commit()

    # Step 3: Summary
    print("=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"✓ Migrated (moved to canonical): {migrated_count}")
    print(f"✓ Conflicts resolved: {conflict_count}")
    print(f"✓ Duplicate ratings deleted: {deleted_count}")
    print()

    # Verify final state
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM ratings r
        JOIN images i ON r.image_id = i.id
        WHERE i.is_duplicate = 1
    """)
    remaining = cursor.fetchone()['count']

    if remaining == 0:
        print("✅ SUCCESS: No ratings on duplicate images remain!")
    else:
        print(f"⚠️  WARNING: {remaining} ratings on duplicates still exist (this shouldn't happen)")

    # Show final counts
    cursor.execute("SELECT COUNT(*) as count FROM ratings")
    total_ratings = cursor.fetchone()['count']
    print(f"\nTotal ratings after migration: {total_ratings}")

    db.close()


if __name__ == "__main__":
    migrate_ratings()
