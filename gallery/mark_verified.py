#!/usr/bin/env python3
"""Mark verified images in Supabase by setting rating=5 for matching filenames."""
import sqlite3
import requests
from pathlib import Path
from tqdm import tqdm

SUPABASE_URL = 'https://vlmtxakutftzftccizjf.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZsbXR4YWt1dGZ0emZ0Y2NpempmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjIyNDg5ODUsImV4cCI6MjA3NzgyNDk4NX0.UpUHvRFIWu4bzweWY4CL47bmnIkWCiM9r-V6d5pwsgs'

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=minimal'
}

def get_verified_filenames():
    """Get filenames from local verified images."""
    conn = sqlite3.connect('/Users/aviz/images-finder/gallery/gallery.db')
    cursor = conn.execute('''
        SELECT original_path FROM gallery_images
        WHERE is_hidden = 0 AND thumbnail_path IS NOT NULL
    ''')
    filenames = set()
    for row in cursor:
        path = row[0]
        filename = Path(path).name.upper()
        filenames.add(filename)
    return filenames

def get_supabase_images():
    """Get all images from Supabase."""
    all_images = []
    offset = 0
    limit = 1000

    while True:
        url = f"{SUPABASE_URL}/rest/v1/settlement_images?select=id,filename&offset={offset}&limit={limit}"
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            print(f"Error fetching: {resp.text}")
            break

        data = resp.json()
        if not data:
            break

        all_images.extend(data)
        offset += limit
        print(f"Fetched {len(all_images)} images...")

    return all_images

def reset_all_ratings():
    """Reset all ratings to null."""
    print("Resetting all ratings to null...")
    url = f"{SUPABASE_URL}/rest/v1/settlement_images?rating=not.is.null"
    resp = requests.patch(url, headers=HEADERS, json={'rating': None})
    print(f"Reset result: {resp.status_code}")

def mark_verified(image_ids):
    """Mark images as verified (rating=5)."""
    print(f"Marking {len(image_ids)} images as verified...")

    # Process in batches
    batch_size = 100
    for i in tqdm(range(0, len(image_ids), batch_size)):
        batch = image_ids[i:i+batch_size]
        # Update each one (Supabase doesn't support bulk update by ID list easily)
        for img_id in batch:
            url = f"{SUPABASE_URL}/rest/v1/settlement_images?id=eq.{img_id}"
            requests.patch(url, headers=HEADERS, json={'rating': 5})

def main():
    print("=" * 50)
    print("Mark Verified Images in Supabase")
    print("=" * 50)

    # Get verified filenames
    verified_filenames = get_verified_filenames()
    print(f"Local verified filenames: {len(verified_filenames)}")

    # Reset all ratings first
    reset_all_ratings()

    # Get Supabase images
    supabase_images = get_supabase_images()
    print(f"Supabase images: {len(supabase_images)}")

    # Find matching images
    matching_ids = []
    for img in supabase_images:
        # Extract base filename (remove hex prefix: "84ea74ff_IL2X0104.JPG" -> "IL2X0104.JPG")
        filename = img['filename']
        parts = filename.split('_', 1)
        if len(parts) > 1:
            base_filename = parts[1].upper()
        else:
            base_filename = filename.upper()

        if base_filename in verified_filenames:
            matching_ids.append(img['id'])

    print(f"Matching images: {len(matching_ids)}")

    # Mark as verified
    mark_verified(matching_ids)

    print("\n✅ Done!")
    print(f"Gallery should now show only {len(matching_ids)} verified images")
    print("Filter by: rating >= 5")

if __name__ == "__main__":
    main()
