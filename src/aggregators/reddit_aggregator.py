"""
Reddit content aggregator for community discussions and trending topics
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
import httpx
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class RedditPost(BaseModel):
    """Model for a Reddit post"""

    id: str
    subreddit: str
    title: str
    selftext: str
    score: int
    num_comments: int
    url: str
    created_utc: datetime
    author: str
    permalink: str
    flair: Optional[str] = None

    @property
    def engagement_score(self) -> float:
        """Calculate engagement score based on upvotes and comments"""
        return self.score + (self.num_comments * 2)


class RedditAggregator:
    """Aggregates content from relevant subreddits"""

    # Subreddits relevant to desi immigrants in USA
    DEFAULT_SUBREDDITS = [
        "ABCDesis",  # American Born Confused Desis
        "indian",  # General Indian community
        "h1b",  # H1B visa discussions
        "immigration",  # Immigration topics
        "USCIS",  # USCIS updates
        "f1visa",  # F1 student visa
        "greencard",  # Green card process
        "IndianFood",  # Food & culture
        "Ni_Bondha",  # Telugu community
        "IndiaSpeaks",  # India news relevant to diaspora
    ]

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: str = "DesiPodcastBot/1.0",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.access_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None

    async def _get_access_token(self) -> Optional[str]:
        """Get Reddit OAuth access token"""
        if self.client_id and self.client_secret:
            if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
                return self.access_token

            async with httpx.AsyncClient() as client:
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

    async def fetch_subreddit_posts(
        self,
        subreddit: str,
        limit: int = 25,
        time_filter: str = "day",
        sort: str = "hot",
    ) -> list[RedditPost]:
        """Fetch posts from a subreddit"""
        posts = []

        # Try authenticated request first, fall back to public API
        token = await self._get_access_token()

        async with httpx.AsyncClient() as client:
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

                url = f"{base_url}/r/{subreddit}/{sort}.json"
                params = {"limit": limit, "t": time_filter}

                response = await client.get(url, headers=headers, params=params, timeout=10.0)

                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("data", {}).get("children", []):
                        post_data = item.get("data", {})
                        try:
                            post = RedditPost(
                                id=post_data.get("id", ""),
                                subreddit=post_data.get("subreddit", subreddit),
                                title=post_data.get("title", ""),
                                selftext=post_data.get("selftext", "")[:2000],  # Limit text
                                score=post_data.get("score", 0),
                                num_comments=post_data.get("num_comments", 0),
                                url=post_data.get("url", ""),
                                created_utc=datetime.fromtimestamp(
                                    post_data.get("created_utc", 0)
                                ),
                                author=post_data.get("author", "[deleted]"),
                                permalink=f"https://reddit.com{post_data.get('permalink', '')}",
                                flair=post_data.get("link_flair_text"),
                            )
                            posts.append(post)
                        except Exception as e:
                            logger.warning(f"Failed to parse post: {e}")
                            continue
                else:
                    logger.warning(
                        f"Failed to fetch r/{subreddit}: {response.status_code}"
                    )

            except Exception as e:
                logger.error(f"Error fetching r/{subreddit}: {e}")

        return posts

    async def fetch_all_posts(
        self,
        subreddits: Optional[list[str]] = None,
        limit_per_sub: int = 25,
        time_filter: str = "day",
    ) -> list[RedditPost]:
        """Fetch posts from all configured subreddits"""
        subreddits = subreddits or self.DEFAULT_SUBREDDITS
        all_posts = []

        # Fetch from all subreddits concurrently
        tasks = [
            self.fetch_subreddit_posts(sub, limit_per_sub, time_filter)
            for sub in subreddits
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_posts.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Subreddit fetch error: {result}")

        # Sort by engagement score
        all_posts.sort(key=lambda x: x.engagement_score, reverse=True)

        return all_posts

    async def get_trending_topics(
        self, min_score: int = 50, min_comments: int = 10, limit: int = 20,
        subreddits: Optional[list[str]] = None
    ) -> list[RedditPost]:
        """Get trending topics with high engagement"""
        all_posts = await self.fetch_all_posts(subreddits=subreddits)

        # Filter for high-engagement posts
        trending = [
            post
            for post in all_posts
            if post.score >= min_score or post.num_comments >= min_comments
        ]

        return trending[:limit]

    def categorize_post(self, post: RedditPost) -> list[str]:
        """Categorize a post based on keywords"""
        categories = []
        text = f"{post.title} {post.selftext}".lower()

        category_keywords = {
            "immigration": ["visa", "h1b", "green card", "uscis", "i-140", "i-485", "ead", "gcpriority"],
            "career": ["job", "layoff", "interview", "salary", "offer", "promotion", "wfh", "rto"],
            "community": ["temple", "diwali", "wedding", "festival", "racism", "discrimination"],
            "finance": ["tax", "invest", "401k", "remittance", "mortgage", "credit"],
            "family": ["parents", "marriage", "arrange", "kids", "school", "elder"],
            "food": ["restaurant", "recipe", "biryani", "curry", "vegetarian", "grocery"],
        }

        for category, keywords in category_keywords.items():
            if any(kw in text for kw in keywords):
                categories.append(category)

        return categories if categories else ["general"]
