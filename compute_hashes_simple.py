#!/usr/bin/env python3
"""Compute SHA-256 and perceptual hashes for all existing images."""

import sqlite3
import hashlib
from pathlib import Path
from PIL import Image
import imagehash
import time
from datetime import timedelta

DB_PATH = "/Volumes/My Book/images-finder-data/metadata.db"

def compute_perceptual_hash(file_path):
    """Compute perceptual hash."""
    try:
        with Image.open(file_path) as img:
            phash = imagehash.phash(img, hash_size=8)
            return str(phash)
    except Exception as e:
        print(f"Error computing perceptual hash for {file_path}: {e}")
        return None

def compute_sha256(file_path):
    """Compute SHA-256 hash."""
    try:
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        print(f"Error computing SHA-256 for {file_path}: {e}")
        return None

def update_hashes():
    """Update hashes for all images."""
    
    print("Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Set long timeout for concurrent access
    conn.execute("PRAGMA busy_timeout = 60000")
    
    cursor = conn.cursor()
    
    # Get images that need hash updates
    cursor.execute("""
        SELECT id, file_path, perceptual_hash, sha256_hash
        FROM images
        WHERE sha256_hash IS NULL
    """)
    
    images = cursor.fetchall()
    total = len(images)
    
    print(f"Found {total} images needing SHA-256 hash")
    
    if total == 0:
        print("All images already have SHA-256 hashes!")
        return
    
    processed = 0
    failed = 0
    start_time = time.time()
    
    for img in images:
        img_id = img['id']
        file_path = img['file_path']
        
        try:
            # Compute SHA-256 (always needed)
            sha256_hash = compute_sha256(file_path)
            
            # Update perceptual hash to phash (if old average_hash exists, recompute)
            perceptual_hash = compute_perceptual_hash(file_path)
            
            # Update database with retry logic
            for attempt in range(5):
                try:
                    update_cursor = conn.cursor()
                    update_cursor.execute("""
                        UPDATE images
                        SET perceptual_hash = ?, sha256_hash = ?
                        WHERE id = ?
                    """, (perceptual_hash, sha256_hash, img_id))
                    conn.commit()
                    break
                except sqlite3.OperationalError as e:
                    if "locked" in str(e) and attempt < 4:
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    raise
            
            processed += 1
            
            # Progress update
            if processed % 100 == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed
                remaining = total - processed
                eta_seconds = remaining / rate if rate > 0 else 0
                eta = timedelta(seconds=int(eta_seconds))
                print(f"Progress: {processed}/{total} ({processed/total*100:.1f}%) | Rate: {rate:.1f} img/s | ETA: {eta}")
            
        except Exception as e:
            print(f"Failed to process {file_path}: {e}")
            failed += 1
    
    conn.close()
    
    total_time = time.time() - start_time
    print("")
    print("=" * 60)
    print(f"✓ Complete in {timedelta(seconds=int(total_time))}")
    print(f"  Processed: {processed}")
    print(f"  Failed: {failed}")
    print(f"  Rate: {processed/total_time:.1f} img/s")
    print("=" * 60)

if __name__ == "__main__":
    print("=" * 60)
    print("  Computing SHA-256 & Perceptual Hashes")
    print("=" * 60)
    print("")
    
    update_hashes()



