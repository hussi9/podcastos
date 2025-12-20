"""Topic naming using Gemini for intelligent cluster naming."""

import os
from typing import Optional
import logging

from google import genai
from google.genai import types

from ..models.content import TopicCluster


logger = logging.getLogger(__name__)


class TopicNamer:
    """
    Uses Gemini to generate meaningful topic names and summaries for clusters.
    """

    NAMING_PROMPT = """Analyze these related content items and provide:
1. A concise topic name (3-6 words, catchy but informative)
2. A 2-3 sentence summary of what this topic is about
3. A category (one of: tech, business, politics, immigration, culture, science, other)

Content items:
{content_list}

Respond in this exact JSON format:
{{"name": "Topic Name Here", "summary": "Summary here.", "category": "tech"}}"""

    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        """Lazy load the Gemini client."""
        if self._client is None:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY not set")
            self._client = genai.Client(api_key=api_key)
        return self._client

    async def name_cluster(self, cluster: TopicCluster) -> TopicCluster:
        """
        Generate a meaningful name and summary for a cluster.
        Updates the cluster in place.
        """
        if not cluster.contents:
            return cluster

        # Prepare content list
        content_list = self._format_contents(cluster.contents[:10])  # Limit to 10

        # Generate name using Gemini
        prompt = self.NAMING_PROMPT.format(content_list=content_list)

        try:
            response = await self._generate(prompt)
            result = self._parse_response(response)

            if result:
                cluster.name = result.get("name", cluster.name)
                cluster.summary = result.get("summary", cluster.summary)
                cluster.category = result.get("category", "general")

                logger.debug(f"Named cluster: {cluster.name}")

        except Exception as e:
            logger.error(f"Error naming cluster: {e}")
            # Keep existing name/summary

        return cluster

    async def name_clusters(self, clusters: list[TopicCluster]) -> list[TopicCluster]:
        """
        Name multiple clusters.
        """
        for cluster in clusters:
            await self.name_cluster(cluster)
        return clusters

    async def _generate(self, prompt: str) -> str:
        """Generate response from Gemini."""
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=200,
            ),
        )
        return response.text

    def _format_contents(self, contents) -> str:
        """Format contents for the prompt."""
        items = []
        for i, c in enumerate(contents, 1):
            source = c.source_name
            title = c.title[:100]
            body_preview = c.body[:150] if c.body else ""
            items.append(f"{i}. [{source}] {title}\n   {body_preview}")
        return "\n\n".join(items)

    def _parse_response(self, response: str) -> Optional[dict]:
        """Parse the JSON response from Gemini."""
        import json

        # Clean the response
        text = response.strip()

        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse naming response: {e}")
            return None


class BatchTopicNamer(TopicNamer):
    """
    Batch version that names multiple clusters in a single API call.
    More efficient for large numbers of clusters.
    """

    BATCH_PROMPT = """Analyze these topic clusters and provide names and summaries for each.

{clusters_content}

For EACH cluster, respond with this JSON format (as an array):
[
  {{"cluster_id": "id1", "name": "Topic Name", "summary": "Summary.", "category": "tech"}},
  {{"cluster_id": "id2", "name": "Topic Name", "summary": "Summary.", "category": "business"}}
]

Valid categories: tech, business, politics, immigration, culture, science, other"""

    async def name_clusters_batch(
        self, clusters: list[TopicCluster]
    ) -> list[TopicCluster]:
        """
        Name multiple clusters in a single API call.
        """
        if not clusters:
            return clusters

        # Format all clusters
        clusters_content = self._format_all_clusters(clusters)

        prompt = self.BATCH_PROMPT.format(clusters_content=clusters_content)

        try:
            response = await self._generate(prompt)
            results = self._parse_batch_response(response)

            # Apply results
            result_map = {r["cluster_id"]: r for r in results}

            for cluster in clusters:
                if cluster.id in result_map:
                    result = result_map[cluster.id]
                    cluster.name = result.get("name", cluster.name)
                    cluster.summary = result.get("summary", cluster.summary)
                    cluster.category = result.get("category", "general")

            logger.info(f"Batch named {len(clusters)} clusters")

        except Exception as e:
            logger.error(f"Error in batch naming: {e}")
            # Fall back to individual naming
            return await self.name_clusters(clusters)

        return clusters

    def _format_all_clusters(self, clusters: list[TopicCluster]) -> str:
        """Format all clusters for batch prompt."""
        parts = []
        for cluster in clusters:
            content_preview = self._format_contents(cluster.contents[:5])
            parts.append(f"=== Cluster ID: {cluster.id} ===\n{content_preview}")
        return "\n\n".join(parts)

    def _parse_batch_response(self, response: str) -> list[dict]:
        """Parse batch JSON response."""
        import json

        text = response.strip()

        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        try:
            results = json.loads(text.strip())
            if isinstance(results, list):
                return results
            return []
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse batch response: {e}")
            return []
