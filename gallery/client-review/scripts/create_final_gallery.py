#!/usr/bin/env python3
"""
Create final gallery with all approved images.
Deploys to Vercel with only the good images.
"""
import sqlite3
import re
from pathlib import Path
from dotenv import load_dotenv
import os

BASE = Path(__file__).parent.parent
GALLERY = BASE.parent

def load_ids(filename):
    """Load IDs from text file."""
    text = (BASE / filename).read_text()
    return set(int(x) for x in re.findall(r'\d+', text))

def main():
    print("=" * 50)
    print("Creating Final Gallery")
    print("=" * 50)

    # Load approved IDs
    approved = load_ids('approved_ids.txt')
    print(f"✅ Approved images: {len(approved)}")

    # Update gallery database
    main_db = GALLERY / 'gallery.db'
    conn = sqlite3.connect(str(main_db))

    # First, hide all
    conn.execute("UPDATE gallery_images SET is_hidden = 1 WHERE thumbnail_path IS NOT NULL")

    # Then, show only approved
    placeholders = ','.join('?' * len(approved))
    conn.execute(f"""
        UPDATE gallery_images
        SET is_hidden = 0
        WHERE id IN ({placeholders})
    """, list(approved))
    conn.commit()

    # Verify
    visible = conn.execute("""
        SELECT COUNT(*) FROM gallery_images
        WHERE is_hidden = 0 AND thumbnail_path IS NOT NULL
    """).fetchone()[0]
    conn.close()

    print(f"📷 Gallery now has {visible} visible images")

    # Ask about Vercel deployment
    print("\n" + "=" * 50)
    print("Next steps:")
    print("1. Run deploy script: python gallery/deploy_filtered.py")
    print("2. Deploy to Vercel: cd gallery/vercel-deploy && vercel --prod")
    print("=" * 50)

if __name__ == "__main__":
    main()
