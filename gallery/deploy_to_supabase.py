#!/usr/bin/env python3
"""
Deploy gallery to Supabase - creates bucket, table, uploads thumbnails.
"""

import sqlite3
from pathlib import Path
from supabase import create_client
from tqdm import tqdm
import concurrent.futures
import time

# Supabase config
SUPABASE_URL = "https://vlmtxakutftzftccizjf.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZsbXR4YWt1dGZ0emZ0Y2NpempmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MjI0ODk4NSwiZXhwIjoyMDc3ODI0OTg1fQ.pqMkNPgj7KGXa53ZWqowbN39VVj0_qAxMUghYwXu4E0"

BUCKET_NAME = "gallery-thumbnails"
TABLE_NAME = "village_gallery"

GALLERY_DIR = Path(__file__).parent
DB_PATH = GALLERY_DIR / "gallery.db"
THUMBNAILS_DIR = GALLERY_DIR / "thumbnails"


def get_visible_images():
    """Get all visible images."""
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


def setup_bucket(supabase):
    """Create bucket if not exists."""
    try:
        buckets = supabase.storage.list_buckets()
        bucket_names = [b.name for b in buckets]
        print(f"Existing buckets: {bucket_names}")

        if BUCKET_NAME not in bucket_names:
            print(f"Creating bucket: {BUCKET_NAME}")
            supabase.storage.create_bucket(BUCKET_NAME, options={"public": True})
            print("Bucket created!")
        else:
            print(f"Bucket {BUCKET_NAME} already exists")
    except Exception as e:
        print(f"Bucket setup error: {e}")


def setup_table(supabase):
    """Create table using RPC or check if exists."""
    # First check if table exists
    try:
        result = supabase.table(TABLE_NAME).select('id').limit(1).execute()
        print(f"Table {TABLE_NAME} exists")
        return True
    except:
        pass

    # Create table via SQL (need to run in dashboard)
    sql = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id INTEGER PRIMARY KEY,
        original_path TEXT,
        thumbnail_url TEXT,
        filename TEXT,
        semantic_score REAL,
        rating INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_rating ON {TABLE_NAME}(rating);
    CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_score ON {TABLE_NAME}(semantic_score);

    ALTER TABLE {TABLE_NAME} ENABLE ROW LEVEL SECURITY;
    CREATE POLICY "Public read" ON {TABLE_NAME} FOR SELECT USING (true);
    CREATE POLICY "Service write" ON {TABLE_NAME} FOR ALL USING (true);
    """
    print("Need to create table. Run this SQL in Supabase dashboard:")
    print("-" * 60)
    print(sql)
    print("-" * 60)
    return False


def upload_image(supabase, img):
    """Upload single image and return record."""
    thumb_path = Path(img['thumbnail_path'])
    if not thumb_path.exists():
        return None

    try:
        filename = f"{img['id']}.jpg"

        with open(thumb_path, 'rb') as f:
            file_data = f.read()

        # Upload to storage
        supabase.storage.from_(BUCKET_NAME).upload(
            filename,
            file_data,
            {"content-type": "image/jpeg", "upsert": "true"}
        )

        thumb_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{filename}"

        return {
            'id': img['id'],
            'original_path': img['original_path'],
            'thumbnail_url': thumb_url,
            'filename': Path(img['original_path']).name,
            'semantic_score': img['semantic_score'],
            'rating': img['rating'] or 0
        }
    except Exception as e:
        if "Duplicate" not in str(e) and "already exists" not in str(e):
            return None
        # Already uploaded, return record anyway
        thumb_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{img['id']}.jpg"
        return {
            'id': img['id'],
            'original_path': img['original_path'],
            'thumbnail_url': thumb_url,
            'filename': Path(img['original_path']).name,
            'semantic_score': img['semantic_score'],
            'rating': img['rating'] or 0
        }


def main():
    print("Connecting to Supabase...")
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Setup
    setup_bucket(supabase)
    table_exists = setup_table(supabase)

    if not table_exists:
        print("\nPlease create the table first, then run again.")
        return

    # Get images
    images = get_visible_images()
    print(f"\nFound {len(images)} visible images to upload")

    # Check already uploaded
    try:
        existing = supabase.table(TABLE_NAME).select('id').execute()
        existing_ids = {r['id'] for r in existing.data}
        print(f"Already in database: {len(existing_ids)}")
        images = [img for img in images if img['id'] not in existing_ids]
        print(f"To upload: {len(images)}")
    except Exception as e:
        print(f"Could not check existing: {e}")
        existing_ids = set()

    if not images:
        print("All images already uploaded!")
        return

    # Upload in batches
    batch_size = 50
    records = []
    failed = 0

    for i in tqdm(range(0, len(images), batch_size), desc="Uploading batches"):
        batch = images[i:i+batch_size]
        batch_records = []

        for img in batch:
            record = upload_image(supabase, img)
            if record:
                batch_records.append(record)
            else:
                failed += 1

        # Insert batch to database
        if batch_records:
            try:
                supabase.table(TABLE_NAME).upsert(batch_records).execute()
                records.extend(batch_records)
            except Exception as e:
                print(f"\nDB insert error: {e}")

        # Small delay to avoid rate limits
        time.sleep(0.1)

    print(f"\n✅ Done! Uploaded: {len(records)}, Failed: {failed}")
    print(f"Total in Supabase: {len(records) + len(existing_ids)}")


if __name__ == "__main__":
    main()
