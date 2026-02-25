"""
Gallery Database Module
Handles all database operations for the gallery review system.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
import hashlib


class GalleryDB:
    """Database operations for gallery review system."""

    def __init__(self, db_path: str = "gallery.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_conn(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                -- Main images table
                CREATE TABLE IF NOT EXISTS gallery_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_path TEXT UNIQUE NOT NULL,
                    thumbnail_path TEXT,
                    semantic_score REAL,
                    rating INTEGER DEFAULT 0,
                    width INTEGER,
                    height INTEGER,
                    file_size INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Progress tracking for resumable pipeline
                CREATE TABLE IF NOT EXISTS gallery_progress (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    total_images INTEGER DEFAULT 0,
                    processed_images INTEGER DEFAULT 0,
                    failed_images INTEGER DEFAULT 0,
                    last_processed_path TEXT,
                    started_at TIMESTAMP,
                    updated_at TIMESTAMP
                );

                -- Similar images cache (optional, for speed)
                CREATE TABLE IF NOT EXISTS similar_cache (
                    image_id INTEGER,
                    similar_image_id INTEGER,
                    similarity_score REAL,
                    PRIMARY KEY (image_id, similar_image_id),
                    FOREIGN KEY (image_id) REFERENCES gallery_images(id)
                );

                -- Indexes for fast filtering
                CREATE INDEX IF NOT EXISTS idx_rating ON gallery_images(rating);
                CREATE INDEX IF NOT EXISTS idx_score ON gallery_images(semantic_score);
                CREATE INDEX IF NOT EXISTS idx_path ON gallery_images(original_path);
                CREATE INDEX IF NOT EXISTS idx_thumbnail ON gallery_images(thumbnail_path);

                -- Initialize progress row if not exists
                INSERT OR IGNORE INTO gallery_progress (id, started_at, updated_at)
                VALUES (1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
            """)
            conn.commit()

    # ==================== Image Operations ====================

    def add_image(self, original_path: str, semantic_score: float = None) -> int:
        """Add an image to the gallery. Returns image ID."""
        with self._get_conn() as conn:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO gallery_images (original_path, semantic_score)
                VALUES (?, ?)
            """, (original_path, semantic_score))
            conn.commit()

            if cursor.lastrowid:
                return cursor.lastrowid

            # Already exists, get the ID
            cursor = conn.execute(
                "SELECT id FROM gallery_images WHERE original_path = ?",
                (original_path,)
            )
            row = cursor.fetchone()
            return row['id'] if row else None

    def update_thumbnail(self, original_path: str, thumbnail_path: str,
                         width: int = None, height: int = None, file_size: int = None):
        """Update thumbnail info for an image."""
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE gallery_images
                SET thumbnail_path = ?, width = ?, height = ?, file_size = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE original_path = ?
            """, (thumbnail_path, width, height, file_size, original_path))
            conn.commit()

    def set_rating(self, image_id: int, rating: int) -> bool:
        """Set rating for an image (1-5, or 0 for unrated)."""
        if rating < 0 or rating > 5:
            return False
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE gallery_images
                SET rating = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (rating, image_id))
            conn.commit()
            return True

    def get_image(self, image_id: int) -> Optional[Dict[str, Any]]:
        """Get a single image by ID."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM gallery_images WHERE id = ?", (image_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_image_by_path(self, original_path: str) -> Optional[Dict[str, Any]]:
        """Get a single image by original path."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM gallery_images WHERE original_path = ?", (original_path,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_images(self, page: int = 1, per_page: int = 50,
                   min_rating: int = None, max_rating: int = None,
                   min_score: float = None, max_score: float = None,
                   unrated_only: bool = False,
                   sort_by: str = "semantic_score", order: str = "desc",
                   has_thumbnail: bool = True,
                   show_hidden: bool = False) -> Tuple[List[Dict], int]:
        """
        Get paginated list of images with filters.
        Returns (images, total_count).
        """
        conditions = []
        params = []

        # Filter out hidden duplicates by default
        if not show_hidden:
            conditions.append("(is_hidden IS NULL OR is_hidden = 0)")

        if has_thumbnail:
            conditions.append("thumbnail_path IS NOT NULL")

        if min_rating is not None:
            conditions.append("rating >= ?")
            params.append(min_rating)

        if max_rating is not None:
            conditions.append("rating <= ?")
            params.append(max_rating)

        if min_score is not None:
            conditions.append("semantic_score >= ?")
            params.append(min_score)

        if max_score is not None:
            conditions.append("semantic_score <= ?")
            params.append(max_score)

        if unrated_only:
            conditions.append("rating = 0")

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        # Validate sort_by and order
        valid_sorts = {"semantic_score", "rating", "original_path", "id", "created_at"}
        sort_by = sort_by if sort_by in valid_sorts else "semantic_score"
        order = "DESC" if order.upper() == "DESC" else "ASC"

        with self._get_conn() as conn:
            # Get total count
            count_query = f"SELECT COUNT(*) as cnt FROM gallery_images {where_clause}"
            cursor = conn.execute(count_query, params)
            total = cursor.fetchone()['cnt']

            # Get paginated results
            offset = (page - 1) * per_page
            query = f"""
                SELECT * FROM gallery_images
                {where_clause}
                ORDER BY {sort_by} {order}
                LIMIT ? OFFSET ?
            """
            cursor = conn.execute(query, params + [per_page, offset])
            images = [dict(row) for row in cursor.fetchall()]

            return images, total

    def get_all_paths(self) -> set:
        """Get all original paths in database (for checking existing)."""
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT original_path FROM gallery_images")
            return {row['original_path'] for row in cursor.fetchall()}

    def get_unprocessed_images(self, limit: int = 100) -> List[Dict]:
        """Get images without thumbnails."""
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT id, original_path, semantic_score
                FROM gallery_images
                WHERE thumbnail_path IS NULL
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def bulk_add_images(self, images: List[Tuple[str, float]]) -> int:
        """
        Bulk add images. images = [(original_path, semantic_score), ...]
        Returns count of newly added images.
        """
        with self._get_conn() as conn:
            cursor = conn.executemany("""
                INSERT OR IGNORE INTO gallery_images (original_path, semantic_score)
                VALUES (?, ?)
            """, images)
            conn.commit()
            return cursor.rowcount

    def bulk_update_thumbnails(self, updates: List[Tuple[str, str, int, int, int]]):
        """
        Bulk update thumbnails.
        updates = [(thumbnail_path, original_path, width, height, file_size), ...]
        """
        with self._get_conn() as conn:
            conn.executemany("""
                UPDATE gallery_images
                SET thumbnail_path = ?, width = ?, height = ?, file_size = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE original_path = ?
            """, [(t[0], t[2], t[3], t[4], t[1]) for t in updates])
            conn.commit()

    # ==================== Progress Tracking ====================

    def get_progress(self) -> Dict[str, Any]:
        """Get current progress."""
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT * FROM gallery_progress WHERE id = 1")
            row = cursor.fetchone()
            return dict(row) if row else {}

    def update_progress(self, total: int = None, processed: int = None,
                        failed: int = None, last_path: str = None):
        """Update progress."""
        updates = []
        params = []

        if total is not None:
            updates.append("total_images = ?")
            params.append(total)

        if processed is not None:
            updates.append("processed_images = ?")
            params.append(processed)

        if failed is not None:
            updates.append("failed_images = ?")
            params.append(failed)

        if last_path is not None:
            updates.append("last_processed_path = ?")
            params.append(last_path)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE gallery_progress SET {', '.join(updates)} WHERE id = 1",
                    params
                )
                conn.commit()

    def reset_progress(self):
        """Reset progress for fresh start."""
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE gallery_progress
                SET total_images = 0, processed_images = 0, failed_images = 0,
                    last_processed_path = NULL,
                    started_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            """)
            conn.commit()

    # ==================== Statistics ====================

    def get_stats(self) -> Dict[str, Any]:
        """Get gallery statistics."""
        with self._get_conn() as conn:
            stats = {}

            # Total images
            cursor = conn.execute("SELECT COUNT(*) as cnt FROM gallery_images")
            stats['total_images'] = cursor.fetchone()['cnt']

            # With thumbnails
            cursor = conn.execute(
                "SELECT COUNT(*) as cnt FROM gallery_images WHERE thumbnail_path IS NOT NULL"
            )
            stats['with_thumbnails'] = cursor.fetchone()['cnt']

            # Rating distribution
            cursor = conn.execute("""
                SELECT rating, COUNT(*) as cnt
                FROM gallery_images
                GROUP BY rating
                ORDER BY rating
            """)
            stats['rating_distribution'] = {row['rating']: row['cnt'] for row in cursor.fetchall()}

            # Score range
            cursor = conn.execute("""
                SELECT MIN(semantic_score) as min_score,
                       MAX(semantic_score) as max_score,
                       AVG(semantic_score) as avg_score
                FROM gallery_images
            """)
            row = cursor.fetchone()
            stats['min_score'] = row['min_score']
            stats['max_score'] = row['max_score']
            stats['avg_score'] = row['avg_score']

            # Progress
            cursor = conn.execute("SELECT * FROM gallery_progress WHERE id = 1")
            progress = cursor.fetchone()
            if progress:
                stats['progress'] = dict(progress)

            return stats

    # ==================== Similar Images Cache ====================

    def cache_similar(self, image_id: int, similar: List[Tuple[int, float]]):
        """Cache similar images for an image."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM similar_cache WHERE image_id = ?", (image_id,))
            conn.executemany("""
                INSERT INTO similar_cache (image_id, similar_image_id, similarity_score)
                VALUES (?, ?, ?)
            """, [(image_id, sim_id, score) for sim_id, score in similar])
            conn.commit()

    def get_cached_similar(self, image_id: int) -> List[Dict]:
        """Get cached similar images."""
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT gi.*, sc.similarity_score
                FROM similar_cache sc
                JOIN gallery_images gi ON sc.similar_image_id = gi.id
                WHERE sc.image_id = ?
                ORDER BY sc.similarity_score DESC
            """, (image_id,))
            return [dict(row) for row in cursor.fetchall()]


def path_to_thumbnail_name(original_path: str) -> str:
    """Convert original path to thumbnail filename using MD5 hash."""
    return hashlib.md5(original_path.encode('utf-8')).hexdigest() + '.jpg'


if __name__ == "__main__":
    # Test the database
    db = GalleryDB("/Users/aviz/images-finder/gallery/gallery.db")
    print("Database initialized!")
    print("Stats:", db.get_stats())
