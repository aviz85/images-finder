#!/usr/bin/env python3
"""
Create sample collages from KEEP-classified images.
"""

import sqlite3
import random
from pathlib import Path
from PIL import Image
import math

GALLERY_DIR = Path(__file__).parent.parent
CLASS_DB = GALLERY_DIR / "reindex" / "classification.db"
THUMBNAILS_DIR = GALLERY_DIR / "thumbnails"
OUTPUT_DIR = GALLERY_DIR / "reindex" / "collages"

def get_keep_images():
    """Get all KEEP-classified images sorted by confidence."""
    conn = sqlite3.connect(str(CLASS_DB))
    rows = conn.execute("""
        SELECT thumbnail_path, confidence
        FROM image_classification
        WHERE classification='KEEP'
        ORDER BY confidence DESC
    """).fetchall()
    conn.close()
    return rows

def create_collage(images, output_path, grid_size=3, thumb_size=300):
    """Create a grid collage from images."""
    collage_size = grid_size * thumb_size
    collage = Image.new('RGB', (collage_size, collage_size), (30, 30, 30))

    for i, img_path in enumerate(images[:grid_size*grid_size]):
        row = i // grid_size
        col = i % grid_size

        full_path = THUMBNAILS_DIR / img_path
        if not full_path.exists():
            continue

        try:
            img = Image.open(full_path).convert('RGB')
            # Resize to square
            img.thumbnail((thumb_size, thumb_size))
            # Center in cell
            x = col * thumb_size + (thumb_size - img.width) // 2
            y = row * thumb_size + (thumb_size - img.height) // 2
            collage.paste(img, (x, y))
        except Exception as e:
            print(f"  Skip {img_path}: {e}")

    collage.save(output_path, quality=85)
    return output_path

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Get KEEP images
    keep_images = get_keep_images()
    print(f"📷 KEEP images: {len(keep_images)}")

    # Create 10 collages with different samples
    collage_paths = []

    # Top confidence (best matches)
    for i in range(5):
        start = i * 9
        images = [r[0] for r in keep_images[start:start+9]]
        path = OUTPUT_DIR / f"collage_top_{i+1}.jpg"
        create_collage(images, path)
        collage_paths.append(path)
        print(f"✅ Created {path.name}")

    # Random samples
    random.seed(42)
    remaining = [r[0] for r in keep_images[45:]]
    for i in range(5):
        sample = random.sample(remaining, min(9, len(remaining)))
        path = OUTPUT_DIR / f"collage_random_{i+1}.jpg"
        create_collage(sample, path)
        collage_paths.append(path)
        print(f"✅ Created {path.name}")

    print(f"\n📁 Collages saved to: {OUTPUT_DIR}")
    for p in collage_paths:
        print(f"   {p}")

if __name__ == "__main__":
    main()
