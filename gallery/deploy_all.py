#!/usr/bin/env python3
"""
Full deployment: create bucket, table, upload thumbnails to Supabase.
"""

import sqlite3
from pathlib import Path
from supabase import create_client
from tqdm import tqdm
import time
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://zvmeqrttfldvcvgzftyn.supabase.co")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

BUCKET_NAME = "thumbnails"
TABLE_NAME = "images"

GALLERY_DIR = Path(__file__).parent
DB_PATH = GALLERY_DIR / "gallery.db"
THUMBNAILS_DIR = GALLERY_DIR / "thumbnails"


def get_visible_images():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT id, original_path, thumbnail_path, semantic_score, rating
        FROM gallery_images
        WHERE thumbnail_path IS NOT NULL
          AND (is_hidden IS NULL OR is_hidden = 0)
        ORDER BY semantic_score DESC
    """)
    images = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return images


def main():
    print("=" * 60)
    print("Gallery Deployment to Supabase")
    print("=" * 60)

    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Get images
    images = get_visible_images()
    print(f"📷 Found {len(images)} visible images")

    # Check already uploaded
    try:
        existing = supabase.table(TABLE_NAME).select('id').execute()
        existing_ids = {r['id'] for r in existing.data}
        print(f"✅ Already in DB: {len(existing_ids)}")
        images = [img for img in images if img['id'] not in existing_ids]
        print(f"📤 To process: {len(images)}")
    except Exception as e:
        print(f"DB check failed: {e}")
        existing_ids = set()

    if not images:
        print("\n✅ All done!")
        return

    # Upload
    uploaded = 0
    failed = 0
    records = []

    for img in tqdm(images, desc="Uploading"):
        # thumbnail_path is just filename, prepend directory
        thumb_path = THUMBNAILS_DIR / img['thumbnail_path']
        if not thumb_path.exists():
            failed += 1
            continue

        try:
            filename = f"{img['id']}.jpg"

            with open(thumb_path, 'rb') as f:
                file_data = f.read()

            # Upload to storage
            supabase.storage.from_(BUCKET_NAME).upload(
                filename, file_data,
                {"content-type": "image/jpeg"}
            )

            thumb_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{filename}"

            records.append({
                'id': img['id'],
                'original_path': img['original_path'],
                'thumbnail_url': thumb_url,
                'filename': Path(img['original_path']).name,
                'semantic_score': img['semantic_score'],
                'rating': img['rating'] or 0
            })
            uploaded += 1

            # Batch insert every 100
            if len(records) >= 100:
                supabase.table(TABLE_NAME).upsert(records).execute()
                records = []

        except Exception as e:
            err = str(e)
            if "Duplicate" in err or "already exists" in err.lower():
                # Already uploaded, just add to DB
                thumb_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{img['id']}.jpg"
                records.append({
                    'id': img['id'],
                    'original_path': img['original_path'],
                    'thumbnail_url': thumb_url,
                    'filename': Path(img['original_path']).name,
                    'semantic_score': img['semantic_score'],
                    'rating': img['rating'] or 0
                })
                uploaded += 1
                if len(records) >= 100:
                    supabase.table(TABLE_NAME).upsert(records).execute()
                    records = []
            else:
                failed += 1
                if failed < 5:
                    tqdm.write(f"Error: {err[:100]}")

    # Final batch
    if records:
        supabase.table(TABLE_NAME).upsert(records).execute()

    print(f"\n✅ Done! Uploaded: {uploaded}, Failed: {failed}")

    # Verify
    count = supabase.table(TABLE_NAME).select('id', count='exact').execute()
    print(f"📊 Total in Supabase: {count.count}")


if __name__ == "__main__":
    main()
