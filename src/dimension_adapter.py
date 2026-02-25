"""Dimension adapter for handling embedding dimension mismatches."""

import numpy as np
import logging

logger = logging.getLogger(__name__)


class DimensionAdapter:
    """Adapter to project embeddings between different dimensions."""

    def __init__(self, source_dim: int, target_dim: int):
        """
        Initialize dimension adapter.

        Args:
            source_dim: Source embedding dimension (e.g., 768 for Gemini)
            target_dim: Target embedding dimension (e.g., 512 for ViT-B-32)
        """
        self.source_dim = source_dim
        self.target_dim = target_dim
        
        # Simple projection matrix (PCA-like, but linear)
        # This is a naive approach - for better results, train a proper projection
        np.random.seed(42)  # Reproducible projection
        self.projection = np.random.randn(source_dim, target_dim)
        # Normalize columns
        self.projection = self.projection / np.linalg.norm(self.projection, axis=0, keepdims=True)
        
        logger.info(f"Dimension adapter initialized: {source_dim} → {target_dim}")

    def adapt(self, embedding: np.ndarray) -> np.ndarray:
        """
        Project embedding from source dimension to target dimension.

        Args:
            embedding: Embedding vector of shape (source_dim,) or (N, source_dim)

        Returns:
            Projected embedding of shape (target_dim,) or (N, target_dim)
        """
        if embedding.ndim == 1:
            # Single embedding
            projected = embedding @ self.projection
            # Normalize to maintain unit length
            norm = np.linalg.norm(projected)
            if norm > 0:
                projected = projected / norm
            return projected
        else:
            # Batch of embeddings
            projected = embedding @ self.projection
            # Normalize each embedding
            norms = np.linalg.norm(projected, axis=1, keepdims=True)
            projected = np.where(norms > 0, projected / norms, projected)
            return projected


def create_adapter_if_needed(query_dim: int, index_dim: int):
    """
    Create dimension adapter if dimensions don't match.

    Args:
        query_dim: Query embedding dimension
        index_dim: Index embedding dimension

    Returns:
        DimensionAdapter if needed, None if dimensions match
    """
    if query_dim == index_dim:
        return None
    
    logger.warning(
        f"⚠️ Embedding dimension mismatch detected: "
        f"query={query_dim}, index={index_dim}. "
        f"Using dimension adapter (information loss may occur)."
    )
    
    return DimensionAdapter(source_dim=query_dim, target_dim=index_dim)


