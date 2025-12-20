"""
News aggregator for immigration and South Asian community news
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
import httpx
import feedparser
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class NewsArticle(BaseModel):
    """Model for a news article"""

    id: str
    title: str
    summary: str
    source: str
    url: str
    published_at: datetime
    category: Optional[str] = None
    image_url: Optional[str] = None

    @property
    def relevance_score(self) -> float:
        """Calculate relevance based on recency and keywords"""
        hours_old = (datetime.now() - self.published_at).total_seconds() / 3600
        recency_score = max(0, 100 - hours_old * 2)  # Decay over time
        return recency_score


class NewsAggregator:
    """Aggregates news from various sources relevant to desi immigrants"""

    # News RSS feeds
    RSS_FEEDS = {
        "times_of_india_nri": "https://timesofindia.indiatimes.com/rssfeeds/7822688.cms",
        "hindustan_times_world": "https://www.hindustantimes.com/feeds/rss/world-news/rssfeed.xml",
        "economic_times_nri": "https://economictimes.indiatimes.com/rssfeeds/7771250.cms",
    }

    # Google News search queries
    SEARCH_QUERIES = [
        "H1B visa news",
        "Indian immigrants USA",
        "green card backlog",
        "USCIS news",
        "Indian American news",
        "tech layoffs H1B",
        "immigration reform 2024",
        "south asian community USA",
    ]

    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key

    async def fetch_rss_feed(self, feed_url: str, source_name: str) -> list[NewsArticle]:
        """Fetch articles from an RSS feed"""
        articles = []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(feed_url, timeout=15.0)
                if response.status_code == 200:
                    feed = feedparser.parse(response.text)

                    for entry in feed.entries[:20]:
                        try:
                            # Parse published date
                            published = None
                            if hasattr(entry, "published_parsed") and entry.published_parsed:
                                published = datetime(*entry.published_parsed[:6])
                            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                                published = datetime(*entry.updated_parsed[:6])
                            else:
                                published = datetime.now()

                            # Get image if available
                            image_url = None
                            if hasattr(entry, "media_content"):
                                image_url = entry.media_content[0].get("url")
                            elif hasattr(entry, "enclosures") and entry.enclosures:
                                image_url = entry.enclosures[0].get("href")

                            article = NewsArticle(
                                id=entry.get("id", entry.get("link", "")),
                                title=entry.get("title", ""),
                                summary=entry.get("summary", entry.get("description", ""))[:500],
                                source=source_name,
                                url=entry.get("link", ""),
                                published_at=published,
                                image_url=image_url,
                            )
                            articles.append(article)
                        except Exception as e:
                            logger.warning(f"Failed to parse RSS entry: {e}")
                            continue

        except Exception as e:
            logger.error(f"Error fetching RSS feed {feed_url}: {e}")

        return articles

    async def fetch_from_supabase(self, hours: int = 24) -> list[NewsArticle]:
        """Fetch recent news from Supabase database (from DesiVibe news pipeline)"""
        if not self.supabase_url or not self.supabase_key:
            return []

        articles = []
        cutoff = datetime.now() - timedelta(hours=hours)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/nw_articles",
                    params={
                        "select": "id,headline,summary,source,url,published_at,category,image_url",
                        "published_at": f"gte.{cutoff.isoformat()}",
                        "order": "published_at.desc",
                        "limit": 50,
                    },
                    headers={
                        "apikey": self.supabase_key,
                        "Authorization": f"Bearer {self.supabase_key}",
                    },
                    timeout=15.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    for item in data:
                        try:
                            article = NewsArticle(
                                id=item["id"],
                                title=item["headline"],
                                summary=item.get("summary", ""),
                                source=item["source"],
                                url=item["url"],
                                published_at=datetime.fromisoformat(
                                    item["published_at"].replace("Z", "+00:00")
                                ),
                                category=item.get("category"),
                                image_url=item.get("image_url"),
                            )
                            articles.append(article)
                        except Exception as e:
                            logger.warning(f"Failed to parse Supabase article: {e}")

        except Exception as e:
            logger.error(f"Error fetching from Supabase: {e}")

        return articles

    async def search_google_news(self, query: str) -> list[NewsArticle]:
        """Search Google News RSS for a query"""
        encoded_query = query.replace(" ", "+")
        feed_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        return await self.fetch_rss_feed(feed_url, "Google News")

    async def fetch_all_news(self) -> list[NewsArticle]:
        """Fetch news from all sources"""
        all_articles = []

        # 1. Fetch from Supabase (existing DesiVibe pipeline)
        supabase_articles = await self.fetch_from_supabase()
        all_articles.extend(supabase_articles)
        logger.info(f"Fetched {len(supabase_articles)} articles from Supabase")

        # 2. Fetch from RSS feeds
        rss_tasks = [
            self.fetch_rss_feed(url, name) for name, url in self.RSS_FEEDS.items()
        ]
        rss_results = await asyncio.gather(*rss_tasks, return_exceptions=True)

        for result in rss_results:
            if isinstance(result, list):
                all_articles.extend(result)

        # 3. Search Google News for specific queries (limit to avoid rate limits)
        search_tasks = [self.search_google_news(q) for q in self.SEARCH_QUERIES[:3]]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        for result in search_results:
            if isinstance(result, list):
                all_articles.extend(result)

        # Deduplicate by URL
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)

        # Sort by relevance (recency)
        unique_articles.sort(key=lambda x: x.published_at, reverse=True)

        logger.info(f"Total unique articles: {len(unique_articles)}")
        return unique_articles

    def categorize_article(self, article: NewsArticle) -> str:
        """Categorize an article based on content"""
        text = f"{article.title} {article.summary}".lower()

        if any(kw in text for kw in ["visa", "h1b", "green card", "uscis", "immigration"]):
            return "immigration"
        elif any(kw in text for kw in ["layoff", "job", "tech", "startup", "hire"]):
            return "career"
        elif any(kw in text for kw in ["community", "temple", "festival", "diwali"]):
            return "community"
        elif any(kw in text for kw in ["tax", "money", "invest", "economy"]):
            return "finance"
        elif any(kw in text for kw in ["discrimination", "racism", "hate", "rights"]):
            return "social_issues"
        else:
            return "general"

    async def get_top_stories(self, limit: int = 10) -> list[NewsArticle]:
        """Get top stories for the podcast"""
        all_news = await self.fetch_all_news()

        # Filter for last 24 hours
        cutoff = datetime.now() - timedelta(hours=24)
        recent = [a for a in all_news if a.published_at > cutoff]

        # Categorize and prioritize
        for article in recent:
            if not article.category:
                article.category = self.categorize_article(article)

        # Prioritize immigration and career news
        priority_order = ["immigration", "career", "social_issues", "community", "finance", "general"]

        def sort_key(article):
            try:
                priority = priority_order.index(article.category or "general")
            except ValueError:
                priority = len(priority_order)
            return (priority, -article.relevance_score)

        recent.sort(key=sort_key)

        return recent[:limit]
