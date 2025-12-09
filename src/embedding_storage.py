"""
Thread-safe embedding storage with incremental saves.
Ensures embeddings are saved to disk during generation, not just at the end.
"""

import numpy as np
from pathlib import Path
from typing import List, Optional
import logging
import filelock
import time

logger = logging.getLogger(__name__)


def save_embeddings_incremental(
    embeddings_path: Path,
    new_embeddings: np.ndarray,
    embedding_indices: List[int],
    lock_path: Optional[Path] = None,
    db_path: Optional[Path] = None,
    worker_id: Optional[int] = None
) -> None:
    """
    Thread-safe incremental embedding save operation with safe buffer.
    
    SAFETY MECHANISM:
    1. FIRST: Save embeddings to worker-specific temp file (always succeeds)
    2. THEN: Try to merge temp file into main embeddings.npy (with lock)
    3. If merge succeeds: Delete temp file
    4. If merge fails: Keep temp file for recovery (no data loss!)
    
    This ensures embeddings are NEVER lost, even if lock times out or save fails.
    
    Args:
        embeddings_path: Path to embeddings.npy file
        new_embeddings: New embeddings to add (shape: [N, embedding_dim])
        embedding_indices: List of embedding_index values for each embedding
        lock_path: Optional path for lock file (defaults to embeddings_path + '.lock')
        worker_id: Optional worker ID for temp file naming
    """
    if lock_path is None:
        lock_path = embeddings_path.with_suffix('.npy.lock')
    
    # STEP 1: Save to worker-specific temp file FIRST (safe buffer - always succeeds)
    temp_dir = embeddings_path.parent / "embeddings_temp"
    temp_dir.mkdir(exist_ok=True)
    
    if worker_id is not None:
        temp_file = temp_dir / f"worker_{worker_id}_embeddings.npy"
        temp_indices_file = temp_dir / f"worker_{worker_id}_indices.npy"
    else:
        temp_file = temp_dir / f"worker_{int(time.time())}_embeddings.npy"
        temp_indices_file = temp_dir / f"worker_{int(time.time())}_indices.npy"
    
    # Save to temp file (no lock needed - each worker has its own file)
    try:
        np.save(temp_file, new_embeddings)
        np.save(temp_indices_file, np.array(embedding_indices))
        logger.debug(f"💾 Saved {len(new_embeddings)} embeddings to temp file: {temp_file}")
    except Exception as temp_error:
        logger.error(f"CRITICAL: Failed to save to temp file {temp_file}: {temp_error}")
        raise  # If we can't save to temp, something is seriously wrong
    
    # STEP 2: Try to merge temp file into main file (with lock)
    # Use file lock to prevent concurrent writes
    lock = filelock.FileLock(str(lock_path))
    
    merge_success = False
    try:
        with lock.acquire(timeout=300):  # Wait up to 5 minutes for lock
            # Load existing embeddings if they exist
            existing_embeddings = None
            if embeddings_path.exists():
                try:
                    existing_embeddings = np.load(embeddings_path)
                    # Verify file is not corrupted (has valid shape)
                    if len(existing_embeddings.shape) != 2:
                        logger.warning(f"Corrupted embeddings file (invalid shape: {existing_embeddings.shape}), recreating")
                        existing_embeddings = None
                    else:
                        logger.debug(f"Loaded {len(existing_embeddings)} existing embeddings")
                except Exception as e:
                    # File exists but is corrupted or incomplete
                    logger.warning(f"Failed to load embeddings file (corrupted?): {e}. Will recreate.")
                    # Backup corrupted file
                    corrupted_backup = embeddings_path.with_suffix('.npy.corrupted')
                    if not corrupted_backup.exists():
                        try:
                            embeddings_path.rename(corrupted_backup)
                            logger.info(f"Backed up corrupted file to {corrupted_backup}")
                        except Exception as backup_error:
                            logger.error(f"Failed to backup corrupted file: {backup_error}")
                    existing_embeddings = None
            
            if existing_embeddings is None:
                logger.info("No existing embeddings found or file was corrupted, will create new file")
            
            # Determine required array size
            max_idx = max(embedding_indices) if embedding_indices else -1
            embedding_dim = new_embeddings.shape[1] if len(new_embeddings) > 0 else None
            
            if existing_embeddings is not None:
                # File exists and is readable - work with it
                embedding_dim = existing_embeddings.shape[1]
                current_size = len(existing_embeddings)
                required_size = max_idx + 1
                
                if required_size > current_size:
                    # Expand array to fit the required size
                    # FIXED: Removed expansion limit that was causing data loss
                    # Previously limited to 2x current size, which caused workers saving
                    # at high indices to fail and zero out the file
                    logger.info(f"Expanding embeddings array from {current_size} to {required_size}")
                    full_embeddings = np.zeros((required_size, embedding_dim), dtype=existing_embeddings.dtype)
                    full_embeddings[:current_size] = existing_embeddings
                else:
                    full_embeddings = existing_embeddings.copy()
            else:
                # File doesn't exist or was corrupted - create new array
                # IMPORTANT: Only create array for what we're actually saving now
                # Don't create huge arrays based on database max index
                if embedding_dim is None:
                    raise ValueError("Cannot create new embeddings file without embedding dimension")
                
                if not embedding_indices:
                    raise ValueError("No embedding indices provided")
                
                # Create array starting from index 0, but only as large as needed for current batch
                # This allows file to grow organically without huge upfront allocation
                max_batch_idx = max(embedding_indices)
                min_batch_idx = min(embedding_indices)
                
                # Safety: If indices are very high (from old process), start from 0
                # The file will grow naturally as new embeddings are added
                if min_batch_idx > 100000:
                    logger.warning(f"High embedding indices detected (min: {min_batch_idx}). Creating file starting from 0.")
                    required_size = max_batch_idx + 1
                else:
                    required_size = max_batch_idx + 1
                
                logger.info(f"Creating new embeddings array with size {required_size} (for indices {min_batch_idx} to {max_batch_idx})")
                full_embeddings = np.zeros((required_size, embedding_dim), dtype=np.float32)
            
            # Insert new embeddings at their indices
            for emb, idx in zip(new_embeddings, embedding_indices):
                if not np.all(full_embeddings[idx] == 0):
                    logger.warning(f"Overwriting existing embedding at index {idx} (possible duplicate)")
                full_embeddings[idx] = emb
            
            # Save updated embeddings
            np.save(embeddings_path, full_embeddings)
            logger.info(f"💾 Saved {len(new_embeddings)} embeddings to {embeddings_path} (total: {len(full_embeddings)})")
            
            # STEP 3: Merge successful - delete temp files
            merge_success = True
            try:
                temp_file.unlink()
                temp_indices_file.unlink()
                logger.debug(f"✅ Deleted temp files after successful merge")
            except Exception as cleanup_error:
                logger.warning(f"Failed to delete temp files (non-critical): {cleanup_error}")
            
    except filelock.Timeout:
        logger.warning(f"⏱️  Timeout waiting for lock on {lock_path} - embeddings saved to temp file: {temp_file}")
        logger.warning(f"   Temp file will be merged on next successful save or recovery")
        # Don't raise - embeddings are safe in temp file!
        return
    except Exception as e:
        logger.error(f"❌ Error merging embeddings: {e}")
        logger.warning(f"   Embeddings are SAFE in temp file: {temp_file}")
        logger.warning(f"   Temp file will be merged on next successful save or recovery")
        # Don't raise - embeddings are safe in temp file!
        return
    
    if not merge_success:
        logger.warning(f"⚠️  Merge not completed, but embeddings are safe in: {temp_file}")


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


