"""
Thread-safe embedding storage with incremental saves.
Ensures embeddings are saved to disk during generation, not just at the end.
"""

import numpy as np
from pathlib import Path
from typing import List, Optional
import logging
import filelock

logger = logging.getLogger(__name__)


def save_embeddings_incremental(
    embeddings_path: Path,
    new_embeddings: np.ndarray,
    embedding_indices: List[int],
    lock_path: Optional[Path] = None
) -> None:
    """
    Thread-safe incremental embedding save operation.
    
    This function:
    1. Loads existing embeddings.npy (if exists)
    2. Expands array to fit new indices if needed
    3. Inserts new embeddings at their correct indices
    4. Saves back to disk
    
    Uses file locking to prevent conflicts between parallel workers.
    
    Args:
        embeddings_path: Path to embeddings.npy file
        new_embeddings: New embeddings to add (shape: [N, embedding_dim])
        embedding_indices: List of embedding_index values for each embedding
        lock_path: Optional path for lock file (defaults to embeddings_path + '.lock')
    """
    if lock_path is None:
        lock_path = embeddings_path.with_suffix('.npy.lock')
    
    # Use file lock to prevent concurrent writes
    lock = filelock.FileLock(str(lock_path))
    
    try:
        with lock.acquire(timeout=300):  # Wait up to 5 minutes for lock
            # Load existing embeddings if they exist
            if embeddings_path.exists():
                existing_embeddings = np.load(embeddings_path)
                logger.debug(f"Loaded {len(existing_embeddings)} existing embeddings")
            else:
                existing_embeddings = None
                logger.info("No existing embeddings found, creating new file")
            
            # Determine required array size
            max_idx = max(embedding_indices) if embedding_indices else -1
            embedding_dim = new_embeddings.shape[1] if len(new_embeddings) > 0 else None
            
            if existing_embeddings is not None:
                embedding_dim = existing_embeddings.shape[1]
                current_size = len(existing_embeddings)
                required_size = max_idx + 1
                
                if required_size > current_size:
                    # Need to expand array
                    logger.info(f"Expanding embeddings array from {current_size} to {required_size}")
                    full_embeddings = np.zeros((required_size, embedding_dim), dtype=existing_embeddings.dtype)
                    full_embeddings[:current_size] = existing_embeddings
                else:
                    full_embeddings = existing_embeddings.copy()
            else:
                # Create new array
                if embedding_dim is None:
                    raise ValueError("Cannot create new embeddings file without embedding dimension")
                required_size = max_idx + 1
                logger.info(f"Creating new embeddings array with size {required_size}")
                full_embeddings = np.zeros((required_size, embedding_dim), dtype=np.float32)
            
            # Insert new embeddings at their indices
            for emb, idx in zip(new_embeddings, embedding_indices):
                if not np.all(full_embeddings[idx] == 0):
                    logger.warning(f"Overwriting existing embedding at index {idx} (possible duplicate)")
                full_embeddings[idx] = emb
            
            # Save updated embeddings
            np.save(embeddings_path, full_embeddings)
            logger.info(f"💾 Saved {len(new_embeddings)} embeddings to {embeddings_path} (total: {len(full_embeddings)})")
            
    except filelock.Timeout:
        logger.error(f"Timeout waiting for lock on {lock_path} - another worker may be saving")
        raise
    except Exception as e:
        logger.error(f"Error saving embeddings: {e}")
        raise


def merge_worker_embeddings_to_main(
    embeddings_path: Path,
    worker_embeddings_paths: List[Path],
    worker_indices_paths: List[Path]
) -> None:
    """
    Merge embeddings from worker files into main embeddings.npy.
    
    This is a fallback/safety function for merging worker files after completion.
    """
    lock_path = embeddings_path.with_suffix('.npy.lock')
    lock = filelock.FileLock(str(lock_path))
    
    with lock.acquire(timeout=600):  # 10 minutes timeout for merge
        # Load all worker embeddings
        all_embeddings_dict = {}
        
        for emb_file, idx_file in zip(worker_embeddings_paths, worker_indices_paths):
            if not emb_file.exists() or not idx_file.exists():
                continue
                
            embeddings = np.load(emb_file)
            indices = np.load(idx_file)
            
            for emb, idx in zip(embeddings, indices):
                all_embeddings_dict[int(idx)] = emb
        
        if not all_embeddings_dict:
            logger.warning("No worker embeddings to merge")
            return
        
        # Load existing embeddings
        if embeddings_path.exists():
            existing_embeddings = np.load(embeddings_path)
        else:
            existing_embeddings = None
        
        # Determine size
        max_idx = max(all_embeddings_dict.keys())
        embedding_dim = list(all_embeddings_dict.values())[0].shape[0]
        
        if existing_embeddings is not None:
            current_size = len(existing_embeddings)
            required_size = max(current_size, max_idx + 1)
            full_embeddings = np.zeros((required_size, embedding_dim), dtype=existing_embeddings.dtype)
            full_embeddings[:current_size] = existing_embeddings
        else:
            required_size = max_idx + 1
            full_embeddings = np.zeros((required_size, embedding_dim), dtype=np.float32)
        
        # Insert worker embeddings
        for idx, emb in all_embeddings_dict.items():
            full_embeddings[idx] = emb
        
        # Save
        np.save(embeddings_path, full_embeddings)
        logger.info(f"✅ Merged {len(all_embeddings_dict)} embeddings into {embeddings_path} (total: {len(full_embeddings)})")

