"""
Content ranker that analyzes and ranks topics for the podcast
"""

from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
import logging
from collections import Counter
import re

from .reddit_aggregator import RedditAggregator, RedditPost
from .news_aggregator import NewsAggregator, NewsArticle
from .uscis_aggregator import USCISAggregator, ImmigrationUpdate

logger = logging.getLogger(__name__)


class PodcastTopic(BaseModel):
    """A ranked topic for the podcast"""

    id: str
    title: str
    summary: str
    category: str
    score: float
    sources: list[str]
    source_count: int
    key_points: list[str]
    community_sentiment: Optional[str] = None  # positive, negative, mixed, neutral
    is_breaking: bool = False
    is_trending: bool = False

    # Original source items
    news_articles: list[dict] = []
    reddit_posts: list[dict] = []
    immigration_updates: list[dict] = []


class ContentRanker:
    """
    Aggregates content from all sources and ranks topics
    for inclusion in the daily podcast
    """

    def __init__(
        self,
        reddit_client_id: Optional[str] = None,
        reddit_client_secret: Optional[str] = None,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
    ):
        self.reddit = RedditAggregator(
            client_id=reddit_client_id,
            client_secret=reddit_client_secret,
        )
        self.news = NewsAggregator(
            supabase_url=supabase_url,
            supabase_key=supabase_key,
        )
        self.uscis = USCISAggregator()

    async def gather_all_content(self, subreddits: list[str] = None) -> dict:
        """Gather content from all sources"""
        import asyncio

        logger.info("Gathering content from all sources...")

        # Fetch from all sources concurrently
        reddit_task = self.reddit.get_trending_topics(
            min_score=30, min_comments=5, limit=30, subreddits=subreddits
        )
        news_task = self.news.get_top_stories(limit=20)
        uscis_task = self.uscis.get_all_updates()

        reddit_posts, news_articles, uscis_updates = await asyncio.gather(
            reddit_task, news_task, uscis_task, return_exceptions=True
        )

        # Handle exceptions
        if isinstance(reddit_posts, Exception):
            logger.error(f"Reddit fetch failed: {reddit_posts}")
            reddit_posts = []
        if isinstance(news_articles, Exception):
            logger.error(f"News fetch failed: {news_articles}")
            news_articles = []
        if isinstance(uscis_updates, Exception):
            logger.error(f"USCIS fetch failed: {uscis_updates}")
            uscis_updates = []

        logger.info(
            f"Gathered: {len(reddit_posts)} Reddit posts, "
            f"{len(news_articles)} news articles, "
            f"{len(uscis_updates)} USCIS updates"
        )

        return {
            "reddit": reddit_posts,
            "news": news_articles,
            "uscis": uscis_updates,
        }

    def extract_keywords(self, text: str) -> list[str]:
        """Extract important keywords from text"""
        # Common words to ignore
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once",
            "here", "there", "when", "where", "why", "how", "all",
            "each", "few", "more", "most", "other", "some", "such",
            "no", "nor", "not", "only", "own", "same", "so", "than",
            "too", "very", "just", "and", "but", "if", "or", "because",
            "until", "while", "this", "that", "these", "those", "i",
            "me", "my", "myself", "we", "our", "you", "your", "he",
            "him", "his", "she", "her", "it", "its", "they", "them",
            "what", "which", "who", "whom", "any", "get", "got",
        }

        # Extract words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        keywords = [w for w in words if w not in stopwords]

        # Get frequency
        freq = Counter(keywords)
        return [word for word, count in freq.most_common(10)]

    def cluster_by_topic(self, content: dict) -> list[PodcastTopic]:
        """Cluster content items into topics"""
        topics: dict[str, PodcastTopic] = {}

        # Define topic clusters with their keywords
        topic_clusters = {
            "h1b_visa": {
                "keywords": ["h1b", "h-1b", "visa", "lottery", "cap", "premium"],
                "title": "H-1B Visa Updates",
                "category": "immigration",
            },
            "green_card": {
                "keywords": ["green card", "greencard", "gc", "i-140", "i-485", "priority date", "eb2", "eb3"],
                "title": "Green Card & Priority Dates",
                "category": "immigration",
            },
            "layoffs_jobs": {
                "keywords": ["layoff", "laid off", "job", "hiring", "interview", "offer", "rto", "return to office"],
                "title": "Jobs & Career News",
                "category": "career",
            },
            "uscis_policy": {
                "keywords": ["uscis", "policy", "rule", "fee", "processing", "ead", "parole"],
                "title": "USCIS Policy Updates",
                "category": "immigration",
            },
            "community_culture": {
                "keywords": ["diwali", "temple", "wedding", "festival", "community", "indian american"],
                "title": "Community & Culture",
                "category": "community",
            },
            "discrimination": {
                "keywords": ["racism", "discrimination", "hate", "bias", "prejudice"],
                "title": "Social Issues & Discrimination",
                "category": "social",
            },
            "finance_tax": {
                "keywords": ["tax", "401k", "investment", "remittance", "property", "mortgage"],
                "title": "Finance & Taxes",
                "category": "finance",
            },
            "family_life": {
                "keywords": ["parents", "family", "kids", "school", "marriage", "dating", "arrange"],
                "title": "Family & Relationships",
                "category": "family",
            },
            "entertainment": {
                "keywords": ["bollywood", "movie", "film", "netflix", "actor", "actress", "music", "cricket", "ipl", "kohli", "sharma", "celebrity", "shah rukh", "aamir", "salman", "priyanka", "deepika"],
                "title": "Entertainment & Sports",
                "category": "entertainment",
            },
            "tech_startups": {
                "keywords": ["startup", "founder", "entrepreneur", "tech ceo", "indian ceo", "silicon valley", "ai", "sundar", "nadella", "pichai"],
                "title": "Tech & Startups",
                "category": "tech",
            },
        }

        # Process Reddit posts
        for post in content.get("reddit", []):
            if not isinstance(post, RedditPost):
                continue

            text = f"{post.title} {post.selftext}".lower()

            for cluster_id, cluster_info in topic_clusters.items():
                if any(kw in text for kw in cluster_info["keywords"]):
                    if cluster_id not in topics:
                        topics[cluster_id] = PodcastTopic(
                            id=cluster_id,
                            title=cluster_info["title"],
                            summary="",
                            category=cluster_info["category"],
                            score=0,
                            sources=[],
                            source_count=0,
                            key_points=[],
                            reddit_posts=[],
                            news_articles=[],
                            immigration_updates=[],
                        )

                    topic = topics[cluster_id]
                    topic.reddit_posts.append({
                        "title": post.title,
                        "subreddit": post.subreddit,
                        "score": post.score,
                        "comments": post.num_comments,
                        "url": post.permalink,
                    })
                    topic.score += post.engagement_score / 100
                    if "reddit" not in topic.sources:
                        topic.sources.append("reddit")
                    break  # Assign to first matching cluster

        # Process news articles
        for article in content.get("news", []):
            if not isinstance(article, NewsArticle):
                continue

            text = f"{article.title} {article.summary}".lower()

            for cluster_id, cluster_info in topic_clusters.items():
                if any(kw in text for kw in cluster_info["keywords"]):
                    if cluster_id not in topics:
                        topics[cluster_id] = PodcastTopic(
                            id=cluster_id,
                            title=cluster_info["title"],
                            summary="",
                            category=cluster_info["category"],
                            score=0,
                            sources=[],
                            source_count=0,
                            key_points=[],
                            reddit_posts=[],
                            news_articles=[],
                            immigration_updates=[],
                        )

                    topic = topics[cluster_id]
                    topic.news_articles.append({
                        "title": article.title,
                        "source": article.source,
                        "url": article.url,
                        "published": article.published_at.isoformat(),
                    })
                    topic.score += 2  # News articles get higher weight
                    if article.source not in topic.sources:
                        topic.sources.append(article.source)

                    # Check if breaking news
                    hours_old = (datetime.now() - article.published_at).total_seconds() / 3600
                    if hours_old < 6:
                        topic.is_breaking = True
                    break

        # Process USCIS updates
        for update in content.get("uscis", []):
            if not isinstance(update, ImmigrationUpdate):
                continue

            # USCIS updates go to relevant immigration topics
            if "visa" in update.title.lower() or "h-1b" in update.title.lower():
                cluster_id = "h1b_visa"
            elif "green card" in update.title.lower() or "priority" in update.title.lower():
                cluster_id = "green_card"
            else:
                cluster_id = "uscis_policy"

            if cluster_id not in topics:
                cluster_info = topic_clusters.get(cluster_id, {
                    "title": "Immigration Updates",
                    "category": "immigration",
                })
                topics[cluster_id] = PodcastTopic(
                    id=cluster_id,
                    title=cluster_info.get("title", "Immigration Updates"),
                    summary="",
                    category=cluster_info.get("category", "immigration"),
                    score=0,
                    sources=[],
                    source_count=0,
                    key_points=[],
                    reddit_posts=[],
                    news_articles=[],
                    immigration_updates=[],
                )

            topic = topics[cluster_id]
            topic.immigration_updates.append({
                "title": update.title,
                "summary": update.summary,
                "source": update.source,
                "url": update.url,
                "priority": update.priority,
            })
            topic.score += update.priority  # Use priority as score
            if update.source not in topic.sources:
                topic.sources.append(update.source)
            if update.is_urgent:
                topic.is_breaking = True

        # Calculate final scores and metadata
        for topic in topics.values():
            topic.source_count = (
                len(topic.reddit_posts) +
                len(topic.news_articles) +
                len(topic.immigration_updates)
            )

            # Boost score if multiple source types
            if len(topic.sources) > 1:
                topic.score *= 1.5

            # Mark as trending if high Reddit engagement
            reddit_engagement = sum(p.get("score", 0) + p.get("comments", 0) * 2 for p in topic.reddit_posts)
            if reddit_engagement > 500:
                topic.is_trending = True

            # Generate summary
            topic.summary = self._generate_topic_summary(topic)

            # Extract key points
            topic.key_points = self._extract_key_points(topic)

            # Analyze sentiment from Reddit
            topic.community_sentiment = self._analyze_sentiment(topic.reddit_posts)

        return list(topics.values())

    def _generate_topic_summary(self, topic: PodcastTopic) -> str:
        """Generate a brief summary for a topic"""
        parts = []

        if topic.news_articles:
            parts.append(f"{len(topic.news_articles)} news article(s)")
        if topic.reddit_posts:
            parts.append(f"{len(topic.reddit_posts)} community discussion(s)")
        if topic.immigration_updates:
            parts.append(f"{len(topic.immigration_updates)} official update(s)")

        source_text = " and ".join(parts) if parts else "various sources"
        return f"{topic.title} - Based on {source_text}"

    def _extract_key_points(self, topic: PodcastTopic) -> list[str]:
        """Extract key points from topic content"""
        points = []

        # Get top Reddit discussions
        for post in topic.reddit_posts[:3]:
            points.append(f"Community discussing: {post['title'][:100]}")

        # Get news headlines
        for article in topic.news_articles[:2]:
            points.append(f"News: {article['title'][:100]}")

        # Get USCIS updates
        for update in topic.immigration_updates[:2]:
            points.append(f"Official: {update['title'][:100]}")

        return points[:5]

    def _analyze_sentiment(self, reddit_posts: list[dict]) -> str:
        """Simple sentiment analysis based on Reddit engagement"""
        if not reddit_posts:
            return "neutral"

        # This is a simplified version - in production, use NLP
        total_score = sum(p.get("score", 0) for p in reddit_posts)
        avg_comments = sum(p.get("comments", 0) for p in reddit_posts) / len(reddit_posts)

        if avg_comments > 50:
            return "mixed"  # High discussion = controversy
        elif total_score > 500:
            return "positive"
        elif total_score < 0:
            return "negative"
        else:
            return "neutral"

    async def get_ranked_topics(self, limit: int = 5, subreddits: list[str] = None) -> list[PodcastTopic]:
        """Get ranked topics for the podcast"""
        content = await self.gather_all_content(subreddits=subreddits)
        topics = self.cluster_by_topic(content)

        # Sort by score
        topics.sort(key=lambda x: (-x.score, -x.source_count))

        # Ensure diversity - at least one from each major category if available
        final_topics = []
        categories_covered = set()

        # First pass - add breaking news and high-score topics
        for topic in topics:
            if topic.is_breaking or topic.score > 10:
                if len(final_topics) < limit:
                    final_topics.append(topic)
                    categories_covered.add(topic.category)

        # Second pass - ensure category diversity
        priority_categories = ["immigration", "career", "community"]
        for category in priority_categories:
            if category not in categories_covered:
                for topic in topics:
                    if topic.category == category and topic not in final_topics:
                        if len(final_topics) < limit:
                            final_topics.append(topic)
                            categories_covered.add(category)
                        break

        # Fill remaining slots with highest scored topics
        for topic in topics:
            if topic not in final_topics and len(final_topics) < limit:
                final_topics.append(topic)

        logger.info(f"Selected {len(final_topics)} topics for podcast")
        return final_topics[:limit]
