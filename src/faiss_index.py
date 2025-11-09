"""FAISS index management for fast similarity search."""

import faiss
import numpy as np
from pathlib import Path
from typing import Tuple, Optional


class FAISSIndex:
    """Manages FAISS index for efficient vector search."""

    def __init__(self, embedding_dim: int, index_path: Optional[Path] = None):
        """
        Initialize FAISS index.

        Args:
            embedding_dim: Dimension of embeddings
            index_path: Path to save/load index
        """
        self.embedding_dim = embedding_dim
        self.index_path = index_path
        self.index: Optional[faiss.Index] = None
        self.is_trained = False

    def build_ivf_pq_index(self, embeddings: np.ndarray,
                          nlist: int = 4096,
                          m: int = 64,
                          nbits: int = 8,
                          use_gpu: bool = False) -> None:
        """
        Build IVF-PQ index for memory-efficient search.

        Args:
            embeddings: Training embeddings (N, embedding_dim)
            nlist: Number of IVF clusters (Voronoi cells)
            m: Number of PQ sub-vectors
            nbits: Bits per PQ code
            use_gpu: Whether to use GPU for training (if available)
        """
        n, d = embeddings.shape
        assert d == self.embedding_dim, f"Embedding dim mismatch: {d} vs {self.embedding_dim}"

        print(f"Building IVF-PQ index with nlist={nlist}, m={m}, nbits={nbits}")
        print(f"Training on {n} vectors...")

        # Create quantizer (IVF)
        quantizer = faiss.IndexFlatIP(d)  # Inner product (cosine sim for normalized vectors)

        # Create IVF-PQ index
        self.index = faiss.IndexIVFPQ(quantizer, d, nlist, m, nbits)

        # Convert to GPU if requested and available
        if use_gpu and faiss.get_num_gpus() > 0:
            print("Using GPU for training...")
            res = faiss.StandardGpuResources()
            self.index = faiss.index_cpu_to_gpu(res, 0, self.index)

        # Ensure float32
        embeddings = embeddings.astype(np.float32)

        # Train the index
        print("Training index...")
        self.index.train(embeddings)
        self.is_trained = True

        # Add vectors
        print("Adding vectors to index...")
        self.index.add(embeddings)

        # Convert back to CPU if using GPU
        if use_gpu and faiss.get_num_gpus() > 0:
            self.index = faiss.index_gpu_to_cpu(self.index)

        print(f"Index built with {self.index.ntotal} vectors")

    def build_flat_index(self, embeddings: np.ndarray, use_gpu: bool = False) -> None:
        """
        Build flat (exact) index for smaller datasets.

        Args:
            embeddings: Embeddings to index (N, embedding_dim)
            use_gpu: Whether to use GPU
        """
        n, d = embeddings.shape
        assert d == self.embedding_dim, f"Embedding dim mismatch: {d} vs {self.embedding_dim}"

        print(f"Building flat index for {n} vectors...")

        # Create flat index with inner product (cosine similarity for normalized vectors)
        self.index = faiss.IndexFlatIP(d)

        # Convert to GPU if requested
        if use_gpu and faiss.get_num_gpus() > 0:
            res = faiss.StandardGpuResources()
            self.index = faiss.index_cpu_to_gpu(res, 0, self.index)

        # Add vectors
        embeddings = embeddings.astype(np.float32)
        self.index.add(embeddings)

        # Convert back to CPU
        if use_gpu and faiss.get_num_gpus() > 0:
            self.index = faiss.index_gpu_to_cpu(self.index)

        self.is_trained = True
        print(f"Flat index built with {self.index.ntotal} vectors")

    def search(self, query_embeddings: np.ndarray, k: int = 100,
              nprobe: int = 32) -> Tuple[np.ndarray, np.ndarray]:
        """
        Search for nearest neighbors.

        Args:
            query_embeddings: Query vectors (N, embedding_dim)
            k: Number of results to return
            nprobe: Number of clusters to probe (for IVF indices)

        Returns:
            Tuple of (distances, indices) arrays
        """
        if self.index is None:
            raise RuntimeError("Index not built. Call build_*_index first.")

        # Handle single query
        if query_embeddings.ndim == 1:
            query_embeddings = query_embeddings.reshape(1, -1)

        query_embeddings = query_embeddings.astype(np.float32)

        # Set nprobe for IVF indices
        if isinstance(self.index, faiss.IndexIVFPQ) or isinstance(self.index, faiss.IndexIVFFlat):
            self.index.nprobe = nprobe

        # Search
        distances, indices = self.index.search(query_embeddings, k)

        return distances, indices

    def save(self, path: Optional[Path] = None):
        """Save index to disk."""
        if self.index is None:
            raise RuntimeError("No index to save")

        save_path = path or self.index_path
        if save_path is None:
            raise ValueError("No path specified for saving")

        faiss.write_index(self.index, str(save_path))
        print(f"Index saved to {save_path}")

    def load(self, path: Optional[Path] = None):
        """Load index from disk."""
        load_path = path or self.index_path
        if load_path is None:
            raise ValueError("No path specified for loading")

        if not load_path.exists():
            raise FileNotFoundError(f"Index file not found: {load_path}")

        self.index = faiss.read_index(str(load_path))
        self.is_trained = True
        print(f"Index loaded from {load_path} with {self.index.ntotal} vectors")

    def add_vectors(self, embeddings: np.ndarray):
        """
        Add new vectors to existing index.

        Args:
            embeddings: New embeddings to add (N, embedding_dim)
        """
        if self.index is None:
            raise RuntimeError("Index not initialized")

        if not self.is_trained:
            raise RuntimeError("Index not trained. Build index first.")

        embeddings = embeddings.astype(np.float32)
        self.index.add(embeddings)
        print(f"Added {len(embeddings)} vectors. Total: {self.index.ntotal}")


