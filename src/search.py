"""Search functionality for text-to-image and image-to-image queries."""

from pathlib import Path
from typing import Union, List, Dict, Any, Optional
from PIL import Image
import numpy as np

from .config import Config
from .database import ImageDatabase
from .embeddings import EmbeddingModel, EmbeddingCache, create_embedding_model
from .faiss_index import FAISSIndex, HybridSearch
from .image_processor import ImageProcessor


class SearchResult:
    """Container for search results."""

    def __init__(self, image_id: int, file_path: str, score: float,
                 thumbnail_path: Optional[str] = None,
                 width: Optional[int] = None, height: Optional[int] = None,
                 embedding_index: Optional[int] = None,
                 file_name: Optional[str] = None):
        self.image_id = image_id
        self.file_path = file_path
        self.file_name = file_name or Path(file_path).name
        self.score = float(score)
        self.thumbnail_path = thumbnail_path
        self.width = width
        self.height = height
        self.embedding_index = embedding_index

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'image_id': self.image_id,
            'file_path': self.file_path,
            'file_name': self.file_name,
            'score': self.score,
            'thumbnail_path': self.thumbnail_path,
            'width': self.width,
            'height': self.height,
            'embedding_index': self.embedding_index
        }

    def __repr__(self):
        return f"SearchResult(file_path={self.file_path}, score={self.score:.4f})"


