"""SQLite database management for image metadata."""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


class ImageDatabase:
    """Manages SQLite database for image metadata."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        cursor = self.conn.cursor()

        # Main images table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER,
                width INTEGER,
                height INTEGER,
                format TEXT,
                thumbnail_path TEXT,
                embedding_index INTEGER,
                perceptual_hash TEXT,
                is_duplicate BOOLEAN DEFAULT 0,
                duplicate_of INTEGER,
                processed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (duplicate_of) REFERENCES images(id)
            )
        """)

        # Migrate existing tables to add new columns
        try:
            cursor.execute("ALTER TABLE images ADD COLUMN perceptual_hash TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("ALTER TABLE images ADD COLUMN is_duplicate BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE images ADD COLUMN duplicate_of INTEGER REFERENCES images(id)")
        except sqlite3.OperationalError:
            pass

        # Index for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_path ON images(file_path)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_embedding_index ON images(embedding_index)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed ON images(processed_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_perceptual_hash ON images(perceptual_hash)
        """)

        # Processing status table for resumable jobs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name TEXT UNIQUE NOT NULL,
                total_files INTEGER DEFAULT 0,
                processed_files INTEGER DEFAULT 0,
                failed_files INTEGER DEFAULT 0,
                last_checkpoint TEXT,
                started_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        # Failed images log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS failed_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                error_message TEXT,
                failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Ratings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER NOT NULL,
                rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
            )
        """)

        # Index for ratings
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rating_image_id ON ratings(image_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rating_value ON ratings(rating)
        """)

        # Tags table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Image-Tag junction table (many-to-many)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS image_tags (
                image_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (image_id, tag_id),
                FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
        """)

        # Indexes for tags
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tag_name ON tags(name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_image_tags_image ON image_tags(image_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_image_tags_tag ON image_tags(tag_id)
        """)

        self.conn.commit()

    def add_image(self, file_path: str, file_name: str, file_size: int,
                  width: int, height: int, format: str,
                  thumbnail_path: Optional[str] = None,
                  embedding_index: Optional[int] = None,
                  perceptual_hash: Optional[str] = None) -> int:
        """Add or update an image record."""
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO images (
                file_path, file_name, file_size, width, height, format,
                thumbnail_path, embedding_index, perceptual_hash, processed_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                file_size=excluded.file_size,
                width=excluded.width,
                height=excluded.height,
                format=excluded.format,
                thumbnail_path=excluded.thumbnail_path,
                embedding_index=excluded.embedding_index,
                perceptual_hash=excluded.perceptual_hash,
                processed_at=excluded.processed_at,
                updated_at=excluded.updated_at
        """, (file_path, file_name, file_size, width, height, format,
              thumbnail_path, embedding_index, perceptual_hash, now, now))

        self.conn.commit()
        return cursor.lastrowid

    def get_image_by_path(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get image record by file path."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM images WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_image_by_embedding_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Get image record by embedding index."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM images WHERE embedding_index = ?", (index,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_images_by_indices(self, indices: List[int]) -> List[Dict[str, Any]]:
        """Get multiple images by embedding indices."""
        if not indices:
            return []
        cursor = self.conn.cursor()
        placeholders = ','.join('?' * len(indices))
        cursor.execute(
            f"SELECT * FROM images WHERE embedding_index IN ({placeholders})",
            indices
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_unprocessed_images(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get images that haven't been processed yet."""
        cursor = self.conn.cursor()
        query = "SELECT * FROM images WHERE embedding_index IS NULL"
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def get_total_images(self) -> int:
        """Get total number of images in database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM images")
        return cursor.fetchone()[0]

    def get_processed_count(self) -> int:
        """Get count of processed images."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM images WHERE embedding_index IS NOT NULL")
        return cursor.fetchone()[0]

    def add_failed_image(self, file_path: str, error_message: str):
        """Log a failed image processing attempt."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO failed_images (file_path, error_message)
            VALUES (?, ?)
        """, (file_path, error_message))
        self.conn.commit()

    def update_processing_status(self, job_name: str, total_files: int = 0,
                                processed_files: int = 0, failed_files: int = 0,
                                last_checkpoint: Optional[str] = None,
                                completed: bool = False):
        """Update processing status for resumable jobs."""
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO processing_status (
                job_name, total_files, processed_files, failed_files,
                last_checkpoint, started_at, updated_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_name) DO UPDATE SET
                total_files=excluded.total_files,
                processed_files=excluded.processed_files,
                failed_files=excluded.failed_files,
                last_checkpoint=excluded.last_checkpoint,
                updated_at=excluded.updated_at,
                completed_at=excluded.completed_at
        """, (job_name, total_files, processed_files, failed_files,
              last_checkpoint, now, now, now if completed else None))

        self.conn.commit()

    def get_processing_status(self, job_name: str) -> Optional[Dict[str, Any]]:
        """Get processing status for a job."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM processing_status WHERE job_name = ?", (job_name,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_canonical_image_id(self, image_id: int) -> int:
        """
        Get the canonical (original) image ID for a given image.
        If the image is a duplicate, returns the ID of the original image.
        If the image is already an original or has no duplicate relationship, returns the same ID.

        Args:
            image_id: The image ID to look up

        Returns:
            The canonical image ID (original if duplicate, same ID otherwise)
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COALESCE(duplicate_of, id) as canonical_id
            FROM images
            WHERE id = ?
        """, (image_id,))
        result = cursor.fetchone()
        return result['canonical_id'] if result else image_id

    def set_rating(self, image_id: int, rating: int, comment: Optional[str] = None) -> int:
        """
        Set or update rating for an image.
        Automatically uses the canonical (original) image ID if the image is a duplicate.
        """
        # Always use canonical ID to ensure duplicates share the same rating
        canonical_id = self.get_canonical_image_id(image_id)

        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()

        # Check if rating already exists for canonical image
        cursor.execute("SELECT id FROM ratings WHERE image_id = ?", (canonical_id,))
        existing = cursor.fetchone()

        if existing:
            # Update existing rating
            cursor.execute("""
                UPDATE ratings SET rating = ?, comment = ?, updated_at = ?
                WHERE image_id = ?
            """, (rating, comment, now, canonical_id))
            rating_id = existing[0]
        else:
            # Insert new rating
            cursor.execute("""
                INSERT INTO ratings (image_id, rating, comment)
                VALUES (?, ?, ?)
            """, (canonical_id, rating, comment))
            rating_id = cursor.lastrowid

        self.conn.commit()
        return rating_id

    def get_rating(self, image_id: int) -> Optional[Dict[str, Any]]:
        """
        Get rating for an image.
        Automatically uses the canonical (original) image ID if the image is a duplicate.
        """
        # Always use canonical ID to ensure duplicates return the same rating
        canonical_id = self.get_canonical_image_id(image_id)

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM ratings WHERE image_id = ?", (canonical_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def delete_rating(self, image_id: int):
        """
        Delete rating for an image.
        Automatically uses the canonical (original) image ID if the image is a duplicate.
        """
        # Always use canonical ID to ensure deleting from duplicates affects the canonical rating
        canonical_id = self.get_canonical_image_id(image_id)

        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM ratings WHERE image_id = ?", (canonical_id,))
        self.conn.commit()

    def get_images_with_ratings(self, limit: Optional[int] = None,
                                offset: int = 0,
                                min_rating: Optional[int] = None,
                                max_rating: Optional[int] = None,
                                sort_by: str = 'created_at',
                                sort_order: str = 'DESC',
                                unique_only: bool = False,
                                tag_ids: Optional[List[int]] = None,
                                folder_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get images with their ratings, optionally filtered by tags and folder path."""
        cursor = self.conn.cursor()

        # If filtering by tags, we need to join with image_tags
        if tag_ids:
            query = """
                SELECT DISTINCT i.*, r.rating, r.comment as rating_comment, r.updated_at as rated_at
                FROM images i
                LEFT JOIN ratings r ON i.id = r.image_id
                INNER JOIN image_tags it ON i.id = it.image_id
                WHERE i.embedding_index IS NOT NULL
                AND it.tag_id IN ({})
            """.format(','.join('?' * len(tag_ids)))
            params = list(tag_ids)
        else:
            query = """
                SELECT i.*, r.rating, r.comment as rating_comment, r.updated_at as rated_at
                FROM images i
                LEFT JOIN ratings r ON i.id = r.image_id
                WHERE i.embedding_index IS NOT NULL
            """
            params = []

        if unique_only:
            query += " AND (i.is_duplicate IS NULL OR i.is_duplicate = 0)"

        if folder_path:
            query += " AND i.file_path LIKE ?"
            params.append(f"%{folder_path}%")

        if min_rating is not None:
            query += " AND r.rating >= ?"
            params.append(min_rating)

        if max_rating is not None:
            query += " AND r.rating <= ?"
            params.append(max_rating)

        # Validate sort column to prevent SQL injection
        allowed_sorts = ['created_at', 'rating', 'file_name', 'file_size', 'width', 'height']
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'

        if sort_order not in ['ASC', 'DESC']:
            sort_order = 'DESC'

        query += f" ORDER BY {sort_by} {sort_order}"

        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_rating_statistics(self) -> Dict[str, Any]:
        """Get rating statistics."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total_rated,
                AVG(rating) as avg_rating,
                MIN(rating) as min_rating,
                MAX(rating) as max_rating
            FROM ratings
        """)
        row = cursor.fetchone()

        # Get rating distribution
        cursor.execute("""
            SELECT rating, COUNT(*) as count
            FROM ratings
            GROUP BY rating
            ORDER BY rating
        """)
        distribution = {row[0]: row[1] for row in cursor.fetchall()}

        stats = dict(row) if row else {}
        stats['distribution'] = distribution

        return stats

    def detect_duplicates(self, hash_threshold: int = 5) -> List[tuple]:
        """
        Detect duplicate images based on perceptual hash similarity.

        Args:
            hash_threshold: Maximum hamming distance to consider duplicates (0-64)
                           0 = exact match, 5 = very similar, 10 = similar

        Returns:
            List of (image_id, duplicate_of_id, hash_distance) tuples
        """
        import imagehash

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, perceptual_hash, file_path
            FROM images
            WHERE perceptual_hash IS NOT NULL
            ORDER BY id
        """)

        images = cursor.fetchall()
        duplicates = []

        # Compare each image with every other image
        for i, img1 in enumerate(images):
            for img2 in images[i+1:]:
                if img1['perceptual_hash'] and img2['perceptual_hash']:
                    # Calculate hamming distance between hashes
                    hash1 = imagehash.hex_to_hash(img1['perceptual_hash'])
                    hash2 = imagehash.hex_to_hash(img2['perceptual_hash'])
                    distance = hash1 - hash2

                    if distance <= hash_threshold:
                        # img2 is duplicate of img1 (img1 is older/lower id)
                        duplicates.append((img2['id'], img1['id'], distance))

        return duplicates

    def mark_duplicates(self, hash_threshold: int = 5):
        """
        Mark duplicate images in the database.

        Args:
            hash_threshold: Maximum hamming distance to consider duplicates
        """
        duplicates = self.detect_duplicates(hash_threshold)
        cursor = self.conn.cursor()

        for dup_id, orig_id, distance in duplicates:
            cursor.execute("""
                UPDATE images
                SET is_duplicate = 1, duplicate_of = ?
                WHERE id = ?
            """, (orig_id, dup_id))

        self.conn.commit()
        print(f"Marked {len(duplicates)} duplicate images")
        return len(duplicates)

    def get_duplicate_groups(self) -> Dict[int, List[int]]:
        """
        Get groups of duplicate images.

        Returns:
            Dictionary mapping original image ID to list of duplicate IDs
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT duplicate_of, GROUP_CONCAT(id) as duplicate_ids
            FROM images
            WHERE is_duplicate = 1
            GROUP BY duplicate_of
        """)

        groups = {}
        for row in cursor.fetchall():
            orig_id = row['duplicate_of']
            dup_ids = [int(x) for x in row['duplicate_ids'].split(',')]
            groups[orig_id] = dup_ids

        return groups

    # ==================== Tag Management ====================

    def create_tag(self, name: str) -> int:
        """
        Create a new tag or return existing tag ID.

        Args:
            name: Tag name (case-sensitive, will be trimmed)

        Returns:
            Tag ID
        """
        name = name.strip()
        if not name:
            raise ValueError("Tag name cannot be empty")

        cursor = self.conn.cursor()

        # Try to get existing tag
        cursor.execute("SELECT id FROM tags WHERE name = ?", (name,))
        row = cursor.fetchone()

        if row:
            return row['id']

        # Create new tag
        cursor.execute(
            "INSERT INTO tags (name) VALUES (?)",
            (name,)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_all_tags(self) -> List[Dict[str, Any]]:
        """
        Get all tags with usage count.

        Returns:
            List of tag dictionaries with id, name, count, created_at
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                t.id,
                t.name,
                t.created_at,
                COUNT(DISTINCT it.image_id) as count
            FROM tags t
            LEFT JOIN image_tags it ON t.id = it.tag_id
            GROUP BY t.id
            ORDER BY t.name ASC
        """)

        return [dict(row) for row in cursor.fetchall()]

    def add_tag_to_image(self, image_id: int, tag_id: int) -> bool:
        """
        Add a tag to an image (uses canonical image ID).

        Args:
            image_id: Image ID (will be resolved to canonical)
            tag_id: Tag ID

        Returns:
            True if tag was added, False if already exists
        """
        # Resolve to canonical image
        canonical_id = self.get_canonical_image_id(image_id)

        cursor = self.conn.cursor()

        # Check if already exists
        cursor.execute(
            "SELECT 1 FROM image_tags WHERE image_id = ? AND tag_id = ?",
            (canonical_id, tag_id)
        )
        if cursor.fetchone():
            return False

        # Add tag
        cursor.execute(
            "INSERT INTO image_tags (image_id, tag_id) VALUES (?, ?)",
            (canonical_id, tag_id)
        )
        self.conn.commit()
        return True

    def remove_tag_from_image(self, image_id: int, tag_id: int) -> bool:
        """
        Remove a tag from an image (uses canonical image ID).

        Args:
            image_id: Image ID (will be resolved to canonical)
            tag_id: Tag ID

        Returns:
            True if tag was removed, False if didn't exist
        """
        # Resolve to canonical image
        canonical_id = self.get_canonical_image_id(image_id)

        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM image_tags WHERE image_id = ? AND tag_id = ?",
            (canonical_id, tag_id)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def get_tags_for_image(self, image_id: int) -> List[Dict[str, Any]]:
        """
        Get all tags for an image (uses canonical image ID).

        Args:
            image_id: Image ID (will be resolved to canonical)

        Returns:
            List of tag dictionaries with id, name
        """
        # Resolve to canonical image
        canonical_id = self.get_canonical_image_id(image_id)

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT t.id, t.name
            FROM tags t
            JOIN image_tags it ON t.id = it.tag_id
            WHERE it.image_id = ?
            ORDER BY t.name ASC
        """, (canonical_id,))

        return [dict(row) for row in cursor.fetchall()]

    def bulk_add_tags(self, image_ids: List[int], tag_ids: List[int]) -> int:
        """
        Add multiple tags to multiple images (bulk operation).

        Args:
            image_ids: List of image IDs (will be resolved to canonical)
            tag_ids: List of tag IDs

        Returns:
            Number of new tag associations created
        """
        if not image_ids or not tag_ids:
            return 0

        # Resolve all to canonical IDs
        canonical_ids = [self.get_canonical_image_id(img_id) for img_id in image_ids]

        cursor = self.conn.cursor()
        added = 0

        for img_id in canonical_ids:
            for tag_id in tag_ids:
                # Check if already exists
                cursor.execute(
                    "SELECT 1 FROM image_tags WHERE image_id = ? AND tag_id = ?",
                    (img_id, tag_id)
                )
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO image_tags (image_id, tag_id) VALUES (?, ?)",
                        (img_id, tag_id)
                    )
                    added += 1

        self.conn.commit()
        return added

    def delete_unused_tags(self) -> int:
        """
        Delete tags that are not assigned to any images.

        Returns:
            Number of tags deleted
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM tags
            WHERE id NOT IN (
                SELECT DISTINCT tag_id FROM image_tags
            )
        """)
        self.conn.commit()
        return cursor.rowcount

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
