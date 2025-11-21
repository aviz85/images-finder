"""Smart directory scanner with database-backed caching."""

from pathlib import Path
import pickle
import hashlib
import time
from typing import List, Set
import logging

logger = logging.getLogger(__name__)


class SmartScanner:
    """
    Smart scanner that caches scan results and uses database to avoid re-scanning.
    """
    
    def __init__(self, cache_dir: Path):
        """
        Initialize smart scanner.
        
        Args:
            cache_dir: Directory to store scan caches
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, directory: Path) -> Path:
        """Get cache file path for a directory."""
        # Create a hash of the directory path for cache filename
        dir_hash = hashlib.md5(str(directory).encode()).hexdigest()
        return self.cache_dir / f"scan_cache_{dir_hash}.pkl"
    
    def _load_cache(self, directory: Path) -> dict:
        """Load cached scan results."""
        cache_path = self._get_cache_path(directory)
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    cache = pickle.load(f)
                logger.info(f"Loaded scan cache with {len(cache.get('files', []))} files")
                return cache
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        return {}
    
    def _save_cache(self, directory: Path, files: List[Path], scan_time: float):
        """Save scan results to cache."""
        cache_path = self._get_cache_path(directory)
        cache = {
            'directory': str(directory),
            'files': [str(f) for f in files],
            'scan_time': scan_time,
            'timestamp': time.time()
        }
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(cache, f)
            logger.info(f"Saved scan cache with {len(files)} files")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
    
    def scan_with_cache(
        self,
        directory: Path,
        extensions: List[str],
        registered_paths: Set[str] = None,
        max_cache_age: int = 3600 * 24  # 24 hours
    ) -> List[Path]:
        """
        Scan directory for images, using cache when possible.
        
        Args:
            directory: Directory to scan
            extensions: File extensions to include
            registered_paths: Set of already registered paths to skip
            max_cache_age: Maximum cache age in seconds
        
        Returns:
            List of image file paths that need processing
        """
        registered_paths = registered_paths or set()
        
        # Try to load cache
        cache = self._load_cache(directory)
        use_cache = False
        
        if cache:
            cache_age = time.time() - cache.get('timestamp', 0)
            if cache_age < max_cache_age:
                logger.info(f"Using cached scan results (age: {cache_age/3600:.1f} hours)")
                use_cache = True
            else:
                logger.info(f"Cache too old ({cache_age/3600:.1f} hours), re-scanning")
        
        if use_cache and cache.get('files'):
            # Use cached file list
            all_files = [Path(f) for f in cache['files']]
            logger.info(f"Loaded {len(all_files)} files from cache")
        else:
            # Full scan
            logger.info(f"Scanning directory: {directory}")
            scan_start = time.time()
            
            all_files = []
            extensions_lower = [ext.lower() for ext in extensions]
            
            for file_path in directory.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in extensions_lower:
                    all_files.append(file_path)
            
            scan_time = time.time() - scan_start
            logger.info(f"Scan complete: {len(all_files)} files in {scan_time:.1f}s")
            
            # Save to cache
            self._save_cache(directory, all_files, scan_time)
        
        # Filter out already registered
        unregistered = [f for f in all_files if str(f) not in registered_paths]
        
        if len(unregistered) < len(all_files):
            logger.info(f"Filtered: {len(all_files)} total, {len(unregistered)} new, "
                       f"{len(all_files) - len(unregistered)} already registered")
        
        return sorted(unregistered)
    
    def invalidate_cache(self, directory: Path):
        """Invalidate cache for a directory."""
        cache_path = self._get_cache_path(directory)
        if cache_path.exists():
            cache_path.unlink()
            logger.info(f"Invalidated cache for {directory}")


def scan_images_smart(
    root_dir: Path,
    extensions: List[str],
    db_connection,
    cache_dir: Path = None
) -> List[Path]:
    """
    Smart scan that uses caching and database to avoid re-scanning.
    
    Args:
        root_dir: Root directory to scan
        extensions: List of file extensions
        db_connection: Database connection to check registered paths
        cache_dir: Directory for cache files
    
    Returns:
        List of unregistered image files
    """
    if cache_dir is None:
        cache_dir = Path.home() / '.images-finder' / 'scan_cache'
    
    scanner = SmartScanner(cache_dir)
    
    # Get already registered paths from database
    logger.info("Querying database for registered images...")
    cursor = db_connection.cursor()
    cursor.execute("SELECT file_path FROM images")
    registered_paths = {row[0] for row in cursor.fetchall()}
    logger.info(f"Found {len(registered_paths)} already registered images")
    
    # Scan with cache
    return scanner.scan_with_cache(root_dir, extensions, registered_paths)