def recover_orphaned_temp_files(embeddings_path: Path) -> int:
    """
    Recover embeddings from orphaned temp files (e.g., after crash or lock timeout).
    
    Scans for worker temp files and merges them into main embeddings.npy.
    
    Returns:
        Number of embeddings recovered
    """
    temp_dir = embeddings_path.parent / "embeddings_temp"
    if not temp_dir.exists():
        return 0
    
    # Find all temp files
    temp_emb_files = sorted(temp_dir.glob("worker_*_embeddings.npy"))
    temp_idx_files = sorted(temp_dir.glob("worker_*_indices.npy"))
    
    if not temp_emb_files:
        return 0
    
    logger.info(f"🔍 Found {len(temp_emb_files)} orphaned temp files, recovering...")
    
    recovered = 0
    lock_path = embeddings_path.with_suffix('.npy.lock')
    lock = filelock.FileLock(str(lock_path))
    
    try:
        with lock.acquire(timeout=600):  # 10 minutes for recovery
            # Load existing embeddings
            existing_embeddings = None
            if embeddings_path.exists():
                try:
                    existing_embeddings = np.load(embeddings_path)
                except Exception as e:
                    logger.warning(f"Failed to load existing embeddings: {e}")
                    existing_embeddings = None
            
            # Collect all embeddings from temp files
            all_embeddings_dict = {}
            
            for emb_file, idx_file in zip(temp_emb_files, temp_idx_files):
                try:
                    embeddings = np.load(emb_file)
                    indices = np.load(idx_file)
                    
                    for emb, idx in zip(embeddings, indices):
                        all_embeddings_dict[int(idx)] = emb
                    
                    recovered += len(embeddings)
                    logger.info(f"  Recovered {len(embeddings)} embeddings from {emb_file.name}")
                except Exception as e:
                    logger.error(f"  Failed to recover from {emb_file.name}: {e}")
            
            if not all_embeddings_dict:
                logger.warning("No embeddings recovered from temp files")
                return 0
            
            # Merge into main file
            if existing_embeddings is not None:
                embedding_dim = existing_embeddings.shape[1]
                current_size = len(existing_embeddings)
                max_idx = max(max(all_embeddings_dict.keys()), current_size - 1)
                required_size = max_idx + 1
                
                if required_size > current_size:
                    full_embeddings = np.zeros((required_size, embedding_dim), dtype=existing_embeddings.dtype)
                    full_embeddings[:current_size] = existing_embeddings
                else:
                    full_embeddings = existing_embeddings.copy()
            else:
                max_idx = max(all_embeddings_dict.keys())
                embedding_dim = list(all_embeddings_dict.values())[0].shape[1]
                required_size = max_idx + 1
                full_embeddings = np.zeros((required_size, embedding_dim), dtype=np.float32)
            
            # Insert recovered embeddings
            for idx, emb in all_embeddings_dict.items():
                if not np.all(full_embeddings[idx] == 0):
                    logger.warning(f"Overwriting existing embedding at index {idx} during recovery")
                full_embeddings[idx] = emb
            
            # Save
            np.save(embeddings_path, full_embeddings)
            logger.info(f"✅ Recovered {recovered} embeddings into {embeddings_path} (total: {len(full_embeddings)})")
            
            # Delete recovered temp files
            for emb_file, idx_file in zip(temp_emb_files, temp_idx_files):
                try:
                    emb_file.unlink()
                    idx_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete {emb_file.name}: {e}")
            
    except filelock.Timeout:
        logger.error("Timeout acquiring lock for recovery - temp files will be recovered on next attempt")
    except Exception as e:
        logger.error(f"Error during recovery: {e}")
    
    return recovered

