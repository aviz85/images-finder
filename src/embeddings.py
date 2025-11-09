"""Image and text embedding generation using OpenCLIP."""

import torch
import open_clip
from PIL import Image
from pathlib import Path
from typing import Union, List, Optional
import numpy as np


class EmbeddingModel:
    """Wrapper for OpenCLIP model for generating embeddings."""

    def __init__(self, model_name: str = "hf-hub:timm/ViT-SO400M-14-SigLIP-384",
                 pretrained: str = "webli",
                 device: str = "cuda"):
        """
        Initialize the embedding model.

        Args:
            model_name: OpenCLIP model identifier
            pretrained: Pretrained weights identifier
            device: Device to run on ('cuda' or 'cpu')
        """
        self.device = device if torch.cuda.is_available() else "cpu"

        print(f"Loading model {model_name} with {pretrained} weights on {self.device}...")

        # Load model
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_name,
            pretrained=pretrained,
            device=self.device
        )

        # Tokenizer is a function in open_clip
        self.tokenizer = open_clip.tokenize

        self.model.eval()

        # Get embedding dimension by processing a dummy PIL image through preprocess
        with torch.no_grad():
            # Create a small dummy PIL image and preprocess it to get the correct size
            dummy_pil = Image.new('RGB', (100, 100), color='white')
            dummy_tensor = self.preprocess(dummy_pil).unsqueeze(0).to(self.device)
            dummy_embedding = self.model.encode_image(dummy_tensor)
            self.embedding_dim = dummy_embedding.shape[1]

        print(f"Model loaded. Embedding dimension: {self.embedding_dim}")

    @torch.no_grad()
    def encode_images(self, images: List[Union[str, Path, Image.Image]],
                     batch_size: int = 32,
                     normalize: bool = True) -> np.ndarray:
        """
        Encode a batch of images to embeddings.

        Args:
            images: List of image paths or PIL Images
            batch_size: Batch size for processing
            normalize: Whether to normalize embeddings to unit length

        Returns:
            numpy array of shape (N, embedding_dim)
        """
        all_embeddings = []

        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]

            # Load and preprocess images
            processed_images = []
            for img in batch:
                if isinstance(img, (str, Path)):
                    img = Image.open(img).convert('RGB')
                processed_images.append(self.preprocess(img))

            # Stack into batch tensor
            image_tensor = torch.stack(processed_images).to(self.device)

            # Generate embeddings
            embeddings = self.model.encode_image(image_tensor)

            # Normalize if requested
            if normalize:
                embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True)

            all_embeddings.append(embeddings.cpu().numpy())

        # Concatenate all batches
        return np.vstack(all_embeddings)

    @torch.no_grad()
    def encode_image(self, image: Union[str, Path, Image.Image],
                    normalize: bool = True) -> np.ndarray:
        """
        Encode a single image to embedding.

        Args:
            image: Image path or PIL Image
            normalize: Whether to normalize embedding to unit length

        Returns:
            numpy array of shape (embedding_dim,)
        """
        embeddings = self.encode_images([image], batch_size=1, normalize=normalize)
        return embeddings[0]

    @torch.no_grad()
    def encode_text(self, texts: Union[str, List[str]],
                   normalize: bool = True) -> np.ndarray:
        """
        Encode text queries to embeddings.

        Args:
            texts: Single text or list of texts
            normalize: Whether to normalize embeddings to unit length

        Returns:
            numpy array of shape (N, embedding_dim) or (embedding_dim,) for single text
        """
        if isinstance(texts, str):
            texts = [texts]
            single = True
        else:
            single = False

        # Tokenize
        text_tokens = self.tokenizer(texts).to(self.device)

        # Generate embeddings
        embeddings = self.model.encode_text(text_tokens)

        # Normalize if requested
        if normalize:
            embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True)

        embeddings = embeddings.cpu().numpy()

        return embeddings[0] if single else embeddings

    def get_embedding_dim(self) -> int:
        """Get the embedding dimension."""
        return self.embedding_dim


class EmbeddingCache:
    """Manages embedding storage and retrieval."""

    def __init__(self, cache_path: Path):
        """
        Initialize embedding cache.

        Args:
            cache_path: Path to save/load embeddings (.npy file)
        """
        self.cache_path = cache_path
        self.embeddings: Optional[np.ndarray] = None

    def save(self, embeddings: np.ndarray):
        """Save embeddings to disk."""
        np.save(self.cache_path, embeddings)
        self.embeddings = embeddings
        print(f"Saved {len(embeddings)} embeddings to {self.cache_path}")

    def load(self) -> np.ndarray:
        """Load embeddings from disk."""
        if self.cache_path.exists():
            self.embeddings = np.load(self.cache_path)
            print(f"Loaded {len(self.embeddings)} embeddings from {self.cache_path}")
            return self.embeddings
        else:
            raise FileNotFoundError(f"Embedding cache not found at {self.cache_path}")

    def add_embeddings(self, new_embeddings: np.ndarray):
        """Add new embeddings to the cache."""
        if self.embeddings is None:
            self.embeddings = new_embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, new_embeddings])

    def get_embeddings(self, indices: List[int]) -> np.ndarray:
        """Get embeddings by indices."""
        if self.embeddings is None:
            raise RuntimeError("Embeddings not loaded. Call load() first.")
        return self.embeddings[indices]

    def __len__(self) -> int:
        """Get number of embeddings in cache."""
        return len(self.embeddings) if self.embeddings is not None else 0
