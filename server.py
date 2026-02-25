#!/usr/bin/env python3
"""FastAPI HTTP server for semantic image search."""

from fastapi import FastAPI, File, UploadFile, Query, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from typing import List, Optional, Dict, Any
import tempfile
import os
import threading
import logging
import io
from datetime import datetime
from PIL import Image

from src.config import Config
from src.search import ImageSearchEngine, SearchResult
from src.pipeline import IndexingPipeline
from src.faiss_index import FAISSIndex
from src.embeddings import EmbeddingCache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# Initialize FastAPI app
app = FastAPI(
    title="Local Semantic Image Search API",
    description="Privacy-preserving local image search using CLIP embeddings and FAISS",
    version="0.1.0"
)

# Global search engine (initialized on startup)
search_engine: Optional[ImageSearchEngine] = None
config: Optional[Config] = None

# Indexing progress tracker
indexing_progress = {
    "is_indexing": False,
    "current_folder": None,
    "phase": None,  # "scanning", "processing", "embedding", "building_index", "complete"
    "total_images": 0,
    "processed_images": 0,
    "failed_images": 0,
    "start_time": None,
    "message": "Idle"
}
indexing_lock = threading.Lock()


class SearchResponse(BaseModel):
    """Response model for search results."""
    query: str
    num_results: int
    results: List[dict]


class StatsResponse(BaseModel):
    """Response model for stats."""
    total_images: int
    processed_images: int
    index_ready: bool


@app.on_event("startup")
async def startup_event():
    """Initialize search engine on startup."""
    global search_engine, config

    logger.info("=" * 60)
    logger.info("Starting server initialization...")
    logger.info("Step 1: Loading configuration...")
    config = Config()
    logger.info(f"Step 2: Creating search engine (hybrid mode)...")
    search_engine = ImageSearchEngine(config, use_hybrid=True)
    logger.info("Step 3: Initializing search engine components...")
    search_engine.initialize()
    logger.info("=" * 60)
    logger.info("✓ Server ready! All components initialized.")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    global search_engine

    logger.info("Shutting down server...")
    if search_engine:
        logger.info("Step 1: Closing search engine...")
        search_engine.close()
        logger.info("✓ Server shutdown complete")


