#!/usr/bin/env python3
"""
Apply classification results - hide REMOVE images from gallery.
"""

import sqlite3
from pathlib import Path

GALLERY_DIR = Path(__file__).parent.parent
MAIN_DB = GALLERY_DIR / "gallery.db"
CLASS_DB = GALLERY_DIR / "reindex" / "classification.db"


def apply_classification():
    """Mark REMOVE-classified images as hidden."""

    # Get REMOVE image IDs
    class_conn = sqlite3.connect(str(CLASS_DB))
    remove_ids = [r[0] for r in class_conn.execute(
        "SELECT id FROM image_classification WHERE classification='REMOVE'"
    ).fetchall()]
    class_conn.close()

    print(f"📊 REMOVE images to hide: {len(remove_ids)}")

    # Get current hidden count
    main_conn = sqlite3.connect(str(MAIN_DB))
    before_hidden = main_conn.execute(
        "SELECT COUNT(*) FROM gallery_images WHERE is_hidden = 1"
    ).fetchone()[0]
    print(f"📊 Currently hidden: {before_hidden}")

    # Update in batches
    batch_size = 500
    updated = 0

    for i in range(0, len(remove_ids), batch_size):
        batch = remove_ids[i:i+batch_size]
        placeholders = ','.join('?' * len(batch))
        main_conn.execute(f"""
            UPDATE gallery_images
            SET is_hidden = 1
            WHERE id IN ({placeholders})
        """, batch)
        main_conn.commit()
        updated += len(batch)
        print(f"  Hidden: {updated}/{len(remove_ids)}")

    # Final counts
    after_hidden = main_conn.execute(
        "SELECT COUNT(*) FROM gallery_images WHERE is_hidden = 1"
    ).fetchone()[0]
    visible = main_conn.execute(
        "SELECT COUNT(*) FROM gallery_images WHERE thumbnail_path IS NOT NULL AND (is_hidden IS NULL OR is_hidden = 0)"
    ).fetchone()[0]
    main_conn.close()

    print(f"\n✅ Done!")
    print(f"   Hidden before: {before_hidden}")
    print(f"   Hidden after: {after_hidden}")
    print(f"   Visible now: {visible}")


if __name__ == "__main__":
    apply_classification()
