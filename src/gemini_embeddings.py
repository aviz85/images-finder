"""Google Gemini Embedding API integration."""

from typing import Union, List, Optional
from pathlib import Path
import numpy as np
import logging
from PIL import Image

logger = logging.getLogger(__name__)


class GeminiEmbeddingModel:
    """Wrapper for Google Gemini Embedding API."""

    def __init__(self, api_key: str, embedding_dim: int = 768):
        """
        Initialize the Gemini embedding model.

        Args:
            api_key: Google Gemini API key
            embedding_dim: Expected embedding dimension (768 for gemini-embedding-001)
        """
        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "google-genai package is required. Install with: pip install google-genai"
            )

        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini embedding mode")

        self.api_key = api_key
        self.embedding_dim = embedding_dim
        self.model_name = "gemini-embedding-001"
        
        logger.info(f"Initializing Gemini Embedding API (model: {self.model_name})...")
        
        # Initialize client
        self.client = genai.Client(api_key=api_key)
        
        logger.info(f"Gemini Embedding API ready. Embedding dimension: {embedding_dim}")

    def encode_text(self, texts: Union[str, List[str]],
                   normalize: bool = True) -> np.ndarray:
        """
        Encode text queries to embeddings using Gemini API.

        Args:
            texts: Single text or list of texts
            normalize: Whether to normalize embeddings to unit length

        Returns:
            numpy array of shape (N, embedding_dim) or (embedding_dim,) for single text
        """
        logger.info(f"Gemini: Encoding {len(texts) if isinstance(texts, list) else 1} text(s)")
        
        if isinstance(texts, str):
            texts = [texts]
            single = True
        else:
            single = False

        all_embeddings = []
        
        for text in texts:
            logger.info(f"Gemini: Sending API request for text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            
            try:
                result = self.client.embed_content(
                    model=self.model_name,
                    content=text,
                )
                
                # Extract embedding vector
                embedding = np.array(result.embedding.values, dtype=np.float32)
                
                logger.info(f"Gemini: Received embedding, shape: {embedding.shape}")
                
                # Normalize if requested
                if normalize:
                    norm = np.linalg.norm(embedding)
                    if norm > 0:
                        embedding = embedding / norm
                
                all_embeddings.append(embedding)
                
            except Exception as e:
                logger.error(f"Gemini API error: {e}")
                raise RuntimeError(f"Failed to get embedding from Gemini API: {e}")

        embeddings_array = np.vstack(all_embeddings)
        logger.info(f"Gemini: Text encoding complete, shape: {embeddings_array.shape}")

        return embeddings_array[0] if single else embeddings_array

    def encode_image(self, image: Union[str, Path, Image.Image],
                    normalize: bool = True) -> np.ndarray:
        """
        Encode a single image to embedding.

        NOTE: Gemini embedding API currently only supports text.
        For images, you would need to use a different approach or keep using local model.

        Args:
            image: Image path or PIL Image
            normalize: Whether to normalize embedding to unit length

        Returns:
            numpy array of shape (embedding_dim,)
        """
        raise NotImplementedError(
            "Gemini Embedding API does not support image encoding directly. "
            "Use local CLIP model for images, or convert image to text description first."
        )

    def encode_images(self, images: List[Union[str, Path, Image.Image]],
                     batch_size: int = 32,
                     normalize: bool = True) -> np.ndarray:
        """
        Encode a batch of images to embeddings.

        NOTE: Gemini embedding API currently only supports text.
        See encode_image() for details.

        Args:
            images: List of image paths or PIL Images
            batch_size: Ignored for API (sent one at a time)
            normalize: Whether to normalize embeddings to unit length

        Returns:
            numpy array of shape (N, embedding_dim)
        """
        raise NotImplementedError(
            "Gemini Embedding API does not support image encoding directly. "
            "Use local CLIP model for images."
        )

    def get_embedding_dim(self) -> int:
        """Get the embedding dimension."""
        return self.embedding_dim