class ImageSearchEngine:
    """Main search engine for text and image queries."""

    def __init__(self, config: Config, use_hybrid: bool = True):
        """
        Initialize search engine.

        Args:
            config: Configuration object
            use_hybrid: Whether to use hybrid search (IVF-PQ + exact re-ranking)
        """
        self.config = config
        self.use_hybrid = use_hybrid

        # Initialize components
        self.db = ImageDatabase(config.db_path)
        self.embedding_model = None
        self.local_model = None  # For image encoding when using Gemini API
        self.embedding_cache = EmbeddingCache(config.embeddings_path)
        self.faiss_index = None
        self.hybrid_search = None
        self.image_processor = ImageProcessor(config.thumbnails_dir)

    def initialize(self):
        """Load all necessary components."""
        print("Initializing search engine...")

        # Load embedding model (local or Gemini API)
        if self.embedding_model is None:
            embedding_mode = getattr(self.config, 'embedding_mode', 'local')
            if embedding_mode == 'gemini':
                print(f"Using Gemini Embedding API for text queries (mode: {embedding_mode})")
                print("Note: Image search will use local model")
                # For Gemini mode, we need both models - local for images, Gemini for text
                self.embedding_model = create_embedding_model(self.config)
                # Keep local model for image encoding
                self.local_model = EmbeddingModel(
                    model_name=self.config.model_name,
                    pretrained=self.config.pretrained,
                    device=self.config.device
                )
            else:
                print(f"Using local CLIP model (mode: {embedding_mode})")
                self.embedding_model = create_embedding_model(self.config)
                self.local_model = None

        # Load embeddings cache
        print("Loading embeddings...")
        embeddings = self.embedding_cache.load()

        # Load or build FAISS index
        print("Loading FAISS index...")
        self.faiss_index = FAISSIndex(
            embedding_dim=self.config.embedding_dim,
            index_path=self.config.index_path
        )

        if self.config.index_path.exists():
            self.faiss_index.load()
        else:
            print("Building new FAISS index...")
            self.faiss_index.build_ivf_pq_index(
                embeddings,
                nlist=self.config.nlist,
                m=self.config.m_pq,
                nbits=self.config.nbits_pq,
                use_gpu=self.config.device == "cuda"
            )
            self.faiss_index.save()

        # Initialize hybrid search if requested
        if self.use_hybrid:
            print("Initializing hybrid search...")
            self.hybrid_search = HybridSearch(
                ivf_index=self.faiss_index,
                embeddings_cache=embeddings
            )

        print("Search engine ready!")

    def search_by_text(self, query: str, top_k: int = 20) -> List[SearchResult]:
        """
        Search for images using text query.

        Args:
            query: Text description
            top_k: Number of results to return

        Returns:
            List of SearchResult objects
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if self.embedding_model is None:
            logger.warning("Embedding model not loaded! Initializing now...")
            self.initialize()
            logger.info("Model initialization complete")

        # Encode text query
        logger.info(f"Encoding text query: '{query[:50]}{'...' if len(query) > 50 else ''}'")
        query_embedding = self.embedding_model.encode_text(query, normalize=True)
        logger.info(f"Text encoding complete, embedding shape: {query_embedding.shape}")
        
        # Handle dimension mismatch (e.g., Gemini 768-dim vs index 512-dim)
        if hasattr(query_embedding, 'shape') and len(query_embedding.shape) > 0:
            query_dim = query_embedding.shape[0] if query_embedding.ndim == 1 else query_embedding.shape[1]
            index_dim = self.config.embedding_dim
            
            if query_dim != index_dim:
                logger.warning(
                    f"⚠️ Dimension mismatch: query={query_dim}, index={index_dim}. "
                    f"Attempting dimension adaptation..."
                )
                from .dimension_adapter import create_adapter_if_needed
                adapter = create_adapter_if_needed(query_dim, index_dim)
                if adapter:
                    query_embedding = adapter.adapt(query_embedding)
                    logger.info(f"Dimension adapted: {query_dim} → {index_dim}")

        # Search
        if self.use_hybrid and self.hybrid_search:
            scores, indices = self.hybrid_search.search(
                query_embedding,
                k=top_k,
                k_approximate=self.config.top_k_ivf,
                nprobe=self.config.nprobe
            )
        else:
            scores, indices = self.faiss_index.search(
                query_embedding,
                k=top_k,
                nprobe=self.config.nprobe
            )
            scores = scores[0]
            indices = indices[0]

        # Get image metadata
        results = self._build_results(indices, scores)

        return results

    def search_by_image(self, image_path: Union[str, Path],
                       top_k: int = 20) -> List[SearchResult]:
        """
        Search for similar images using an image query.

        Args:
            image_path: Path to query image
            top_k: Number of results to return

        Returns:
            List of SearchResult objects
        """
        if self.embedding_model is None:
            self.initialize()

        # Load and encode image
        image = self.image_processor.load_image(Path(image_path))
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        # For image encoding, always use local model (Gemini doesn't support images)
        model_to_use = self.local_model if self.local_model is not None else self.embedding_model
        if model_to_use is None:
            self.initialize()
            model_to_use = self.local_model if self.local_model is not None else self.embedding_model
        
        query_embedding = model_to_use.encode_image(image, normalize=True)

        # Search
        if self.use_hybrid and self.hybrid_search:
            scores, indices = self.hybrid_search.search(
                query_embedding,
                k=top_k,
                k_approximate=self.config.top_k_ivf,
                nprobe=self.config.nprobe
            )
        else:
            scores, indices = self.faiss_index.search(
                query_embedding,
                k=top_k,
                nprobe=self.config.nprobe
            )
            scores = scores[0]
            indices = indices[0]

        # Get image metadata
        results = self._build_results(indices, scores)

        return results

    def search_by_embedding(self, embedding: np.ndarray,
                          top_k: int = 20) -> List[SearchResult]:
        """
        Search using a pre-computed embedding.

        Args:
            embedding: Query embedding vector
            top_k: Number of results to return

        Returns:
            List of SearchResult objects
        """
        if self.faiss_index is None:
            self.initialize()

        # Ensure normalized
        embedding = embedding / np.linalg.norm(embedding)

        # Search
        if self.use_hybrid and self.hybrid_search:
            scores, indices = self.hybrid_search.search(
                embedding,
                k=top_k,
                k_approximate=self.config.top_k_ivf,
                nprobe=self.config.nprobe
            )
        else:
            scores, indices = self.faiss_index.search(
                embedding,
                k=top_k,
                nprobe=self.config.nprobe
            )
            scores = scores[0]
            indices = indices[0]

        # Get image metadata
        results = self._build_results(indices, scores)

        return results

    def _build_results(self, indices: np.ndarray, scores: np.ndarray) -> List[SearchResult]:
        """
        Build SearchResult objects from indices and scores.

        Args:
            indices: Array of embedding indices
            scores: Array of similarity scores

        Returns:
            List of SearchResult objects
        """
        # Get image records
        image_records = self.db.get_images_by_indices(indices.tolist())

        # Create mapping from embedding_index to record
        index_to_record = {rec['embedding_index']: rec for rec in image_records}

        # Build results in order
        results = []
        max_valid_index = len(self.embedding_cache.embeddings) - 1 if self.embedding_cache.embeddings is not None else None
        
        for idx, score in zip(indices, scores):
            if idx < 0:  # Invalid index from FAISS
                continue
            
            # Filter out invalid embedding indices (beyond available embeddings)
            if max_valid_index is not None and idx > max_valid_index:
                continue

            record = index_to_record.get(int(idx))
            if record:
                result = SearchResult(
                    image_id=record['id'],
                    file_path=record['file_path'],
                    score=score,
                    thumbnail_path=record.get('thumbnail_path'),
                    width=record.get('width'),
                    height=record.get('height'),
                    embedding_index=record.get('embedding_index'),
                    file_name=record.get('file_name')
                )
                results.append(result)

        return results

    def close(self):
        """Clean up resources."""
        self.db.close()
