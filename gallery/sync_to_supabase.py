#!/usr/bin/env python3
"""
Sync gallery images to Supabase for Vercel deployment.
Uploads thumbnails to storage, syncs metadata to database.
"""

import os
import sqlite3
from pathlib import Path
from supabase import create_client
from tqdm import tqdm
import hashlib

# Supabase config (same as settlement-gallery)
SUPABASE_URL = 'https://vlmtxakutftzftccizjf.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZsbXR4YWt1dGZ0emZ0Y2NpempmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjIyNDg5ODUsImV4cCI6MjA3NzgyNDk4NX0.UpUHvRFIWu4bzweWY4CL47bmnIkWCiM9r-V6d5pwsgs'

# Use service role key for uploads (need to get from env)
SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', SUPABASE_KEY)

BUCKET_NAME = 'gallery-images'
TABLE_NAME = 'gallery_images'

GALLERY_DIR = Path(__file__).parent
DB_PATH = GALLERY_DIR / "gallery.db"
THUMBNAILS_DIR = GALLERY_DIR / "thumbnails"


def get_visible_images():
    """Get all visible (non-hidden) images."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT id, original_path, thumbnail_path, semantic_score, rating,
               width, height, file_size
        FROM gallery_images
        WHERE thumbnail_path IS NOT NULL
          AND (is_hidden IS NULL OR is_hidden = 0)
        ORDER BY semantic_score DESC
    """)
    images = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return images


def main():
    print("Connecting to Supabase...")
    supabase = create_client(SUPABASE_URL, SERVICE_KEY)

    # Get visible images
    images = get_visible_images()
    print(f"Found {len(images)} visible images to sync")

    # Check existing uploads
    print("Checking existing uploads...")
    try:
        existing = supabase.table(TABLE_NAME).select('id').execute()
        existing_ids = {row['id'] for row in existing.data}
        print(f"Already synced: {len(existing_ids)}")
    except Exception as e:
        print(f"Table might not exist, will create: {e}")
        existing_ids = set()

    # Upload new images
    uploaded = 0
    failed = 0

    for img in tqdm(images, desc="Syncing"):
        if img['id'] in existing_ids:
            continue

        try:
            # Upload thumbnail to storage
            thumb_path = Path(img['thumbnail_path'])
            if thumb_path.exists():
                with open(thumb_path, 'rb') as f:
                    file_data = f.read()

                # Use hash as filename for uniqueness
                filename = f"{img['id']}_{thumb_path.name}"

                # Upload to storage
                supabase.storage.from_(BUCKET_NAME).upload(
                    filename,
                    file_data,
                    {'content-type': 'image/jpeg'}
                )

                # Get public URL
                thumb_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{filename}"
            else:
                thumb_url = None

            # Insert to database
            supabase.table(TABLE_NAME).upsert({
                'id': img['id'],
                'original_path': img['original_path'],
                'thumbnail_url': thumb_url,
                'semantic_score': img['semantic_score'],
                'rating': img['rating'] or 0,
                'width': img['width'],
                'height': img['height'],
                'file_size': img['file_size'],
                'filename': Path(img['original_path']).name
            }).execute()

            uploaded += 1

        except Exception as e:
            failed += 1
            if failed < 5:
                print(f"\nError: {e}")

    print(f"\nDone! Uploaded: {uploaded}, Failed: {failed}")


if __name__ == "__main__":
    main()