class HybridSearch:
    """Hybrid search combining IVF-PQ approximate search with exact re-ranking."""

    def __init__(self, ivf_index: FAISSIndex, embeddings_cache: np.ndarray):
        """
        Initialize hybrid search.

        Args:
            ivf_index: IVF-PQ index for approximate search
            embeddings_cache: Full precision embeddings for re-ranking
        """
        self.ivf_index = ivf_index
        self.embeddings_cache = embeddings_cache.astype(np.float32)

    def search(self, query_embedding: np.ndarray,
              k: int = 100,
              k_approximate: int = 1000,
              nprobe: int = 32) -> Tuple[np.ndarray, np.ndarray]:
        """
        Hybrid search: IVF-PQ for recall, then exact re-ranking.

        Args:
            query_embedding: Query vector (embedding_dim,)
            k: Final number of results
            k_approximate: Number of candidates from IVF-PQ
            nprobe: Number of IVF clusters to probe

        Returns:
            Tuple of (distances, indices) for top-k results
        """
        # Ensure query is 2D
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        query_embedding = query_embedding.astype(np.float32)

        # Step 1: Get approximate top-k candidates from IVF-PQ
        _, candidate_indices = self.ivf_index.search(
            query_embedding,
            k=min(k_approximate, self.ivf_index.index.ntotal),
            nprobe=nprobe
        )

        # Flatten candidate indices
        candidate_indices = candidate_indices[0]

        # Remove invalid indices (-1)
        candidate_indices = candidate_indices[candidate_indices >= 0]

        # Step 2: Re-rank candidates with exact embeddings
        candidate_embeddings = self.embeddings_cache[candidate_indices]

        # Compute exact cosine similarities (assuming normalized embeddings)
        similarities = np.dot(candidate_embeddings, query_embedding.T).squeeze()

        # Sort by similarity (descending)
        sorted_idx = np.argsort(-similarities)

        # Get top-k
        top_k_idx = sorted_idx[:k]
        top_k_distances = similarities[top_k_idx]
        top_k_indices = candidate_indices[top_k_idx]

        return top_k_distances, top_k_indices
