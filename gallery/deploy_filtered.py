#!/usr/bin/env python3
"""
Deploy only KEEP (filtered) images to Supabase.
Clears existing data and uploads only visible images.
"""

import sqlite3
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from tqdm import tqdm

GALLERY_DIR = Path(__file__).parent
MAIN_DB = GALLERY_DIR / "gallery.db"
THUMBNAILS_DIR = GALLERY_DIR / "thumbnails"

load_dotenv(GALLERY_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_visible_images():
    """Get only visible (KEEP) images."""
    conn = sqlite3.connect(str(MAIN_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT id, original_path, thumbnail_path, rating
        FROM gallery_images
        WHERE thumbnail_path IS NOT NULL
          AND (is_hidden IS NULL OR is_hidden = 0)
        ORDER BY id
    """)
    images = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return images


def clear_supabase():
    """Clear existing images from Supabase."""
    print("🗑️ Clearing existing Supabase data...")
    try:
        # Delete all from images table
        supabase.table('settlement_images').delete().neq('id', 0).execute()
        print("✅ Cleared images table")
    except Exception as e:
        print(f"⚠️ Clear error: {e}")


def upload_image(img):
    """Upload single image to Supabase storage."""
    thumb_path = THUMBNAILS_DIR / img['thumbnail_path']
    if not thumb_path.exists():
        return None

    storage_path = f"thumbnails/{img['thumbnail_path']}"

    try:
        with open(thumb_path, 'rb') as f:
            supabase.storage.from_('gallery').upload(
                storage_path,
                f.read(),
                {"content-type": "image/jpeg", "upsert": "true"}
            )
        return storage_path
    except Exception as e:
        if "already exists" in str(e) or "Duplicate" in str(e):
            return storage_path
        return None


def main():
    print("=" * 50)
    print("Deploy Filtered Gallery to Supabase")
    print("=" * 50)

    # Get visible images
    images = get_visible_images()
    print(f"📷 Visible (KEEP) images: {len(images)}")

    # Clear existing
    clear_supabase()

    # Upload thumbnails and insert records
    print(f"\n📤 Uploading {len(images)} images...")

    records = []
    for img in tqdm(images, desc="Uploading"):
        storage_path = upload_image(img)
        if storage_path:
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/gallery/{storage_path}"
            records.append({
                'id': img['id'],
                'original_path': img['original_path'],
                'thumbnail_url': public_url,
                'rating': img['rating'] or 0
            })

        # Batch insert every 100
        if len(records) >= 100:
            try:
                supabase.table('settlement_images').upsert(records).execute()
            except Exception as e:
                print(f"⚠️ Insert error: {e}")
            records = []

    # Final batch
    if records:
        try:
            supabase.table('settlement_images').upsert(records).execute()
        except Exception as e:
            print(f"⚠️ Insert error: {e}")

    # Verify
    result = supabase.table('settlement_images').select('id', count='exact').execute()
    print(f"\n✅ Done! Supabase has {result.count} images")


if __name__ == "__main__":
    main()
