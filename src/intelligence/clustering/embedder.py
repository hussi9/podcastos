"""Semantic embedder using sentence-transformers (local, free)."""

from typing import Optional
import numpy as np
import logging

from sentence_transformers import SentenceTransformer

from ..models.content import RawContent


logger = logging.getLogger(__name__)


class SemanticEmbedder:
    """
    Generates semantic embeddings using sentence-transformers.
    Runs locally - no API costs.

    Default model: all-MiniLM-L6-v2
    - 384 dimensions
    - Fast inference
    - Good quality for clustering
    """

    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or self.DEFAULT_MODEL
        self._model: Optional[SentenceTransformer] = None
        self.embedding_dim: int = 384

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the model."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            self.embedding_dim = self._model.get_sentence_embedding_dimension()
            logger.info(f"Model loaded. Embedding dimension: {self.embedding_dim}")
        return self._model

    def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """
        Generate embeddings for multiple texts.
        Returns numpy array of shape (n_texts, embedding_dim).
        """
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=len(texts) > 100,
            convert_to_numpy=True,
        )
        return embeddings

    def embed_content(self, content: RawContent) -> list[float]:
        """
        Generate embedding for a RawContent item.
        Combines title and body for richer representation.
        """
        # Combine title (weighted more) and body
        text = f"{content.title}. {content.title}. {content.body[:500]}"
        embedding = self.embed_text(text)
        content.embedding = embedding
        return embedding

    def embed_contents(
        self, contents: list[RawContent], batch_size: int = 32
    ) -> np.ndarray:
        """
        Generate embeddings for multiple RawContent items.
        Updates each content's embedding field.
        """
        # Prepare texts
        texts = [
            f"{c.title}. {c.title}. {c.body[:500]}"
            for c in contents
        ]

        # Generate embeddings
        embeddings = self.embed_texts(texts, batch_size)

        # Update content objects
        for i, content in enumerate(contents):
            content.embedding = embeddings[i].tolist()

        logger.info(f"Generated embeddings for {len(contents)} items")
        return embeddings

    def compute_similarity(
        self, embedding1: list[float], embedding2: list[float]
    ) -> float:
        """
        Compute cosine similarity between two embeddings.
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def find_similar(
        self,
        query_embedding: list[float],
        embeddings: np.ndarray,
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        """
        Find most similar items to a query embedding.
        Returns list of (index, similarity) tuples.
        """
        query = np.array(query_embedding)

        # Compute similarities
        similarities = np.dot(embeddings, query) / (
            np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query)
        )

        # Get top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        return [(int(i), float(similarities[i])) for i in top_indices]

    def compute_centroid(self, embeddings: np.ndarray) -> list[float]:
        """
        Compute centroid (mean) of embeddings.
        """
        centroid = np.mean(embeddings, axis=0)
        return centroid.tolist()


# Alternative models for different use cases
EMBEDDING_MODELS = {
    "fast": "all-MiniLM-L6-v2",  # Default, fast
    "balanced": "all-mpnet-base-v2",  # Better quality, slower
    "multilingual": "paraphrase-multilingual-MiniLM-L12-v2",  # Multiple languages
    "large": "all-roberta-large-v1",  # Best quality, slowest
}
