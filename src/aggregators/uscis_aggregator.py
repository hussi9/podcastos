"""
USCIS and immigration-specific content aggregator
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
import httpx
import feedparser
from pydantic import BaseModel
import logging
import re

logger = logging.getLogger(__name__)


class ImmigrationUpdate(BaseModel):
    """Model for immigration-related updates"""

    id: str
    title: str
    summary: str
    source: str
    url: str
    published_at: datetime
    update_type: str  # visa_bulletin, processing_times, policy, news
    priority: int = 5  # 1-10, higher = more important

    @property
    def is_urgent(self) -> bool:
        return self.priority >= 7


class USCISAggregator:
    """Aggregates immigration updates from official and community sources"""

    # Official RSS feeds
    OFFICIAL_FEEDS = {
        "uscis_news": "https://www.uscis.gov/news/news-releases/feed",
        "uscis_alerts": "https://www.uscis.gov/news/alerts/feed",
    }

    # Community tracking sites
    COMMUNITY_SOURCES = {
        "trackitt": "https://www.trackitt.com/",
        "visajourney": "https://www.visajourney.com/",
        "immihelp": "https://www.immihelp.com/",
    }

    # Visa Bulletin URL (State Department)
    VISA_BULLETIN_URL = "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html"

    def __init__(self):
        self.cached_processing_times: Optional[dict] = None
        self.cache_timestamp: Optional[datetime] = None

    async def fetch_uscis_news(self) -> list[ImmigrationUpdate]:
        """Fetch official USCIS news and alerts"""
        updates = []

        for source_name, feed_url in self.OFFICIAL_FEEDS.items():
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(feed_url, timeout=15.0)
                    if response.status_code == 200:
                        feed = feedparser.parse(response.text)

                        for entry in feed.entries[:15]:
                            try:
                                published = datetime.now()
                                if hasattr(entry, "published_parsed") and entry.published_parsed:
                                    published = datetime(*entry.published_parsed[:6])

                                # Determine priority based on keywords
                                title_lower = entry.get("title", "").lower()
                                priority = self._calculate_priority(title_lower)

                                update = ImmigrationUpdate(
                                    id=entry.get("id", entry.get("link", "")),
                                    title=entry.get("title", ""),
                                    summary=entry.get("summary", "")[:500],
                                    source="USCIS",
                                    url=entry.get("link", ""),
                                    published_at=published,
                                    update_type="policy" if "alert" in source_name else "news",
                                    priority=priority,
                                )
                                updates.append(update)
                            except Exception as e:
                                logger.warning(f"Failed to parse USCIS entry: {e}")

            except Exception as e:
                logger.error(f"Error fetching {source_name}: {e}")

        return updates

    def _calculate_priority(self, text: str) -> int:
        """Calculate priority score based on keywords"""
        high_priority_keywords = [
            "h-1b", "h1b", "premium processing", "fee increase",
            "policy change", "rule change", "executive order",
            "employment authorization", "ead", "i-140", "i-485",
            "green card", "priority date", "visa bulletin",
        ]

        medium_priority_keywords = [
            "processing time", "naturalization", "citizenship",
            "travel document", "advance parole", "asylum",
        ]

        text_lower = text.lower()

        if any(kw in text_lower for kw in high_priority_keywords):
            return 8
        elif any(kw in text_lower for kw in medium_priority_keywords):
            return 6
        else:
            return 4

    async def check_visa_bulletin_update(self) -> Optional[ImmigrationUpdate]:
        """Check for new Visa Bulletin updates"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.VISA_BULLETIN_URL, timeout=15.0)
                if response.status_code == 200:
                    # Parse for the latest bulletin
                    content = response.text.lower()

                    # Look for current month's bulletin
                    months = [
                        "january", "february", "march", "april", "may", "june",
                        "july", "august", "september", "october", "november", "december"
                    ]
                    current_month = datetime.now().strftime("%B").lower()
                    current_year = datetime.now().year

                    # Simple check - in production, use proper HTML parsing
                    if f"{current_month} {current_year}" in content:
                        return ImmigrationUpdate(
                            id=f"visa-bulletin-{current_month}-{current_year}",
                            title=f"Visa Bulletin for {current_month.title()} {current_year}",
                            summary="The latest Visa Bulletin has been released with updated priority dates for employment and family-based categories.",
                            source="State Department",
                            url=self.VISA_BULLETIN_URL,
                            published_at=datetime.now(),
                            update_type="visa_bulletin",
                            priority=9,
                        )

        except Exception as e:
            logger.error(f"Error checking Visa Bulletin: {e}")

        return None

    async def get_processing_time_summary(self) -> Optional[dict]:
        """Get a summary of current processing times (simplified)"""
        # In production, this would scrape USCIS processing times page
        # For now, return a structured summary that can be updated

        # Check cache
        if self.cached_processing_times and self.cache_timestamp:
            if datetime.now() - self.cache_timestamp < timedelta(hours=6):
                return self.cached_processing_times

        # Placeholder - in production, scrape actual data
        processing_summary = {
            "last_updated": datetime.now().isoformat(),
            "forms": {
                "I-140": {
                    "regular": "8-12 months",
                    "premium": "15 business days",
                    "note": "EB2/EB3 employment-based petitions",
                },
                "I-485": {
                    "employment": "12-24 months",
                    "family": "12-36 months",
                    "note": "Adjustment of Status applications",
                },
                "I-765": {
                    "initial": "3-6 months",
                    "renewal": "3-6 months",
                    "note": "Employment Authorization Document",
                },
                "I-131": {
                    "standard": "4-8 months",
                    "note": "Advance Parole / Travel Document",
                },
            },
            "service_centers": {
                "Texas": "Generally faster for I-140",
                "Nebraska": "Moderate processing times",
                "California": "Higher volume, longer waits",
            },
        }

        self.cached_processing_times = processing_summary
        self.cache_timestamp = datetime.now()

        return processing_summary

    async def get_all_updates(self) -> list[ImmigrationUpdate]:
        """Get all immigration updates"""
        all_updates = []

        # Fetch USCIS news
        uscis_updates = await self.fetch_uscis_news()
        all_updates.extend(uscis_updates)

        # Check Visa Bulletin
        visa_bulletin = await self.check_visa_bulletin_update()
        if visa_bulletin:
            all_updates.append(visa_bulletin)

        # Sort by priority and recency
        all_updates.sort(key=lambda x: (-x.priority, x.published_at), reverse=True)

        return all_updates

    async def get_urgent_updates(self) -> list[ImmigrationUpdate]:
        """Get only urgent/high-priority updates"""
        all_updates = await self.get_all_updates()
        return [u for u in all_updates if u.is_urgent]

    def generate_immigration_segment(self, updates: list[ImmigrationUpdate]) -> str:
        """Generate a summary segment for the podcast"""
        if not updates:
            return "No major immigration updates to report today."

        lines = ["Here's what's happening in the immigration world:"]

        for i, update in enumerate(updates[:5], 1):
            source = f"({update.source})" if update.source != "USCIS" else ""
            lines.append(f"{i}. {update.title} {source}")

        return "\n".join(lines)
