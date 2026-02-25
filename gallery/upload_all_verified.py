#!/usr/bin/env python3
"""Upload all verified thumbnails to Supabase, replacing settlement_images table."""
import sqlite3
from pathlib import Path
from supabase import create_client
from tqdm import tqdm
import uuid
import hashlib

GALLERY_DIR = Path(__file__).parent
DB_PATH = GALLERY_DIR / "gallery.db"
THUMBNAILS_DIR = GALLERY_DIR / "thumbnails"

SUPABASE_URL = 'https://vlmtxakutftzftccizjf.supabase.co'
SERVICE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZsbXR4YWt1dGZ0emZ0Y2NpempmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MjI0ODk4NSwiZXhwIjoyMDc3ODI0OTg1fQ.pqMkNPgj7KGXa53ZWqowbN39VVj0_qAxMUghYwXu4E0'

supabase = create_client(SUPABASE_URL, SERVICE_KEY)

def get_verified_images():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT id, original_path, thumbnail_path, rating
        FROM gallery_images
        WHERE is_hidden = 0 AND thumbnail_path IS NOT NULL
        ORDER BY id
    """)
    images = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return images

def get_thumb_path(thumbnail_path):
    """Handle both formats: 'hash.jpg' and 'thumbnails/thumb_123.jpg'"""
    if thumbnail_path.startswith('thumbnails/'):
        return GALLERY_DIR / thumbnail_path
    else:
        return THUMBNAILS_DIR / thumbnail_path

def main():
    print("=" * 50)
    print("Insert Records into Supabase (thumbnails already uploaded)")
    print("=" * 50)

    images = get_verified_images()
    print(f"Found {len(images)} verified images")

    # Clear existing settlement_images
    print("\nClearing existing data...")
    try:
        supabase.table('settlement_images').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        print("Cleared!")
    except Exception as e:
        print(f"Clear error: {e}")

    print("\nInserting records...")

    records = []
    for img in tqdm(images, desc="Preparing"):
        thumb_path = get_thumb_path(img['thumbnail_path'])
        if not thumb_path.exists():
            continue

        thumb_filename = thumb_path.name
        storage_path = f"verified/{thumb_filename}"
        filename = Path(img['original_path']).name

        # Generate unique hex_id from original_path hash
        hex_id = hashlib.md5(img['original_path'].encode()).hexdigest()[:8]

        records.append({
            'id': str(uuid.uuid4()),
            'hex_id': hex_id,
            'filename': filename,
            'original_path': img['original_path'],
            'storage_path': storage_path,
            'rating': 5,
        })

    print(f"\nInserting {len(records)} records in batches...")

    inserted = 0
    for i in tqdm(range(0, len(records), 100), desc="Inserting"):
        batch = records[i:i+100]
        try:
            supabase.table('settlement_images').insert(batch).execute()
            inserted += len(batch)
        except Exception as e:
            print(f"\nInsert error at {i}: {e}")

    print(f"\n{'='*50}")
    print(f"Inserted: {inserted}")

    # Verify count
    result = supabase.table('settlement_images').select('id', count='exact').execute()
    print(f"Supabase settlement_images: {result.count} records")

if __name__ == "__main__":
    main()
