#!/usr/bin/env python3
"""FastAPI HTTP server for semantic image search."""

from fastapi import FastAPI, File, UploadFile, Query, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from typing import List, Optional, Dict, Any
import tempfile
import os
import threading
from datetime import datetime

from src.config import Config
from src.search import ImageSearchEngine, SearchResult
from src.pipeline import IndexingPipeline
from src.faiss_index import FAISSIndex
from src.embeddings import EmbeddingCache


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

    print("Initializing search engine...")
    config = Config()
    search_engine = ImageSearchEngine(config, use_hybrid=True)
    search_engine.initialize()
    print("Search engine ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    global search_engine

    if search_engine:
        search_engine.close()
        print("Search engine closed")


@app.get("/")
async def root():
    """Root endpoint."""
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

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    return {"status": "healthy", "search_engine": "ready"}


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get indexing statistics."""
    global search_engine, config

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    total = search_engine.db.get_total_images()
    processed = search_engine.db.get_processed_count()
    index_ready = config.index_path.exists()

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

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    try:
        results = search_engine.search_by_text(q, top_k=top_k)
        results_dict = [r.to_dict() for r in results]

        # Add folder tags to each result
        for result in results_dict:
            result['folders'] = extract_folder_tags(result.get('file_path', ''))

        return SearchResponse(
            query=q,
            num_results=len(results),
            results=results_dict
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/image", response_model=SearchResponse)
async def search_by_image(
    file: UploadFile = File(..., description="Query image"),
    top_k: int = Query(20, ge=1, le=100, description="Number of results")
):
    """Search for similar images using an uploaded image."""
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    # Save uploaded file to temporary location
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        # Perform search
        results = search_engine.search_by_image(tmp_path, top_k=top_k)

        # Clean up temp file
        os.unlink(tmp_path)

        return SearchResponse(
            query=file.filename,
            num_results=len(results),
            results=[r.to_dict() for r in results]
        )

    except Exception as e:
        # Clean up temp file on error
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/thumbnail/{image_id}")
async def get_thumbnail(image_id: int):
    """Get thumbnail for an image by ID."""
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    # Get image record
    cursor = search_engine.db.conn.cursor()
    cursor.execute("SELECT thumbnail_path FROM images WHERE id = ?", (image_id,))
    row = cursor.fetchone()

    if not row or not row['thumbnail_path']:
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    thumbnail_path = Path(row['thumbnail_path'])
    if not thumbnail_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file not found")

    return FileResponse(thumbnail_path, media_type="image/jpeg")


@app.get("/image/{image_id}")
async def get_image_info(image_id: int):
    """Get full information about an image."""
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    cursor = search_engine.db.conn.cursor()
    cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Image not found")

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

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    db = search_engine.db
    cursor = db.conn.cursor()

    # Get the image info
    cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
    image = cursor.fetchone()

    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    # Get canonical ID (in case this is a duplicate)
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

    # Part 2: Find semantically similar images using embeddings
    similar = []

    if image['embedding_index'] is not None and search_engine.hybrid_search is not None:
        # Get this image's embedding
        embedding_idx = image['embedding_index']
        embedding = search_engine.hybrid_search.embeddings_cache[embedding_idx]

        # Search for similar images (get more than needed, we'll filter)
        search_results = search_engine.search_by_embedding(
            embedding,
            top_k=limit + len(duplicates) + 10  # Extra to account for filtering
        )

        # Filter out: the query image itself, duplicates (already shown), and convert to dict
        duplicate_ids = {d['id'] for d in duplicates}
        duplicate_ids.add(image_id)  # Also exclude the query image

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


def extract_folder_tags(file_path: str, root_path: str = "data/sources") -> List[str]:
    """
    Extract folder names from file path, excluding the root path.

    Args:
        file_path: Full path to the image file
        root_path: Root directory to exclude from tags

    Returns:
        List of folder names (excluding root and filename)
    """
    path = Path(file_path)
    root = Path(root_path)

    try:
        # Get relative path from root
        relative = path.relative_to(root)
        # Get all parent directories (exclude filename)
        folders = list(relative.parent.parts)
        # Filter out empty strings and '.'
        return [f for f in folders if f and f != '.']
    except ValueError:
        # Path is not relative to root, return empty list
        return []


@app.get("/browse", response_model=BrowseResponse)
async def browse_images(
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100),
    min_rating: Optional[int] = Query(None, ge=1, le=5),
    max_rating: Optional[int] = Query(None, ge=1, le=5),
    sort_by: str = Query("created_at", regex="^(created_at|rating|file_name|file_size|width|height)$"),
    sort_order: str = Query("DESC", regex="^(ASC|DESC)$"),
    tag_ids: Optional[str] = Query(None, description="Comma-separated tag IDs to filter by")
):
    """Browse images with pagination and filtering. Always shows unique images only."""
    global search_engine

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    # Calculate offset
    offset = (page - 1) * per_page

    # Parse tag_ids if provided
    tag_id_list = None
    if tag_ids:
        try:
            tag_id_list = [int(tid) for tid in tag_ids.split(',') if tid.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tag_ids format")

    # Get images (always unique only)
    images = search_engine.db.get_images_with_ratings(
        limit=per_page,
        offset=offset,
        min_rating=min_rating,
        max_rating=max_rating,
        sort_by=sort_by,
        sort_order=sort_order,
        unique_only=True,  # Always filter duplicates
        tag_ids=tag_id_list
    )

    cursor = search_engine.db.conn.cursor()

    # Add folder tags and duplicate count to each image
    for img in images:
        img['folders'] = extract_folder_tags(img['file_path'])

        # Get duplicate count
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM images
            WHERE duplicate_of = ?
        """, (img['id'],))
        img['duplicate_count'] = cursor.fetchone()['count']

    # Get total count (unique images only, with tag filter if applicable)
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
        cursor.execute(count_query, tag_id_list)
    else:
        # Count without tag filter
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM images
            WHERE embedding_index IS NOT NULL
            AND (is_duplicate IS NULL OR is_duplicate = 0)
        """)
    total = cursor.fetchone()['count']

    total_pages = (total + per_page - 1) // per_page

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

    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")

    db = search_engine.db
    cursor = db.conn.cursor()

    # Get the source image info
    cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
    image = cursor.fetchone()

    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    # Get canonical ID to exclude duplicates
    canonical_id = db.get_canonical_image_id(image_id)

    # Get embedding for this image
    if image['embedding_index'] is None or search_engine.hybrid_search is None:
        raise HTTPException(status_code=400, detail="Image has no embedding")

    embedding_idx = image['embedding_index']
    embedding = search_engine.hybrid_search.embeddings_cache[embedding_idx]

    # Search for similar images (get many results for pagination)
    max_results = 1000
    search_results = search_engine.search_by_embedding(
        embedding,
        top_k=max_results
    )

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

    # Apply pagination
    total = len(filtered_results)
    total_pages = (total + per_page - 1) // per_page
    offset = (page - 1) * per_page

    paginated_results = filtered_results[offset:offset + per_page]

    # Convert to image dict format (matching browse response)
    images = []
    for result in paginated_results:
        cursor.execute("SELECT * FROM images WHERE id = ?", (result.image_id,))
        img_row = cursor.fetchone()
        if img_row:
            img_dict = dict(img_row)
            img_dict['folders'] = extract_folder_tags(img_dict['file_path'])
            img_dict['similarity_score'] = float(result.score)  # Add similarity score

            # Get duplicate count
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM images
                WHERE duplicate_of = ?
            """, (result.image_id,))
            img_dict['duplicate_count'] = cursor.fetchone()['count']

            images.append(img_dict)

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
