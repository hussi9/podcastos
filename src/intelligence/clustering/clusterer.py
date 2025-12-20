"""Semantic clustering using HDBSCAN."""

from datetime import datetime
from typing import Optional
import uuid
import numpy as np
import logging

import hdbscan
from sklearn.metrics.pairwise import cosine_distances

from .embedder import SemanticEmbedder
from ..models.content import RawContent, TopicCluster


logger = logging.getLogger(__name__)


class SemanticClusterer:
    """
    Clusters semantically similar content using HDBSCAN.
    HDBSCAN advantages:
    - No need to specify number of clusters
    - Handles noise (outliers)
    - Finds clusters of varying densities
    """

    def __init__(
        self,
        embedder: Optional[SemanticEmbedder] = None,
        min_cluster_size: int = 2,
        min_samples: int = 1,
        cluster_selection_epsilon: float = 0.3,
    ):
        self.embedder = embedder or SemanticEmbedder()
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.cluster_selection_epsilon = cluster_selection_epsilon

    def cluster_contents(
        self,
        contents: list[RawContent],
        min_cluster_size: Optional[int] = None,
    ) -> list[TopicCluster]:
        """
        Cluster a list of RawContent items.
        Returns list of TopicClusters.
        """
        if len(contents) < 2:
            # Not enough content to cluster
            if contents:
                return [self._single_item_cluster(contents[0])]
            return []

        # Generate embeddings if not already present
        embeddings = self._get_embeddings(contents)

        # Ensure float64 for HDBSCAN compatibility
        embeddings = embeddings.astype(np.float64)

        # Compute distance matrix
        distances = cosine_distances(embeddings)

        # Run HDBSCAN clustering
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size or self.min_cluster_size,
            min_samples=self.min_samples,
            metric="precomputed",
            cluster_selection_epsilon=self.cluster_selection_epsilon,
        )

        labels = clusterer.fit_predict(distances)

        # Group contents by cluster
        cluster_map: dict[int, list[RawContent]] = {}
        noise_items: list[RawContent] = []

        for i, label in enumerate(labels):
            if label == -1:
                noise_items.append(contents[i])
            else:
                if label not in cluster_map:
                    cluster_map[label] = []
                cluster_map[label].append(contents[i])

        # Create TopicCluster objects
        clusters = []

        for label, cluster_contents in cluster_map.items():
            cluster = self._create_cluster(cluster_contents, embeddings, labels, label)
            clusters.append(cluster)

        # Handle noise items (create individual clusters for high-engagement ones)
        for item in noise_items:
            if item.engagement_score > 50:  # Only if notable
                cluster = self._single_item_cluster(item)
                clusters.append(cluster)

        # Sort clusters by priority
        clusters.sort(key=lambda c: c.priority_score, reverse=True)

        logger.info(f"Created {len(clusters)} clusters from {len(contents)} items")

        return clusters

    def _get_embeddings(self, contents: list[RawContent]) -> np.ndarray:
        """Get or compute embeddings for contents."""
        # Check if embeddings exist
        if all(c.embedding for c in contents):
            return np.array([c.embedding for c in contents])

        # Generate embeddings
        return self.embedder.embed_contents(contents)

    def _create_cluster(
        self,
        contents: list[RawContent],
        all_embeddings: np.ndarray,
        labels: np.ndarray,
        label: int,
    ) -> TopicCluster:
        """Create a TopicCluster from clustered contents."""
        # Get embeddings for this cluster
        indices = np.where(labels == label)[0]
        cluster_embeddings = all_embeddings[indices]

        # Compute centroid
        centroid = np.mean(cluster_embeddings, axis=0).tolist()

        # Create cluster
        cluster = TopicCluster(
            id=str(uuid.uuid4())[:8],
            name=self._generate_cluster_name(contents),
            summary=self._generate_cluster_summary(contents),
            contents=contents,
            embedding_centroid=centroid,
        )

        # Calculate metrics
        cluster.calculate_metrics()

        # Compute coherence score
        cluster.coherence_score = self._compute_coherence(cluster_embeddings)

        # Detect trends
        self._detect_trends(cluster)

        return cluster

    def _single_item_cluster(self, content: RawContent) -> TopicCluster:
        """Create a cluster from a single item."""
        cluster = TopicCluster(
            id=str(uuid.uuid4())[:8],
            name=content.title[:50],
            summary=content.body[:200] if content.body else content.title,
            contents=[content],
            embedding_centroid=content.embedding,
            coherence_score=1.0,  # Perfect coherence for single item
        )
        cluster.calculate_metrics()
        return cluster

    def _generate_cluster_name(self, contents: list[RawContent]) -> str:
        """
        Generate a cluster name from content titles.
        This is a placeholder - will be replaced by LLM naming.
        """
        # Find most common significant words
        from collections import Counter

        words = []
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "and", "or", "but", "with", "by", "from", "this", "that", "it", "be", "as", "what", "how", "why", "when", "where", "who"}

        for content in contents:
            title_words = content.title.lower().split()
            words.extend([w for w in title_words if w not in stop_words and len(w) > 2])

        if not words:
            return contents[0].title[:50]

        # Get most common words
        common = Counter(words).most_common(3)
        name = " ".join(word.title() for word, _ in common)

        return name[:50]

    def _generate_cluster_summary(self, contents: list[RawContent]) -> str:
        """
        Generate a cluster summary.
        This is a placeholder - will be replaced by LLM summarization.
        """
        # Use the highest-engagement content's title/body
        top_content = max(contents, key=lambda c: c.engagement_score)

        if top_content.body:
            return top_content.body[:300]
        return top_content.title

    def _compute_coherence(self, embeddings: np.ndarray) -> float:
        """
        Compute cluster coherence based on embedding similarity.
        Higher = more coherent cluster.
        """
        if len(embeddings) < 2:
            return 1.0

        # Compute pairwise similarities
        distances = cosine_distances(embeddings)

        # Convert to similarities
        similarities = 1 - distances

        # Average similarity (excluding diagonal)
        n = len(embeddings)
        total = np.sum(similarities) - n  # Subtract diagonal (self-similarity)
        pairs = n * (n - 1)

        return float(total / pairs) if pairs > 0 else 1.0

    def _detect_trends(self, cluster: TopicCluster):
        """
        Detect if cluster represents breaking/trending news.
        """
        if not cluster.contents:
            return

        now = datetime.now()

        # Check recency
        recent_count = sum(
            1 for c in cluster.contents
            if (now - c.published_at).total_seconds() < 3600 * 6  # Last 6 hours
        )

        recent_ratio = recent_count / len(cluster.contents)

        # High recency + high engagement = breaking
        if recent_ratio > 0.7 and cluster.total_engagement > 500:
            cluster.is_breaking = True
            cluster.trend_velocity = recent_ratio * (cluster.total_engagement / 100)

        # Multiple sources + high engagement = trending
        if cluster.source_diversity >= 2 and cluster.total_engagement > 200:
            cluster.is_trending = True

    def merge_similar_clusters(
        self,
        clusters: list[TopicCluster],
        similarity_threshold: float = 0.85,
    ) -> list[TopicCluster]:
        """
        Merge clusters that are too similar.
        """
        if len(clusters) < 2:
            return clusters

        # Get centroids
        centroids = []
        for cluster in clusters:
            if cluster.embedding_centroid:
                centroids.append(cluster.embedding_centroid)
            elif cluster.contents and cluster.contents[0].embedding:
                centroids.append(cluster.contents[0].embedding)
            else:
                # Compute centroid from contents
                embeddings = self._get_embeddings(cluster.contents)
                centroids.append(np.mean(embeddings, axis=0).tolist())

        centroids_array = np.array(centroids)

        # Compute similarities
        distances = cosine_distances(centroids_array)
        similarities = 1 - distances

        # Find clusters to merge
        merged = set()
        new_clusters = []

        for i in range(len(clusters)):
            if i in merged:
                continue

            cluster = clusters[i]
            combined_contents = list(cluster.contents)

            for j in range(i + 1, len(clusters)):
                if j in merged:
                    continue

                if similarities[i, j] > similarity_threshold:
                    combined_contents.extend(clusters[j].contents)
                    merged.add(j)

            # Create merged cluster if contents were combined
            if len(combined_contents) > len(cluster.contents):
                new_cluster = TopicCluster(
                    id=cluster.id,
                    name=cluster.name,
                    summary=cluster.summary,
                    contents=combined_contents,
                )
                new_cluster.calculate_metrics()
                new_clusters.append(new_cluster)
            else:
                new_clusters.append(cluster)

        logger.info(f"Merged {len(clusters)} clusters into {len(new_clusters)}")
        return new_clusters
