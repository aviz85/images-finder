#!/usr/bin/env python3
"""Upload only verified (visible) images to Supabase."""
import sqlite3
import os
from pathlib import Path
from supabase import create_client
from tqdm import tqdm

GALLERY_DIR = Path(__file__).parent
DB_PATH = GALLERY_DIR / "gallery.db"
THUMBNAILS_DIR = GALLERY_DIR / "thumbnails"

SUPABASE_URL = 'https://vlmtxakutftzftccizjf.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZsbXR4YWt1dGZ0emZ0Y2NpempmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjIyNDg5ODUsImV4cCI6MjA3NzgyNDk4NX0.UpUHvRFIWu4bzweWY4CL47bmnIkWCiM9r-V6d5pwsgs'

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_verified_images():
    """Get only visible images from local DB."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT id, original_path, thumbnail_path, rating, semantic_score
        FROM gallery_images
        WHERE is_hidden = 0 AND thumbnail_path IS NOT NULL
        ORDER BY id
    """)
    images = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return images

def main():
    print("=" * 50)
    print("Upload Verified Images to Supabase")
    print("=" * 50)

    images = get_verified_images()
    print(f"Found {len(images)} verified images")

    # Clear existing verified_gallery table
    print("\nClearing existing data...")
    try:
        supabase.table('verified_gallery').delete().neq('id', 0).execute()
    except Exception as e:
        print(f"Table may not exist yet: {e}")

    # Upload thumbnails and create records
    print(f"\nUploading {len(images)} images...")

    records = []
    uploaded = 0

    for img in tqdm(images, desc="Processing"):
        thumb_path = THUMBNAILS_DIR / img['thumbnail_path']
        if not thumb_path.exists():
            continue

        storage_path = f"verified/{img['thumbnail_path']}"

        # Upload to storage
        try:
            with open(thumb_path, 'rb') as f:
                supabase.storage.from_('settlement-images').upload(
                    storage_path,
                    f.read(),
                    {"content-type": "image/jpeg", "upsert": "true"}
                )
            uploaded += 1
        except Exception as e:
            if "already exists" not in str(e).lower() and "duplicate" not in str(e).lower():
                continue
            uploaded += 1  # Already exists is ok

        # Create record
        records.append({
            'id': img['id'],
            'original_path': img['original_path'],
            'storage_path': storage_path,
            'rating': img['rating'],
            'semantic_score': img['semantic_score']
        })

        # Batch insert every 100
        if len(records) >= 100:
            try:
                supabase.table('verified_gallery').upsert(records).execute()
            except Exception as e:
                print(f"\nInsert error: {e}")
            records = []

    # Final batch
    if records:
        try:
            supabase.table('verified_gallery').upsert(records).execute()
        except Exception as e:
            print(f"\nFinal insert error: {e}")

    print(f"\n✅ Uploaded {uploaded} thumbnails")

    # Verify
    try:
        result = supabase.table('verified_gallery').select('id', count='exact').execute()
        print(f"✅ Supabase verified_gallery has {result.count} images")
    except:
        print("Could not verify count")

if __name__ == "__main__":
    main()
