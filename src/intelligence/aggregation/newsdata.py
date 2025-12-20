"""NewsData.io connector for news aggregation."""

import os
from datetime import datetime
from typing import Optional
import httpx
import logging

from .base import BaseConnector
from ..models.content import RawContent, SourceConfig


logger = logging.getLogger(__name__)

NEWSDATA_API_BASE = "https://newsdata.io/api/1"


class NewsDataConnector(BaseConnector):
    """
    Connector for NewsData.io API.
    Requires NEWSDATA_API_KEY environment variable.
    Free tier: 200 credits/day, 10 results/request.
    """

    def __init__(self, config: Optional[SourceConfig] = None, api_key: Optional[str] = None):
        if config is None:
            config = SourceConfig(
                id="newsdata",
                source_type="newsdata",
                name="NewsData.io",
                config={"categories": ["technology", "business"]},
                priority=8,
                credibility_score=0.85,
            )
        super().__init__(config)
        self.api_key = api_key or os.getenv("NEWSDATA_API_KEY")
        if not self.api_key:
            logger.warning("NEWSDATA_API_KEY not set - NewsData connector will not work")

    async def fetch(self, limit: int = 50) -> list[RawContent]:
        """Fetch news from NewsData.io."""
        if not self.api_key:
            logger.error("NewsData API key not configured")
            return []

        all_items = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Build query parameters
            params = {
                "apikey": self.api_key,
                "language": "en",
            }

            # Add categories if specified
            categories = self.config.config.get("categories", [])
            if categories:
                params["category"] = ",".join(categories)

            # Add domains if specified
            domains = self.config.config.get("domains", [])
            if domains:
                params["domain"] = ",".join(domains)

            # Add query if specified
            query = self.config.config.get("q")
            if query:
                params["q"] = query

            # Fetch pages until we have enough items
            next_page = None
            while len(all_items) < limit:
                if next_page:
                    params["page"] = next_page

                try:
                    response = await client.get(f"{NEWSDATA_API_BASE}/news", params=params)
                    response.raise_for_status()
                    data = response.json()

                    if data.get("status") != "success":
                        logger.error(f"NewsData API error: {data.get('message')}")
                        break

                    results = data.get("results", [])
                    if not results:
                        break

                    for article in results:
                        try:
                            item = self._parse_article(article)
                            if item and self.filter_by_keywords(item):
                                all_items.append(item)
                        except Exception as e:
                            logger.debug(f"Error parsing NewsData article: {e}")

                    # Check for next page
                    next_page = data.get("nextPage")
                    if not next_page:
                        break

                except httpx.HTTPError as e:
                    logger.error(f"NewsData API HTTP error: {e}")
                    break
                except Exception as e:
                    logger.error(f"NewsData API error: {e}")
                    break

        return all_items[:limit]

    def _parse_article(self, article: dict) -> Optional[RawContent]:
        """Parse a NewsData article into RawContent."""
        title = article.get("title")
        if not title:
            return None

        # Parse publication date
        pub_date_str = article.get("pubDate")
        if pub_date_str:
            try:
                # NewsData format: "2024-01-15 10:30:00"
                published_at = datetime.strptime(pub_date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                published_at = datetime.now()
        else:
            published_at = datetime.now()

        # Get source name
        source_name = article.get("source_id", "NewsData")

        # Build body from description and content
        description = article.get("description", "") or ""
        content = article.get("content", "") or ""
        body = f"{description}\n\n{content}".strip()

        return RawContent(
            id=RawContent.generate_id(article.get("link", title), "newsdata"),
            source_type="newsdata",
            source_name=source_name,
            title=title,
            body=body,
            url=article.get("link"),
            author=article.get("creator", [None])[0] if article.get("creator") else None,
            published_at=published_at,
            categories=article.get("category", []),
        )

    async def search(self, query: str, limit: int = 20) -> list[RawContent]:
        """
        Search for specific news topics.
        """
        if not self.api_key:
            return []

        items = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {
                "apikey": self.api_key,
                "language": "en",
                "q": query,
            }

            try:
                response = await client.get(f"{NEWSDATA_API_BASE}/news", params=params)
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "success":
                    for article in data.get("results", [])[:limit]:
                        item = self._parse_article(article)
                        if item:
                            items.append(item)
            except Exception as e:
                logger.error(f"NewsData search error: {e}")

        return items
