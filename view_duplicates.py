#!/usr/bin/env python3
"""Generate HTML page to visually inspect duplicate images."""

import sqlite3
from pathlib import Path
import base64
from PIL import Image
import io

DB_PATH = "/Volumes/My Book/images-finder-data/metadata.db"
OUTPUT_HTML = "/Users/aviz/images-finder/duplicates_viewer.html"

def get_duplicate_groups(limit=50, min_size=2, max_size=20):
    """Get duplicate groups from database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Get duplicate groups
    cur.execute(f"""
        SELECT perceptual_hash, COUNT(*) as count
        FROM images 
        WHERE perceptual_hash IS NOT NULL 
        GROUP BY perceptual_hash 
        HAVING COUNT(*) BETWEEN ? AND ?
        ORDER BY COUNT(*) DESC
        LIMIT ?
    """, (min_size, max_size, limit))
    
    hashes = cur.fetchall()
    
    groups = []
    for phash, count in hashes:
        # Get all images in this group
        cur.execute("""
            SELECT file_path, file_name, width, height
            FROM images
            WHERE perceptual_hash = ?
            ORDER BY file_path
        """, (phash,))
        
        images = cur.fetchall()
        groups.append({
            'hash': phash,
            'count': count,
            'images': images
        })
    
    conn.close()
    return groups

def image_to_base64(image_path, max_size=400):
    """Convert image to base64 for HTML embedding."""
    try:
        img = Image.open(image_path)
        
        # Resize for display
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # Convert to JPEG in memory
        buffer = io.BytesIO()
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        img.save(buffer, format='JPEG', quality=85)
        img_data = buffer.getvalue()
        
        # Encode to base64
        return base64.b64encode(img_data).decode('utf-8')
    except Exception as e:
        print(f"Error loading {image_path}: {e}")
        return None

def generate_html(groups, max_images_per_group=10):
    """Generate HTML page to view duplicates."""
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Duplicate Images Viewer</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        
        .header p {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        .duplicate-group {
            background: white;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .group-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #667eea;
        }
        
        .group-title {
            font-size: 1.3rem;
            font-weight: 600;
            color: #333;
        }
        
        .group-count {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: 600;
        }
        
        .images-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }
        
        .image-card {
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            overflow: hidden;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .image-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.15);
            border-color: #667eea;
        }
        
        .image-card img {
            width: 100%;
            height: 300px;
            object-fit: contain;
            background: #f5f5f5;
            display: block;
        }
        
        .image-info {
            padding: 12px;
            background: #f8f9fa;
        }
        
        .image-name {
            font-weight: 600;
            margin-bottom: 5px;
            color: #333;
            word-break: break-all;
        }
        
        .image-path {
            font-size: 0.85rem;
            color: #666;
            word-break: break-all;
            line-height: 1.4;
        }
        
        .image-dimensions {
            font-size: 0.8rem;
            color: #999;
            margin-top: 5px;
        }
        
        .hash-code {
            font-family: monospace;
            font-size: 0.85rem;
            color: #666;
            background: #f0f0f0;
            padding: 5px 10px;
            border-radius: 5px;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: white;
            font-size: 1.2rem;
        }
        
        .stats {
            background: rgba(255,255,255,0.1);
            color: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Duplicate Images Viewer</h1>
            <p>Visual inspection of detected duplicates</p>
        </div>
        
        <div class="stats">
            <strong>Showing top 50 duplicate groups</strong> • 
            Click images to see full size in new tab
        </div>
"""
    
    print(f"Generating HTML for {len(groups)} duplicate groups...")
    
    for idx, group in enumerate(groups, 1):
        print(f"Processing group {idx}/{len(groups)}: {group['count']} images...")
        
        html += f"""
        <div class="duplicate-group">
            <div class="group-header">
                <div class="group-title">Duplicate Group #{idx}</div>
                <div class="group-count">{group['count']} copies</div>
            </div>
            <div style="margin-bottom: 15px;">
                <span class="hash-code">Hash: {group['hash']}</span>
            </div>
            <div class="images-grid">
"""
        
        # Show up to max_images_per_group images
        for img_path, img_name, width, height in group['images'][:max_images_per_group]:
            # Try to load and encode image
            img_data = image_to_base64(img_path, max_size=400)
            
            if img_data:
                html += f"""
                <div class="image-card">
                    <a href="file://{img_path}" target="_blank">
                        <img src="data:image/jpeg;base64,{img_data}" alt="{img_name}">
                    </a>
                    <div class="image-info">
                        <div class="image-name">{img_name}</div>
                        <div class="image-dimensions">{width}×{height}</div>
                        <div class="image-path">{img_path}</div>
                    </div>
                </div>
"""
            else:
                html += f"""
                <div class="image-card">
                    <div style="padding: 20px; text-align: center; color: #999;">
                        <p>⚠️ Could not load image</p>
                        <div class="image-info">
                            <div class="image-name">{img_name}</div>
                            <div class="image-path">{img_path}</div>
                        </div>
                    </div>
                </div>
"""
        
        if group['count'] > max_images_per_group:
            html += f"""
                <div style="grid-column: 1/-1; text-align: center; padding: 20px; color: #666;">
                    ... and {group['count'] - max_images_per_group} more copies
                </div>
"""
        
        html += """
            </div>
        </div>
"""
    
    html += """
    </div>
</body>
</html>
"""
    
    return html

if __name__ == "__main__":
    print("=" * 60)
    print("  🔍 DUPLICATE IMAGES VIEWER GENERATOR")
    print("=" * 60)
    print("")
    
    print("1. Fetching duplicate groups from database...")
    groups = get_duplicate_groups(limit=50, min_size=2, max_size=20)
    print(f"   Found {len(groups)} duplicate groups")
    print("")
    
    print("2. Generating HTML with embedded images...")
    print("   (This may take a few minutes...)")
    html = generate_html(groups, max_images_per_group=10)
    print("")
    
    print("3. Saving to file...")
    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"   ✓ Saved to: {OUTPUT_HTML}")
    print("")
    
    print("=" * 60)
    print("")
    print("✅ DONE! Open the file in your browser:")
    print(f"   open {OUTPUT_HTML}")
    print("")
    print("Or drag and drop this file into your browser:")
    print(f"   {OUTPUT_HTML}")
    print("")
    print("=" * 60)