@app.get("/")
async def root():
    """Root endpoint."""
    logger.info("GET / - Root endpoint accessed")
    return {
        "message": "Local Semantic Image Search API",
        "version": "0.1.0",
        "endpoints": {
            "search_text": "/search/text?q=<query>&top_k=<n>",
            "search_image": "/search/image (POST with image file)",
            "stats": "/stats",
            "health": "/health"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    global search_engine

    logger.info("GET /health - Health check")
    if search_engine is None:
        logger.warning("Health check failed: Search engine not initialized")
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    logger.info("✓ Health check passed")
    return {"status": "healthy", "search_engine": "ready"}


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get indexing statistics."""
    global search_engine, config

    logger.info("GET /stats - Fetching statistics...")
    if search_engine is None:
        logger.error("Stats request failed: Search engine not initialized")
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    logger.info("Step 1: Querying total images...")
    total = search_engine.db.get_total_images()
    logger.info("Step 2: Querying processed images...")
    processed = search_engine.db.get_processed_count()
    logger.info("Step 3: Checking index file...")
    index_ready = config.index_path.exists()
    logger.info(f"✓ Stats: {total:,} total, {processed:,} processed, index={'ready' if index_ready else 'not ready'}")

    return StatsResponse(
        total_images=total,
        processed_images=processed,
        index_ready=index_ready
    )


@app.get("/search/text", response_model=SearchResponse)
async def search_by_text(
    q: str = Query(..., description="Text query"),
    top_k: int = Query(20, ge=1, le=100, description="Number of results")
):
    """Search for images using text query."""
    global search_engine

    logger.info(f"GET /search/text - Query: '{q[:50]}{'...' if len(q) > 50 else ''}', top_k={top_k}")
    if search_engine is None:
        logger.error("Text search failed: Search engine not initialized")
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    try:
        logger.info("Step 1: Encoding text query to embedding...")
        logger.info(f"Step 1a: Checking if embedding model is loaded...")
        if search_engine.embedding_model is None:
            logger.warning("Model not loaded! Initializing now (this may take time)...")
        else:
            logger.info("Model already loaded, encoding text...")
        results = search_engine.search_by_text(q, top_k=top_k)
        logger.info(f"Step 2: Search returned {len(results)} results")
        logger.info("Step 3: Converting results to dict...")
        results_dict = [r.to_dict() for r in results]

        logger.info("Step 4: Adding folder tags to results...")
        for result in results_dict:
            result['folders'] = extract_folder_tags(result.get('file_path', ''))

        logger.info(f"✓ Text search complete: {len(results)} results")
        return SearchResponse(
            query=q,
            num_results=len(results),
            results=results_dict
        )
    except Exception as e:
        logger.error(f"✗ Text search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/image", response_model=SearchResponse)
async def search_by_image(
    file: UploadFile = File(..., description="Query image"),
    top_k: int = Query(20, ge=1, le=100, description="Number of results")
):
    """Search for similar images using an uploaded image."""
    global search_engine

    logger.info(f"POST /search/image - File: {file.filename}, top_k={top_k}")
    if search_engine is None:
        logger.error("Image search failed: Search engine not initialized")
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    tmp_path = None
    try:
        logger.info("Step 1: Saving uploaded file to temp location...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name
        logger.info(f"Step 2: Temp file saved: {tmp_path}")

        logger.info("Step 3: Encoding image to embedding...")
        results = search_engine.search_by_image(tmp_path, top_k=top_k)
        logger.info(f"Step 4: Search returned {len(results)} results")

        logger.info("Step 5: Cleaning up temp file...")
        os.unlink(tmp_path)
        tmp_path = None

        logger.info(f"✓ Image search complete: {len(results)} results")
        return SearchResponse(
            query=file.filename,
            num_results=len(results),
            results=[r.to_dict() for r in results]
        )

    except Exception as e:
        logger.error(f"✗ Image search error: {e}")
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
                logger.info("Cleaned up temp file after error")
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/thumbnail/{image_id}")
async def get_thumbnail(image_id: int, size: int = Query(384, ge=50, le=1024, description="Thumbnail max size")):
    """Get thumbnail for an image by ID. If thumbnail doesn't exist, serves resized full image."""
    global search_engine, config

    logger.info(f"GET /thumbnail/{image_id} - Requesting thumbnail (size={size})")
    if search_engine is None:
        logger.error("Thumbnail request failed: Search engine not initialized")
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    cursor = search_engine.db.conn.cursor()
    
    # Try to get existing thumbnail first
    logger.info("Step 1: Checking for existing thumbnail...")
    cursor.execute("SELECT thumbnail_path, file_path FROM images WHERE id = ?", (image_id,))
    row = cursor.fetchone()

    if not row:
        logger.warning(f"Image not found: image_id={image_id}")
        raise HTTPException(status_code=404, detail="Image not found")

    thumbnail_path = row['thumbnail_path'] if row else None
    file_path = Path(row['file_path'])

    # If thumbnail exists and is valid, serve it
    if thumbnail_path:
        thumb_path = Path(thumbnail_path)
        if thumb_path.exists():
            logger.info(f"✓ Serving existing thumbnail: {thumb_path}")
            return FileResponse(thumb_path, media_type="image/jpeg")

    # Thumbnail doesn't exist - serve resized full image on-the-fly
    logger.info(f"Step 2: Thumbnail not found, resizing full image on-the-fly: {file_path}")
    
    if not file_path.exists():
        logger.error(f"Image file not found: {file_path}")
        raise HTTPException(status_code=404, detail="Image file not found")

    try:
        # Open and resize image
        with Image.open(file_path) as img:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Create thumbnail (maintains aspect ratio)
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            
            # Save to in-memory buffer
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='JPEG', quality=85, optimize=True)
            img_buffer.seek(0)
            
            logger.info(f"✓ Serving resized image ({img.width}×{img.height})")
            return Response(
                content=img_buffer.getvalue(),
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=3600"}
            )
    
    except Exception as e:
        logger.error(f"✗ Error resizing image: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")


@app.get("/image/{image_id}")
async def get_image_info(image_id: int):
    """Get full information about an image."""
    global search_engine

    logger.info(f"GET /image/{image_id} - Requesting image info")
    if search_engine is None:
        logger.error("Image info request failed: Search engine not initialized")
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    logger.info("Step 1: Querying database for image data...")
    cursor = search_engine.db.conn.cursor()
    cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
    row = cursor.fetchone()

    if not row:
        logger.warning(f"Image not found: image_id={image_id}")
        raise HTTPException(status_code=404, detail="Image not found")

    logger.info(f"✓ Image info retrieved: {row.get('file_name', 'unknown')}")
    return dict(row)


@app.get("/image/{image_id}/similar")
async def get_similar_images(
    image_id: int,
    limit: int = Query(12, ge=1, le=50, description="Maximum number of similar images to return")
):
    """
    Get similar images for a given image.
    Returns both exact duplicates and semantically similar images.
    """
    global search_engine

    logger.info(f"GET /image/{image_id}/similar - Finding similar images (limit={limit})")
    if search_engine is None:
        logger.error("Similar images request failed: Search engine not initialized")
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    db = search_engine.db
    cursor = db.conn.cursor()

    logger.info("Step 1: Fetching query image info...")
    cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
    image = cursor.fetchone()

    if not image:
        logger.warning(f"Query image not found: image_id={image_id}")
        raise HTTPException(status_code=404, detail="Image not found")

    logger.info("Step 2: Getting canonical ID...")
    canonical_id = db.get_canonical_image_id(image_id)

    # Part 1: Find duplicates
    duplicates = []

    # Get all images in the same duplicate group
    if image['is_duplicate'] == 1:
        # This is a duplicate, find the original and all other duplicates
        original_id = image['duplicate_of']
        cursor.execute("""
            SELECT id, file_name, file_path, width, height, thumbnail_path
            FROM images
            WHERE id = ? OR (duplicate_of = ? AND id != ?)
            ORDER BY id
        """, (original_id, original_id, image_id))
    else:
        # This might be an original, find all its duplicates
        cursor.execute("""
            SELECT id, file_name, file_path, width, height, thumbnail_path
            FROM images
            WHERE duplicate_of = ? AND id != ?
            ORDER BY id
        """, (canonical_id, image_id))

    duplicate_rows = cursor.fetchall()
    duplicates = [dict(row) for row in duplicate_rows]
    logger.info(f"Step 3: Found {len(duplicates)} duplicate images")

    # Part 2: Find semantically similar images using embeddings
    similar = []

    if image['embedding_index'] is not None and search_engine.hybrid_search is not None:
        logger.info("Step 4: Searching for semantically similar images...")
        # Get this image's embedding
        embedding_idx = image['embedding_index']
        embedding = search_engine.hybrid_search.embeddings_cache[embedding_idx]
        logger.info(f"Step 5: Retrieved embedding at index {embedding_idx}")

        # Search for similar images (get more than needed, we'll filter)
        search_results = search_engine.search_by_embedding(
            embedding,
            top_k=limit + len(duplicates) + 10  # Extra to account for filtering
        )
        logger.info(f"Step 6: Initial search returned {len(search_results)} candidates")

        # Filter out: the query image itself, duplicates (already shown), and convert to dict
        duplicate_ids = {d['id'] for d in duplicates}
        duplicate_ids.add(image_id)  # Also exclude the query image
        logger.info("Step 7: Filtering results (excluding duplicates and query image)...")

        for result in search_results:
            if result.image_id not in duplicate_ids:
                # Get canonical ID for this result to avoid showing duplicate variants
                result_canonical = db.get_canonical_image_id(result.image_id)
                if result_canonical not in duplicate_ids:
                    similar.append({
                        'id': result.image_id,
                        'file_name': result.file_name,
                        'file_path': result.file_path,
                        'width': result.width,
                        'height': result.height,
                        'thumbnail_path': result.thumbnail_path,
                        'similarity': float(result.score)
                    })
                    duplicate_ids.add(result_canonical)  # Prevent showing other duplicates of this result

                if len(similar) >= limit:
                    break

        logger.info(f"Step 8: Filtered to {len(similar)} similar images")
    else:
        logger.warning(f"Image has no embedding (index={image.get('embedding_index')}) or hybrid_search not available")

    logger.info(f"✓ Similar images complete: {len(duplicates)} duplicates, {len(similar)} similar")
    return {
        'duplicates': duplicates,
        'similar': similar
    }


@app.post("/open-in-explorer/{image_id}")
async def open_in_explorer(image_id: int):
    """
    Open the image file location in the OS file explorer.
    macOS: Finder
    Windows: File Explorer
    Linux: Default file manager
    """
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    # Get the image file path
    cursor = search_engine.db.conn.cursor()
    cursor.execute("SELECT file_path FROM images WHERE id = ?", (image_id,))
    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Image not found")

    file_path = Path(row['file_path'])

    # Check if file exists
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found at {file_path}")

    # Platform-specific commands
    import platform
    import subprocess

    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            # Use 'open -R' to reveal file in Finder
            subprocess.run(["open", "-R", str(file_path)], check=True)
        elif system == "Windows":
            # Use 'explorer /select,' to open and select file
            subprocess.run(["explorer", "/select,", str(file_path)], check=True)
        else:  # Linux and others
            # Try xdg-open with the parent directory
            subprocess.run(["xdg-open", str(file_path.parent)], check=True)

        return {"success": True, "message": f"Opened {file_path.name} in file explorer"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to open file explorer: {str(e)}")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail=f"File explorer command not found for {system}")


# Browse and pagination endpoints
class BrowseResponse(BaseModel):
    """Response model for browse results."""
    total: int
    page: int
    per_page: int
    total_pages: int
    images: List[dict]


class RatingRequest(BaseModel):
    """Request model for setting a rating."""
    rating: int
    comment: Optional[str] = None


class TagRequest(BaseModel):
    """Request model for creating a tag."""
    name: str


class AddTagRequest(BaseModel):
    """Request model for adding a tag to an image."""
    tag_id: int


class BulkTagRequest(BaseModel):
    """Request model for bulk tagging."""
    image_ids: List[int]
    tag_ids: List[int]


class IndexFolderRequest(BaseModel):
    """Request model for indexing a folder."""
    folder_path: str


def extract_folder_tags(file_path: str, max_depth: int = 3) -> List[str]:
    """
    Extract folder names from an image path for display as tags.

    Args:
        file_path: Full path to the image file
        max_depth: Maximum number of folder segments to return

    Returns:
        Ordered list of folder names (excluding filename)
    """
    path = Path(file_path)
    skip_parts = {os.sep, '', '.'}

    if config:
        skip_parts.add(str(config.data_dir.name))
        skip_parts.add('sources')

    parts: List[str] = []
    for part in path.parent.parts:
        if part.endswith(":"):
            # Skip Windows drive letters (e.g., 'C:')
            continue
        if part in skip_parts:
            continue
        parts.append(part)

    if len(parts) > max_depth:
        parts = parts[-max_depth:]

    return parts


@app.get("/browse", response_model=BrowseResponse)
async def browse_images(
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100),
    min_rating: Optional[int] = Query(None, ge=1, le=5),
    max_rating: Optional[int] = Query(None, ge=1, le=5),
    sort_by: str = Query("created_at", regex="^(created_at|rating|file_name|file_size|width|height)$"),
    sort_order: str = Query("DESC", regex="^(ASC|DESC)$"),
    tag_ids: Optional[str] = Query(None, description="Comma-separated tag IDs to filter by"),
    folder_path: Optional[str] = Query(None, description="Filter by folder path (substring match)")
):
    """Browse images with pagination and filtering. Always shows unique images only."""
    global search_engine

    filters = []
    if min_rating: filters.append(f"min_rating={min_rating}")
    if max_rating: filters.append(f"max_rating={max_rating}")
    if tag_ids: filters.append(f"tags={tag_ids}")
    if folder_path: filters.append(f"folder={folder_path[:30]}")
    filter_str = f" [{', '.join(filters)}]" if filters else ""
    logger.info(f"GET /browse - Page {page}, {per_page} per page, sort={sort_by}({sort_order}){filter_str}")

    if search_engine is None:
        logger.error("Browse request failed: Search engine not initialized")
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    # Calculate offset
    offset = (page - 1) * per_page
    logger.info(f"Step 1: Calculating offset: {offset}")

    # Parse tag_ids if provided
    tag_id_list = None
    if tag_ids:
        logger.info("Step 2: Parsing tag IDs...")
        try:
            tag_id_list = [int(tid) for tid in tag_ids.split(',') if tid.strip()]
            logger.info(f"Parsed {len(tag_id_list)} tag IDs")
        except ValueError:
            logger.error(f"Invalid tag_ids format: {tag_ids}")
            raise HTTPException(status_code=400, detail="Invalid tag_ids format")

    # Get images (always unique only)
    logger.info("Step 3: Fetching images from database...")
    images = search_engine.db.get_images_with_ratings(
        limit=per_page,
        offset=offset,
        min_rating=min_rating,
        max_rating=max_rating,
        sort_by=sort_by,
        sort_order=sort_order,
        unique_only=True,  # Always filter duplicates
        tag_ids=tag_id_list,
        folder_path=folder_path
    )
    logger.info(f"Step 4: Retrieved {len(images)} images")

    cursor = search_engine.db.conn.cursor()

    logger.info("Step 5: Enriching images with folder tags and duplicate counts...")
    
    # Get all image IDs first
    image_ids = [img['id'] for img in images]
    
    # Fetch all duplicate counts in one query (much faster!)
    duplicate_counts = {}
    if image_ids:
        placeholders = ','.join('?' * len(image_ids))
        cursor.execute(f"""
            SELECT duplicate_of, COUNT(*) as count
            FROM images
            WHERE duplicate_of IN ({placeholders})
            GROUP BY duplicate_of
        """, image_ids)
        for row in cursor.fetchall():
            duplicate_counts[row['duplicate_of']] = row['count']

    # Add folder tags and duplicate count to each image
    for img in images:
        img['folders'] = extract_folder_tags(img['file_path'])
        img['duplicate_count'] = duplicate_counts.get(img['id'], 0)

    # Get total count (unique images only, with tag and folder filter if applicable)
    count_params = []
    if tag_id_list:
        # Count with tag filter
        placeholders = ','.join('?' * len(tag_id_list))
        count_query = f"""
            SELECT COUNT(DISTINCT i.id) as count
            FROM images i
            INNER JOIN image_tags it ON i.id = it.image_id
            WHERE i.embedding_index IS NOT NULL
            AND (i.is_duplicate IS NULL OR i.is_duplicate = 0)
            AND it.tag_id IN ({placeholders})
        """
        count_params.extend(tag_id_list)
        if folder_path:
            count_query += " AND i.file_path LIKE ?"
            count_params.append(f"%{folder_path}%")
        cursor.execute(count_query, count_params)
    else:
        # Count without tag filter
        count_query = """
            SELECT COUNT(*) as count
            FROM images
            WHERE embedding_index IS NOT NULL
            AND (is_duplicate IS NULL OR is_duplicate = 0)
        """
        if folder_path:
            count_query += " AND file_path LIKE ?"
            count_params.append(f"%{folder_path}%")
        cursor.execute(count_query, count_params)
    logger.info("Step 6: Counting total images...")
    total = cursor.fetchone()['count']
    logger.info(f"Total images matching filters: {total:,}")

    total_pages = (total + per_page - 1) // per_page
    logger.info(f"✓ Browse complete: {len(images)} images on page {page}/{total_pages}")

    return BrowseResponse(
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        images=[dict(img) for img in images]
    )


@app.get("/search/image/{image_id}", response_model=BrowseResponse)
async def search_by_similar_image(
    image_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100)
):
    """
    Search for images similar to the given image with pagination.
    Full-page search results view (not modal thumbnails).
    """
    global search_engine

    logger.info(f"GET /search/image/{image_id} - Similar image search (page {page}, {per_page} per page)")
    if search_engine is None:
        logger.error("Similar image search failed: Search engine not initialized")
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    db = search_engine.db
    cursor = db.conn.cursor()

    logger.info("Step 1: Fetching query image info...")
    cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
    image = cursor.fetchone()

    if not image:
        logger.warning(f"Query image not found: image_id={image_id}")
        raise HTTPException(status_code=404, detail="Image not found")

    logger.info("Step 2: Getting canonical ID...")
    canonical_id = db.get_canonical_image_id(image_id)

    logger.info("Step 3: Checking embedding availability...")
    if image['embedding_index'] is None or search_engine.hybrid_search is None:
        logger.error(f"Image has no embedding (index={image.get('embedding_index')})")
        raise HTTPException(status_code=400, detail="Image has no embedding")

    embedding_idx = image['embedding_index']
    embedding = search_engine.hybrid_search.embeddings_cache[embedding_idx]
    logger.info(f"Step 4: Retrieved embedding at index {embedding_idx}")

    logger.info("Step 5: Searching for similar images...")
    max_results = 1000
    search_results = search_engine.search_by_embedding(
        embedding,
        top_k=max_results
    )
    logger.info(f"Step 6: Initial search returned {len(search_results)} candidates")

    # Build set of IDs to exclude (query image + all its duplicates)
    exclude_ids = set()

    # Get all duplicates of the query image
    if image['is_duplicate'] == 1:
        original_id = image['duplicate_of']
        cursor.execute("SELECT id FROM images WHERE id = ? OR duplicate_of = ?",
                      (original_id, original_id))
    else:
        cursor.execute("SELECT id FROM images WHERE duplicate_of = ?",
                      (canonical_id,))

    for row in cursor.fetchall():
        exclude_ids.add(row['id'])

    exclude_ids.add(image_id)  # Also exclude query image itself
    logger.info(f"Step 7: Excluding {len(exclude_ids)} duplicate/query images...")

    logger.info("Step 8: Filtering results (removing duplicates)...")
    # Filter results: remove query image, its duplicates, and duplicate variants
    filtered_results = []
    seen_canonical_ids = set()

    for result in search_results:
        if result.image_id in exclude_ids:
            continue

        # Get canonical ID for this result to avoid showing duplicate variants
        result_canonical = db.get_canonical_image_id(result.image_id)
        if result_canonical in exclude_ids or result_canonical in seen_canonical_ids:
            continue

        seen_canonical_ids.add(result_canonical)
        filtered_results.append(result)

    logger.info(f"Step 9: Filtered to {len(filtered_results)} unique results")

    logger.info("Step 10: Applying pagination...")
    # Apply pagination
    total = len(filtered_results)
    total_pages = (total + per_page - 1) // per_page
    offset = (page - 1) * per_page

    paginated_results = filtered_results[offset:offset + per_page]

    # Get all image IDs first for batch queries
    result_image_ids = [r.image_id for r in paginated_results]
    
    # Fetch all duplicate counts in one query (much faster!)
    duplicate_counts = {}
    if result_image_ids:
        placeholders = ','.join('?' * len(result_image_ids))
        cursor.execute(f"""
            SELECT duplicate_of, COUNT(*) as count
            FROM images
            WHERE duplicate_of IN ({placeholders})
            GROUP BY duplicate_of
        """, result_image_ids)
        for row in cursor.fetchall():
            duplicate_counts[row['duplicate_of']] = row['count']
    
    # Fetch all image data in one query
    images_dict = {}
    if result_image_ids:
        placeholders = ','.join('?' * len(result_image_ids))
        cursor.execute(f"""
            SELECT * FROM images WHERE id IN ({placeholders})
        """, result_image_ids)
        for row in cursor.fetchall():
            images_dict[row['id']] = dict(row)

    # Convert to image dict format (matching browse response)
    images = []
    for result in paginated_results:
        if result.image_id in images_dict:
            img_dict = images_dict[result.image_id].copy()
            img_dict['folders'] = extract_folder_tags(img_dict['file_path'])
            img_dict['similarity_score'] = float(result.score)
            img_dict['duplicate_count'] = duplicate_counts.get(result.image_id, 0)
            images.append(img_dict)

    logger.info(f"✓ Similar image search complete: {len(images)} images on page {page}/{total_pages}")
    return BrowseResponse(
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        images=images
    )


