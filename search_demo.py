#!/usr/bin/env python3
"""
Quick similarity search demo with current embeddings.

This script shows you how search will work, even with just 2,562 embeddings.
"""
import sys
import argparse
from pathlib import Path
from PIL import Image
import numpy as np

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_config
from src.database import ImageDatabase
from src.embeddings import EmbeddingModel
from src.image_processor import ImageProcessor


def search_with_current_embeddings(query_type: str, query_input: str, top_k: int = 10, open_preview: bool = False):
    """
    Search using embeddings currently in database.
    
    NOTE: This regenerates embeddings on-the-fly since vectors aren't saved yet.
    Full search (with FAISS) will be available after 'build-index' command.
    
    Args:
        query_type: 'text' or 'image'
        query_input: Query text or image path
        top_k: Number of results
        open_preview: If True, open results in Preview app
    """
    
    print("=" * 70)
    print("  🔍 Similarity Search Demo (Current Embeddings)")
    print("=" * 70)
    print()
    
    # Load config
    config = load_config(Path('config_optimized.yaml'))
    db_path = config.db_path
    
    # Check how many embeddings we have
    db = ImageDatabase(db_path)
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM images WHERE embedding_index IS NOT NULL")
    num_embeddings = cursor.fetchone()[0]
    
    print(f"📊 Status:")
    print(f"   - Images with embeddings: {num_embeddings:,}")
    print()
    
    if num_embeddings == 0:
        print("❌ No embeddings found yet. Wait for embedding generation to start.")
        return
    
    if num_embeddings < 100:
        print("⚠️  Very few embeddings. Results may not be representative.")
        print()
    
    # Load embedding model
    print("🤖 Loading embedding model (ViT-B-32)...")
    model = EmbeddingModel(
        model_name=config.model_name,
        pretrained=config.pretrained,
        device=config.device
    )
    print("   ✓ Model loaded")
    print()
    
    # Generate query embedding
    print(f"🎯 Processing query ({query_type})...")
    
    if query_type == 'text':
        query_embedding = model.encode_text(query_input, normalize=True)
        print(f"   Query: \"{query_input}\"")
    
    elif query_type == 'image':
        if not Path(query_input).exists():
            print(f"❌ Image not found: {query_input}")
            return
        
        image_processor = ImageProcessor(config.thumbnails_dir)
        img = image_processor.load_image(Path(query_input))
        
        if img is None:
            print(f"❌ Failed to load image: {query_input}")
            return
        
        query_embedding = model.encode_image(img, normalize=True)
        print(f"   Query image: {query_input}")
    
    else:
        print(f"❌ Unknown query type: {query_type}")
        return
    
    print("   ✓ Query embedding generated")
    print()
    
    # Get images with embeddings from database
    print("📚 Loading images with embeddings from database...")
    cursor.execute("""
        SELECT id, file_path, file_name, embedding_index, width, height
        FROM images 
        WHERE embedding_index IS NOT NULL
        ORDER BY embedding_index
        LIMIT 5000
    """)
    records = [dict(row) for row in cursor.fetchall()]
    print(f"   ✓ Loaded {len(records):,} images")
    print()
    
    # ⚠️ THE CHALLENGE: Embeddings vectors aren't saved yet, only indices are marked
    print("⚠️  Note: Embedding vectors aren't saved to file yet.")
    print("    To enable full search, run after processing completes:")
    print("    1. python cli.py save-embeddings")
    print("    2. python cli.py build-index")
    print()
    print("    For this demo, I'll show you the concept with regeneration")
    print("    (which is slow - FAISS search will be milliseconds).")
    print()
    
    # For demo: regenerate embeddings for a sample of images
    print(f"🔄 Regenerating embeddings for {min(100, len(records))} sample images...")
    print("   (This is slow - FAISS will be instant)")
    
    sample_records = records[:100]  # Sample for demo
    sample_embeddings = []
    sample_indices = []
    
    image_processor = ImageProcessor(config.thumbnails_dir)
    
    for i, record in enumerate(sample_records):
        if i % 10 == 0:
            print(f"   Progress: {i}/{len(sample_records)}", end='\r')
        
        img = image_processor.load_image(Path(record['file_path']))
        if img is not None:
            emb = model.encode_image(img, normalize=True)
            sample_embeddings.append(emb)
            sample_indices.append(i)
    
    print(f"   ✓ Generated {len(sample_embeddings)} embeddings            ")
    print()
    
    if len(sample_embeddings) == 0:
        print("❌ Could not load any images. Check file paths.")
        return
    
    # Simple numpy similarity search
    print(f"🔍 Searching for top {top_k} similar images...")
    embeddings_array = np.array(sample_embeddings)
    
    # Compute cosine similarity
    similarities = np.dot(embeddings_array, query_embedding)
    
    # Get top-k
    top_indices = np.argsort(-similarities)[:top_k]
    
    print()
    print("=" * 70)
    print(f"  📊 Top {top_k} Results")
    print("=" * 70)
    print()
    
    for rank, idx in enumerate(top_indices, 1):
        record = sample_records[sample_indices[idx]]
        similarity = similarities[idx]
        
        print(f"{rank}. Score: {similarity:.4f}")
        print(f"   Path: {record['file_path']}")
        print(f"   File: {record['file_name']}")
        if record['width'] and record['height']:
            print(f"   Size: {record['width']}×{record['height']}")
        print()
    
    print("=" * 70)
    print()
    
    # Open in Preview if requested
    if open_preview:
        print("🖼️  Opening results in Preview...")
        import subprocess
        
        # Collect file paths
        result_paths = []
        for rank, idx in enumerate(top_indices[:min(top_k, len(top_indices))], 1):
            record = sample_records[sample_indices[idx]]
            file_path = record['file_path']
            if Path(file_path).exists():
                result_paths.append(file_path)
            else:
                print(f"   ⚠️  File not found: {file_path}")
        
        if result_paths:
            try:
                # Open all results in Preview at once
                subprocess.run(['open', '-a', 'Preview'] + result_paths)
                print(f"   ✓ Opened {len(result_paths)} images in Preview")
            except Exception as e:
                print(f"   ❌ Failed to open Preview: {e}")
        else:
            print("   ❌ No valid files found to open")
        print()
    
    print("💡 This is a demo with regenerated embeddings.")
    print("   Real search with FAISS will:")
    print("   - Search 3 million images in milliseconds")
    print("   - Use compressed index (32× less memory)")
    print("   - Support exact + approximate search")
    print()
    print("🚀 Run after processing completes:")
    print("   python cli.py build-index")
    print("   python cli.py search-text 'sunset beach'")
    print("   python cli.py search-image query.jpg")
    print()
    
    db.close()


def main():
    parser = argparse.ArgumentParser(
        description='Demo similarity search with current embeddings'
    )
    parser.add_argument(
        'query_type',
        choices=['text', 'image'],
        help='Type of query: text or image'
    )
    parser.add_argument(
        'query',
        help='Query text or path to query image'
    )
    parser.add_argument(
        '-k', '--top-k',
        type=int,
        default=10,
        help='Number of results to return (default: 10)'
    )
    parser.add_argument(
        '--open',
        action='store_true',
        help='Open results in Preview app (macOS)'
    )
    
    args = parser.parse_args()
    
    search_with_current_embeddings(
        query_type=args.query_type,
        query_input=args.query,
        top_k=args.top_k,
        open_preview=args.open
    )


if __name__ == '__main__':
    main()

