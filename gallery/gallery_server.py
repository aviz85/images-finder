#!/usr/bin/env python3
"""
Gallery Review Server
FastAPI server for the image gallery review system.

Usage:
    python gallery_server.py [--port PORT] [--host HOST]

    # Or with uvicorn directly:
    uvicorn gallery_server:app --host 0.0.0.0 --port 8080 --reload
"""

import sys
import os
import subprocess
from pathlib import Path
from typing import Optional, List
import argparse

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from gallery.gallery_db import GalleryDB, path_to_thumbnail_name

# Configuration
GALLERY_DIR = Path(__file__).parent
THUMBNAILS_DIR = GALLERY_DIR / "thumbnails"
STATIC_DIR = GALLERY_DIR / "static"
DB_PATH = GALLERY_DIR / "gallery.db"

# Search engine (lazy loaded)
_search_engine = None


def get_search_engine():
    """Lazy load the search engine."""
    global _search_engine
    if _search_engine is None:
        try:
            from src.config import load_config
            from src.search import ImageSearchEngine

            config_path = Path(__file__).parent.parent / "config_optimized.yaml"
            config = load_config(config_path)
            _search_engine = ImageSearchEngine(config, use_hybrid=True)
            _search_engine.initialize()
        except Exception as e:
            print(f"Warning: Could not load search engine: {e}")
            return None
    return _search_engine


# FastAPI app
app = FastAPI(
    title="Gallery Review API",
    description="API for reviewing and rating village landscape images",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database instance
db = GalleryDB(str(DB_PATH))


# ==================== Pydantic Models ====================

class RatingRequest(BaseModel):
    rating: int


class SearchRequest(BaseModel):
    query: str
    top_k: int = 20


class ImageResponse(BaseModel):
    id: int
    original_path: str
    thumbnail_path: Optional[str]
    semantic_score: Optional[float]
    rating: int
    width: Optional[int]
    height: Optional[int]
    file_size: Optional[int]


class PaginatedResponse(BaseModel):
    images: List[dict]
    total: int
    page: int
    per_page: int
    total_pages: int


# ==================== API Endpoints ====================

@app.get("/api/images", response_model=PaginatedResponse)
async def get_images(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    min_rating: Optional[int] = Query(None, ge=0, le=5),
    max_rating: Optional[int] = Query(None, ge=0, le=5),
    min_score: Optional[float] = Query(None),
    max_score: Optional[float] = Query(None),
    unrated_only: bool = Query(False),
    sort_by: str = Query("semantic_score"),
    order: str = Query("desc"),
    show_hidden: bool = Query(False, description="Include hidden duplicates")
):
    """Get paginated list of images with filters. Hidden duplicates excluded by default."""
    images, total = db.get_images(
        page=page,
        per_page=per_page,
        min_rating=min_rating,
        max_rating=max_rating,
        min_score=min_score,
        max_score=max_score,
        unrated_only=unrated_only,
        sort_by=sort_by,
        order=order,
        show_hidden=show_hidden
    )

    total_pages = (total + per_page - 1) // per_page

    return PaginatedResponse(
        images=images,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@app.get("/api/images/{image_id}")
async def get_image(image_id: int):
    """Get a single image by ID."""
    image = db.get_image(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    return image


@app.post("/api/images/{image_id}/rate")
async def rate_image(image_id: int, request: RatingRequest):
    """Set rating for an image (0-5, 0 = unrated)."""
    if request.rating < 0 or request.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 0 and 5")

    success = db.set_rating(image_id, request.rating)
    if not success:
        raise HTTPException(status_code=404, detail="Image not found")

    return {"success": True, "rating": request.rating}


@app.get("/api/images/{image_id}/similar")
async def get_similar_images(image_id: int, top_k: int = Query(10, ge=1, le=50)):
    """Find similar images using FAISS search."""
    # Get the original image
    image = db.get_image(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    # Check cache first
    cached = db.get_cached_similar(image_id)
    if cached:
        return {"similar": cached[:top_k]}

    # Use search engine for similarity search
    search_engine = get_search_engine()
    if not search_engine:
        return {"similar": [], "error": "Search engine not available"}

    try:
        # Search by image
        original_path = image['original_path']
        if not Path(original_path).exists():
            return {"similar": [], "error": "Original image not found"}

        results = search_engine.search_by_image(original_path, top_k=top_k + 1)

        # Filter out the query image itself and convert to gallery format
        similar = []
        for result in results:
            if result.file_path != original_path:
                # Look up in gallery database
                gallery_img = db.get_image_by_path(result.file_path)
                if gallery_img:
                    gallery_img['similarity_score'] = result.score
                    similar.append(gallery_img)

        return {"similar": similar[:top_k]}

    except Exception as e:
        return {"similar": [], "error": str(e)}


@app.get("/api/search")
async def search_images(
    q: str = Query(..., min_length=1),
    top_k: int = Query(50, ge=1, le=200)
):
    """Semantic search within the gallery."""
    search_engine = get_search_engine()
    if not search_engine:
        raise HTTPException(status_code=503, detail="Search engine not available")

    try:
        results = search_engine.search_by_text(q, top_k=top_k)

        # Match with gallery database
        gallery_results = []
        for result in results:
            gallery_img = db.get_image_by_path(result.file_path)
            if gallery_img:
                gallery_img['search_score'] = result.score
                gallery_results.append(gallery_img)

        return {
            "query": q,
            "results": gallery_results,
            "total": len(gallery_results)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """Get gallery statistics."""
    return db.get_stats()


@app.post("/api/open-finder")
async def open_in_finder(original_path: str = Query(...)):
    """Open file in macOS Finder."""
    path = Path(original_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Use macOS open command to reveal in Finder
        subprocess.run(['open', '-R', str(path)], check=True)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Static Files ====================

# Serve thumbnails
@app.get("/thumbnails/{filename}")
async def get_thumbnail(filename: str):
    """Serve thumbnail images."""
    thumb_path = THUMBNAILS_DIR / filename
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(thumb_path, media_type="image/jpeg")


# Serve static files (frontend)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Serve index.html at root
@app.get("/")
async def root():
    """Serve the main gallery page."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return JSONResponse(
            content={"message": "Gallery frontend not found. Run the thumbnail generator first."},
            status_code=404
        )
    return FileResponse(index_path)


# ==================== Main ====================

def main():
    parser = argparse.ArgumentParser(description="Gallery Review Server")
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    args = parser.parse_args()

    print(f"Starting Gallery Server at http://{args.host}:{args.port}")
    print(f"Database: {DB_PATH}")
    print(f"Thumbnails: {THUMBNAILS_DIR}")
    print(f"Static: {STATIC_DIR}")

    uvicorn.run(
        "gallery_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