@app.get("/image/{image_id}/duplicates")
async def get_image_duplicates(image_id: int):
    """
    Get all duplicate images for a given image.
    Returns array of duplicates with file paths.
    """
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    db = search_engine.db
    cursor = db.conn.cursor()

    # Get the image info
    cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
    image = cursor.fetchone()

    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    # Get canonical ID
    canonical_id = db.get_canonical_image_id(image_id)

    # Get all duplicates of this image
    cursor.execute("""
        SELECT id, file_name, file_path, thumbnail_path, width, height
        FROM images
        WHERE duplicate_of = ?
        ORDER BY file_name
    """, (canonical_id,))

    duplicates = [dict(row) for row in cursor.fetchall()]

    return {
        'canonical_id': canonical_id,
        'count': len(duplicates),
        'duplicates': duplicates
    }


@app.post("/rating/{image_id}")
async def set_rating(image_id: int, rating_data: RatingRequest):
    """Set or update rating for an image."""
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    if rating_data.rating < 1 or rating_data.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    try:
        rating_id = search_engine.db.set_rating(
            image_id=image_id,
            rating=rating_data.rating,
            comment=rating_data.comment
        )
        return {"success": True, "rating_id": rating_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rating/{image_id}")
async def get_rating(image_id: int):
    """Get rating for an image."""
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    rating = search_engine.db.get_rating(image_id)
    if rating:
        return rating
    else:
        return {"image_id": image_id, "rating": None, "comment": None}


@app.delete("/rating/{image_id}")
async def delete_rating(image_id: int):
    """Delete rating for an image."""
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    search_engine.db.delete_rating(image_id)
    return {"success": True}


@app.get("/rating-stats")
async def get_rating_stats():
    """Get rating statistics."""
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    return search_engine.db.get_rating_statistics()


# ==================== Tag Endpoints ====================

@app.get("/tags")
async def get_all_tags():
    """Get all tags with usage counts."""
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    try:
        tags = search_engine.db.get_all_tags()
        return {"tags": tags}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tags")
async def create_tag(tag_data: TagRequest):
    """Create a new tag."""
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    try:
        tag_id = search_engine.db.create_tag(tag_data.name)
        return {"success": True, "tag_id": tag_id, "name": tag_data.name.strip()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/image/{image_id}/tags")
async def get_image_tags(image_id: int):
    """Get all tags for an image."""
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    try:
        tags = search_engine.db.get_tags_for_image(image_id)
        return {"tags": tags}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/image/{image_id}/tags")
async def add_tag_to_image(image_id: int, tag_data: AddTagRequest):
    """Add a tag to an image."""
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    try:
        added = search_engine.db.add_tag_to_image(image_id, tag_data.tag_id)
        return {"success": True, "added": added}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/image/{image_id}/tags/{tag_id}")
async def remove_tag_from_image(image_id: int, tag_id: int):
    """Remove a tag from an image."""
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    try:
        removed = search_engine.db.remove_tag_from_image(image_id, tag_id)
        return {"success": True, "removed": removed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tags/bulk")
async def bulk_add_tags(bulk_data: BulkTagRequest):
    """Add multiple tags to multiple images (bulk operation)."""
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    try:
        added_count = search_engine.db.bulk_add_tags(bulk_data.image_ids, bulk_data.tag_ids)
        return {"success": True, "added_count": added_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Indexing Endpoints ====================

def run_indexing(folder_path: str):
    """Background task to run indexing."""
    global indexing_progress, search_engine, config

    with indexing_lock:
        if indexing_progress["is_indexing"]:
            return

        indexing_progress["is_indexing"] = True
        indexing_progress["current_folder"] = folder_path
        indexing_progress["start_time"] = datetime.now().isoformat()
        indexing_progress["total_images"] = 0
        indexing_progress["processed_images"] = 0
        indexing_progress["failed_images"] = 0

    try:
        # Create pipeline
        pipeline = IndexingPipeline(config)

        # Phase 1: Scan and register
        indexing_progress["phase"] = "scanning"
        indexing_progress["message"] = f"Scanning folder: {folder_path}"
        num_registered = pipeline.scan_and_register_images(Path(folder_path))
        indexing_progress["total_images"] = num_registered

        if num_registered == 0:
            indexing_progress["message"] = "No new images found"
            indexing_progress["phase"] = "complete"
            return

        # Phase 2: Process embeddings
        indexing_progress["phase"] = "embedding"
        indexing_progress["message"] = f"Generating embeddings for {num_registered} images"
        pipeline.initialize_model()
        pipeline.generate_embeddings(resume=True)

        # Phase 3: Build index
        indexing_progress["phase"] = "building_index"
        indexing_progress["message"] = "Rebuilding search index"

        # Load embeddings
        embedding_cache = EmbeddingCache(config.embeddings_path)
        embeddings = embedding_cache.load()

        # Build index
        faiss_index = FAISSIndex(config.embedding_dim, config.index_path)
        if len(embeddings) < 100:
            faiss_index.build_flat_index(embeddings, use_gpu=config.device == "cuda")
        else:
            faiss_index.build_ivf_pq_index(
                embeddings,
                nlist=config.nlist,
                m=config.m_pq,
                nbits=config.nbits_pq,
                use_gpu=config.device == "cuda"
            )
        faiss_index.save()

        # Phase 4: Detect duplicates
        indexing_progress["phase"] = "duplicates"
        indexing_progress["message"] = "Detecting duplicates"
        num_duplicates = pipeline.db.mark_duplicates(
            hash_threshold=config.duplicate_hash_threshold
        )

        # Complete
        indexing_progress["phase"] = "complete"
        indexing_progress["message"] = f"Indexed {num_registered} images ({num_duplicates} duplicates found)"

        # Reload search engine
        if search_engine:
            search_engine.initialize()

    except Exception as e:
        indexing_progress["phase"] = "error"
        indexing_progress["message"] = f"Error: {str(e)}"
    finally:
        with indexing_lock:
            indexing_progress["is_indexing"] = False


@app.post("/index/folder")
async def index_folder(request: IndexFolderRequest, background_tasks: BackgroundTasks):
    """Start indexing a folder in the background."""
    global config

    folder_path = Path(request.folder_path)

    # Validate folder exists
    if not folder_path.exists():
        raise HTTPException(status_code=400, detail=f"Folder not found: {folder_path}")

    if not folder_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {folder_path}")

    # Check if already indexing
    with indexing_lock:
        if indexing_progress["is_indexing"]:
            return {
                "success": False,
                "message": "Indexing already in progress",
                "current_folder": indexing_progress["current_folder"]
            }

    # Start background task
    background_tasks.add_task(run_indexing, str(folder_path))

    return {
        "success": True,
        "message": f"Started indexing: {folder_path}",
        "folder": str(folder_path)
    }


@app.get("/index/progress")
async def get_index_progress():
    """Get current indexing progress."""
    return indexing_progress


@app.get("/ui", response_class=HTMLResponse)
async def serve_ui():
    """Serve the web UI."""
    ui_path = Path(__file__).parent / "static" / "index.html"
    if ui_path.exists():
        with open(ui_path) as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head><title>Image Explorer</title></head>
        <body>
            <h1>UI not found</h1>
            <p>Please create static/index.html</p>
        </body>
        </html>
        """, status_code=404)


# Mount static files directory
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
