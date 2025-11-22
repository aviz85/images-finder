#!/usr/bin/env python3
"""Simple status server for monitoring processing progress."""

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import sqlite3
from pathlib import Path
import uvicorn

app = FastAPI(title="Image Processing Status")

# Configuration
DB_PATH = "/Volumes/My Book/images-finder-data/metadata.db"
STATIC_DIR = Path(__file__).parent / "static"

@app.get("/")
async def root():
    """Redirect to status page."""
    return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <meta http-equiv="refresh" content="0; url=/status.html">
        </head>
        <body>
            Redirecting to status page...
        </body>
        </html>
    """)

@app.get("/stats")
async def get_stats():
    """Get processing statistics."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout for locks
        cur = conn.cursor()
        
        # Total images
        cur.execute('SELECT COUNT(*) FROM images')
        total_images = cur.fetchone()[0]
        
        # Processed (with embeddings)
        cur.execute('SELECT COUNT(*) FROM images WHERE embedding_index IS NOT NULL')
        processed_images = cur.fetchone()[0]
        
        # Failed
        cur.execute('SELECT COUNT(*) FROM failed_images')
        failed_images = cur.fetchone()[0]
        
        # SHA-256 hash progress
        cur.execute('SELECT COUNT(*) FROM images WHERE sha256_hash IS NOT NULL')
        with_sha256 = cur.fetchone()[0]
        
        # Perceptual hash progress  
        cur.execute('SELECT COUNT(*) FROM images WHERE perceptual_hash IS NOT NULL')
        with_phash = cur.fetchone()[0]
        
        # SHA-256 duplicates (exact copies)
        try:
            cur.execute('''
                SELECT COUNT(*) FROM (
                    SELECT sha256_hash 
                    FROM images 
                    WHERE sha256_hash IS NOT NULL
                    GROUP BY sha256_hash 
                    HAVING COUNT(*) > 1
                )
            ''')
            sha256_dup_groups = cur.fetchone()[0]
            
            cur.execute('''
                SELECT SUM(cnt - 1) FROM (
                    SELECT COUNT(*) as cnt
                    FROM images 
                    WHERE sha256_hash IS NOT NULL
                    GROUP BY sha256_hash 
                    HAVING COUNT(*) > 1
                )
            ''')
            sha256_duplicates = cur.fetchone()[0] or 0
        except:
            sha256_dup_groups = 0
            sha256_duplicates = 0
        
        # Perceptual duplicates (visual matches)
        try:
            cur.execute('''
                SELECT COUNT(*) FROM (
                    SELECT perceptual_hash 
                    FROM images 
                    WHERE perceptual_hash IS NOT NULL
                    GROUP BY perceptual_hash 
                    HAVING COUNT(*) > 1
                )
            ''')
            phash_dup_groups = cur.fetchone()[0]
            
            cur.execute('''
                SELECT SUM(cnt - 1) FROM (
                    SELECT COUNT(*) as cnt
                    FROM images 
                    WHERE perceptual_hash IS NOT NULL
                    GROUP BY perceptual_hash 
                    HAVING COUNT(*) > 1
                )
            ''')
            phash_duplicates = cur.fetchone()[0] or 0
        except:
            phash_dup_groups = 0
            phash_duplicates = 0
        
        conn.close()
        
        return {
            "total_images": total_images,
            "processed_images": processed_images,
            "failed_images": failed_images,
            "with_sha256": with_sha256,
            "with_phash": with_phash,
            "sha256_duplicate_groups": sha256_dup_groups,
            "sha256_duplicates": sha256_duplicates,
            "phash_duplicate_groups": phash_dup_groups,
            "phash_duplicates": phash_duplicates,
            "index_ready": False
        }
    except Exception as e:
        return {
            "total_images": 0,
            "processed_images": 0,
            "failed_images": 0,
            "with_sha256": 0,
            "with_phash": 0,
            "sha256_duplicate_groups": 0,
            "sha256_duplicates": 0,
            "phash_duplicate_groups": 0,
            "phash_duplicates": 0,
            "index_ready": False,
            "error": str(e)
        }

# Mount static files
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    print("=" * 60)
    print("  IMAGE PROCESSING STATUS SERVER")
    print("=" * 60)
    print("")
    print("✓ Starting server...")
    print("")
    print("📊 Status Dashboard:")
    print("   http://localhost:8000/status.html")
    print("")
    print("🔌 API Endpoint:")
    print("   http://localhost:8000/stats")
    print("")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print("")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

