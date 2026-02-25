#!/usr/bin/env python3
"""
Monitor embeddings.npy file growth and embedding_index assignments.
Useful for verifying that the new resumable saving process is working.
"""

import sqlite3
from pathlib import Path
import time
from datetime import datetime

def get_db_stats(db_path):
    """Get statistics from database."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Total stats
    cursor.execute("SELECT COUNT(*) FROM images")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(embedding_index) FROM images")
    with_idx = cursor.fetchone()[0]
    
    cursor.execute("SELECT MAX(embedding_index) FROM images WHERE embedding_index IS NOT NULL")
    max_idx = cursor.fetchone()[0] or 0
    
    # Recent assignments (last hour)
    cursor.execute("""
        SELECT COUNT(*) 
        FROM images 
        WHERE embedding_index IS NOT NULL 
        AND datetime(updated_at) > datetime('now', '-1 hour')
    """)
    recent_1h = cursor.fetchone()[0]
    
    # Very recent assignments (last 10 minutes)
    cursor.execute("""
        SELECT COUNT(*), MAX(embedding_index), MAX(updated_at)
        FROM images 
        WHERE embedding_index IS NOT NULL 
        AND datetime(updated_at) > datetime('now', '-10 minutes')
    """)
    recent_10m = cursor.fetchone()
    
    conn.close()
    
    return {
        'total': total,
        'with_embedding_index': with_idx,
        'max_embedding_index': max_idx,
        'recent_1h': recent_1h,
        'recent_10m_count': recent_10m[0] if recent_10m[0] else 0,
        'recent_10m_max_idx': recent_10m[1] if recent_10m[1] else None,
        'recent_10m_last_time': recent_10m[2] if recent_10m[2] else None
    }

def get_npy_file_stats(emb_path):
    """Get statistics about embeddings.npy file."""
    if not emb_path.exists():
        return {
            'exists': False,
            'size_mb': 0,
            'num_embeddings': 0,
            'readable': False
        }
    
    size_bytes = emb_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    
    # Try to load the file
    try:
        import numpy as np
        arr = np.load(str(emb_path))
        return {
            'exists': True,
            'size_mb': size_mb,
            'num_embeddings': len(arr),
            'shape': arr.shape,
            'readable': True
        }
    except Exception as e:
        return {
            'exists': True,
            'size_mb': size_mb,
            'num_embeddings': 0,
            'readable': False,
            'error': str(e)
        }

def main():
    db_path = Path('data/metadata.db')
    emb_path = Path('data/embeddings.npy')
    
    print("=" * 70)
    print(f"  EMBEDDINGS PROGRESS MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    
    # Database stats
    db_stats = get_db_stats(db_path)
    print("📊 DATABASE STATISTICS:")
    print(f"   Total images: {db_stats['total']:,}")
    print(f"   With embedding_index: {db_stats['with_embedding_index']:,}")
    print(f"   Max embedding_index: {db_stats['max_embedding_index']:,}")
    print()
    print(f"   New assignments (last hour): {db_stats['recent_1h']:,}")
    print(f"   New assignments (last 10 min): {db_stats['recent_10m_count']:,}")
    if db_stats['recent_10m_max_idx']:
        print(f"   Latest max index: {db_stats['recent_10m_max_idx']:,}")
        print(f"   Latest assignment time: {db_stats['recent_10m_last_time']}")
    print()
    
    # .npy file stats
    npy_stats = get_npy_file_stats(emb_path)
    print("💾 EMBEDDINGS.NPY FILE:")
    if not npy_stats['exists']:
        print("   ❌ File does not exist")
    elif not npy_stats['readable']:
        print(f"   ⚠️  File exists but CORRUPTED")
        print(f"      Size: {npy_stats['size_mb']:.2f} MB")
        print(f"      Error: {npy_stats.get('error', 'Unknown error')}")
    else:
        print(f"   ✅ File is readable")
        print(f"      Size: {npy_stats['size_mb']:.2f} MB")
        print(f"      Embeddings: {npy_stats['num_embeddings']:,}")
        print(f"      Shape: {npy_stats['shape']}")
        
        # Compare with database
        expected_size = (db_stats['max_embedding_index'] + 1) * 512 * 4 / (1024 * 1024)
        print(f"      Expected size (for max index): {expected_size:.2f} MB")
        print(f"      Coverage: {npy_stats['num_embeddings'] / (db_stats['max_embedding_index'] + 1) * 100:.1f}%")
    
    print()
    print("=" * 70)
    print("  INTERPRETATION:")
    print("=" * 70)
    
    if db_stats['recent_10m_count'] > 0:
        print(f"✅ NEW PROCESS IS RUNNING!")
        print(f"   {db_stats['recent_10m_count']:,} new embedding_index values assigned in last 10 minutes")
        print(f"   Latest index: {db_stats['recent_10m_max_idx']:,}")
        if npy_stats['readable']:
            print(f"   .npy file has {npy_stats['num_embeddings']:,} embeddings")
            if npy_stats['num_embeddings'] < db_stats['recent_10m_max_idx']:
                print(f"   ⚠️  .npy file is BEHIND database (missing embeddings)")
            else:
                print(f"   ✅ .npy file is keeping up")
        else:
            print(f"   ⚠️  .npy file is corrupted - needs fixing")
    else:
        print("⚠️  NO NEW ASSIGNMENTS in last 10 minutes")
        print("   Workers might not be running or processing")
    
    print("=" * 70)
    print()
    print("💡 TIP: Run this script again in a few minutes to see if:")
    print("   1. New embedding_index values are being assigned")
    print("   2. .npy file size is growing")
    print("   3. File becomes readable (corruption fixed)")

if __name__ == '__main__':
    main()










