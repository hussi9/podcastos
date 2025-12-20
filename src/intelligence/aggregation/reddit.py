"""Reddit connector using OAuth API."""

import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import httpx
import logging

from .base import BaseConnector
from ..models.content import RawContent, SourceConfig


logger = logging.getLogger(__name__)


class RedditConnector(BaseConnector):
    """
    Connector for Reddit using OAuth API.
    Uses REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env variables.
    Falls back to public API if credentials not available.
    """

    def __init__(self, config: Optional[SourceConfig] = None):
        if config is None:
            config = SourceConfig(
                id="reddit",
                source_type="reddit",
                name="Reddit",
                config={"subreddits": ["technology", "programming"]},
                priority=8,
                credibility_score=0.6,
            )
        super().__init__(config)

        self.client_id = os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.user_agent = os.getenv("REDDIT_USER_AGENT", "PodcastOS/1.0")

        self.access_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None

        self.subreddits = config.config.get("subreddits", [])
        self.sort = config.config.get("sort", "hot")
        self.time_filter = config.config.get("time_filter", "day")

    async def _get_access_token(self) -> Optional[str]:
        """Get Reddit OAuth access token."""
        if not self.client_id or not self.client_secret:
            return None

        # Check if existing token is still valid
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    "https://www.reddit.com/api/v1/access_token",
                    auth=(self.client_id, self.client_secret),
                    data={"grant_type": "client_credentials"},
                    headers={"User-Agent": self.user_agent},
                )
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data["access_token"]
                    self.token_expiry = datetime.now() + timedelta(
                        seconds=data["expires_in"] - 60
                    )
                    return self.access_token
            except Exception as e:
                logger.error(f"Failed to get Reddit access token: {e}")

        return None

    async def fetch(self, limit: int = 50) -> list[RawContent]:
        """Fetch posts from all configured subreddits."""
        all_items = []
        per_subreddit = max(10, limit // len(self.subreddits)) if self.subreddits else limit

        # Fetch from all subreddits concurrently
        tasks = [
            self._fetch_subreddit(subreddit, per_subreddit)
            for subreddit in self.subreddits
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_items.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Reddit fetch error: {result}")

        # Sort by engagement score
        all_items.sort(key=lambda x: x.engagement_score, reverse=True)

        # Apply keyword filters
        filtered_items = [item for item in all_items if self.filter_by_keywords(item)]

        return filtered_items[:limit]

    async def _fetch_subreddit(self, subreddit: str, limit: int) -> list[RawContent]:
        """Fetch posts from a single subreddit."""
        items = []

        # Try authenticated request first
        token = await self._get_access_token()

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                if token:
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "User-Agent": self.user_agent,
                    }
                    base_url = "https://oauth.reddit.com"
                else:
                    headers = {"User-Agent": self.user_agent}
                    base_url = "https://www.reddit.com"

                url = f"{base_url}/r/{subreddit}/{self.sort}.json"
                params = {"limit": limit, "t": self.time_filter}

                response = await client.get(url, headers=headers, params=params)

                if response.status_code == 200:
                    data = response.json()
                    for child in data.get("data", {}).get("children", []):
                        post_data = child.get("data", {})
                        try:
                            item = self._parse_post(post_data, subreddit)
                            if item:
                                items.append(item)
                        except Exception as e:
                            logger.debug(f"Error parsing Reddit post: {e}")
                else:
                    logger.warning(f"Failed to fetch r/{subreddit}: {response.status_code}")

            except Exception as e:
                logger.error(f"Error fetching r/{subreddit}: {e}")

        return items

    def _parse_post(self, post_data: dict, subreddit: str) -> Optional[RawContent]:
        """Parse a Reddit post into RawContent."""
        title = post_data.get("title")
        if not title:
            return None

        # Skip stickied/pinned posts
        if post_data.get("stickied"):
            return None

        # Build body from selftext
        body = post_data.get("selftext", "")[:2000]  # Limit length

        # Get permalink
        permalink = f"https://reddit.com{post_data.get('permalink', '')}"

        # Parse creation time
        created_utc = post_data.get("created_utc", 0)
        published_at = datetime.fromtimestamp(created_utc) if created_utc else datetime.now()

        return RawContent(
            id=RawContent.generate_id(post_data.get("id", ""), "reddit"),
            source_type="reddit",
            source_name=f"r/{subreddit}",
            title=title,
            body=body,
            url=permalink,
            author=post_data.get("author", "[deleted]"),
            published_at=published_at,
            score=post_data.get("score", 0),
            comments=post_data.get("num_comments", 0),
            categories=[post_data.get("link_flair_text")] if post_data.get("link_flair_text") else [],
        )

    async def fetch_comments(self, post_id: str, limit: int = 10) -> list[str]:
        """
        Fetch top comments for a post.
        Useful for getting community perspectives.
        """
        comments = []

        token = await self._get_access_token()

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                if token:
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "User-Agent": self.user_agent,
                    }
                    base_url = "https://oauth.reddit.com"
                else:
                    headers = {"User-Agent": self.user_agent}
                    base_url = "https://www.reddit.com"

                url = f"{base_url}/comments/{post_id}.json"
                params = {"limit": limit, "sort": "best"}

                response = await client.get(url, headers=headers, params=params)

                if response.status_code == 200:
                    data = response.json()
                    # Comments are in the second element
                    if len(data) > 1:
                        for child in data[1].get("data", {}).get("children", []):
                            comment_data = child.get("data", {})
                            body = comment_data.get("body", "")
                            if body and body != "[deleted]" and body != "[removed]":
                                comments.append(body)
                                if len(comments) >= limit:
                                    break

            except Exception as e:
                logger.error(f"Error fetching comments for {post_id}: {e}")

        return comments

    async def search(self, query: str, limit: int = 25) -> list[RawContent]:
        """
        Search across Reddit for a specific query.
        """
        items = []

        token = await self._get_access_token()

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                if token:
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "User-Agent": self.user_agent,
                    }
                    base_url = "https://oauth.reddit.com"
                else:
                    headers = {"User-Agent": self.user_agent}
                    base_url = "https://www.reddit.com"

                url = f"{base_url}/search.json"
                params = {
                    "q": query,
                    "limit": limit,
                    "sort": "relevance",
                    "t": "week",
                }

                response = await client.get(url, headers=headers, params=params)

                if response.status_code == 200:
                    data = response.json()
                    for child in data.get("data", {}).get("children", []):
                        post_data = child.get("data", {})
                        item = self._parse_post(post_data, post_data.get("subreddit", ""))
                        if item:
                            items.append(item)

            except Exception as e:
                logger.error(f"Error searching Reddit: {e}")

        return items
