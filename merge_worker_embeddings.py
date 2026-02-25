#!/usr/bin/env python3
"""
Merge embeddings from multiple worker files into a single embeddings.npy file.
This should be run after all workers complete.
"""

import sys
from pathlib import Path
import numpy as np
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_config

def merge_worker_embeddings(config_path: Path = None):
    """Merge embeddings from worker files into main embeddings.npy."""
    
    if config_path is None:
        config_path = Path('config_optimized.yaml')
    
    config = load_config(config_path)
    embeddings_dir = config.embeddings_path.parent
    
    print(f"Looking for worker embedding files in {embeddings_dir}")
    
    # Find all worker embedding files
    worker_files = sorted(embeddings_dir.glob("embeddings_worker_*.npy"))
    
    if not worker_files:
        print("❌ No worker embedding files found!")
        return
    
    print(f"Found {len(worker_files)} worker files:")
    for f in worker_files:
        print(f"  - {f.name}")
    
    # Load all worker embeddings and their indices
    all_embeddings_dict = {}
    
    for worker_file in tqdm(worker_files, desc="Loading worker files"):
        worker_id = worker_file.stem.split("_")[-1]
        indices_file = embeddings_dir / f"indices_worker_{worker_id}.npy"
        
        if not indices_file.exists():
            print(f"⚠️  Warning: No indices file found for worker {worker_id}, skipping")
            continue
        
        embeddings = np.load(worker_file)
        indices = np.load(indices_file)
        
        print(f"Worker {worker_id}: {len(embeddings)} embeddings, indices {indices.min()}-{indices.max()}")
        
        # Store embeddings by their index
        for emb, idx in zip(embeddings, indices):
            all_embeddings_dict[int(idx)] = emb
    
    if not all_embeddings_dict:
        print("❌ No embeddings loaded!")
        return
    
    # Create full embeddings array
    max_idx = max(all_embeddings_dict.keys())
    embedding_dim = list(all_embeddings_dict.values())[0].shape[0]
    
    print(f"Creating embeddings array: shape ({max_idx + 1}, {embedding_dim})")
    full_embeddings = np.zeros((max_idx + 1, embedding_dim), dtype=np.float32)
    
    # Fill in embeddings
    for idx, emb in tqdm(all_embeddings_dict.items(), desc="Filling embeddings array"):
        full_embeddings[idx] = emb
    
    # Save merged embeddings
    print(f"Saving merged embeddings to {config.embeddings_path}...")
    np.save(config.embeddings_path, full_embeddings)
    
    print(f"✅ Saved {len(full_embeddings)} embeddings to {config.embeddings_path}")
    print(f"   (Actually contains {len(all_embeddings_dict)} non-zero embeddings)")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Merge worker embeddings into main file')
    parser.add_argument('--config', type=Path, default='config_optimized.yaml',
                       help='Path to config file')
    args = parser.parse_args()
    
    merge_worker_embeddings(args.config)

