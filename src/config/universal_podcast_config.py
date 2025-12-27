"""
Universal Podcast Configuration System
Supports ANY topic, niche, or vertical

This module provides flexible configuration for:
- Tech, Business, Gaming, Sports, Science, Entertainment
- News, Education, Health, Food, Travel, Arts
- Custom combinations
- Literally ANY topic you can imagine!
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class PodcastType(Enum):
    """Built-in podcast types"""
    NEWS_DAILY = "news_daily"
    TECH_STARTUPS = "tech_startups"
    GAMING_ESPORTS = "gaming_esports"
    BUSINESS_FINANCE = "business_finance"
    SPORTS = "sports"
    SCIENCE_EDUCATION = "science_education"
    ENTERTAINMENT = "entertainment"
    HEALTH_FITNESS = "health_fitness"
    FOOD_COOKING = "food_cooking"
    TRAVEL_LIFESTYLE = "travel_lifestyle"
    ARTS_CULTURE = "arts_culture"
    CUSTOM = "custom"


class ToneStyle(Enum):
    """AI tone styles"""
    PROFESSIONAL_NEUTRAL = "professional_neutral"
    PROFESSIONAL_ANALYTICAL = "professional_analytical"
    CASUAL_CONVERSATIONAL = "casual_conversational"
    ENTHUSIASTIC_ENERGETIC = "enthusiastic_energetic"
    EDUCATIONAL_ACCESSIBLE = "educational_accessible"
    FUN_ENTERTAINING = "fun_entertaining"
    SERIOUS_INVESTIGATIVE = "serious_investigative"


class AudienceType(Enum):
    """Target audience types"""
    GENERAL_PUBLIC = "general_public"
    PROFESSIONALS = "professionals"
    ENTHUSIASTS = "enthusiasts"
    BEGINNERS = "beginners"
    EXPERTS = "experts"
    STUDENTS = "students"


@dataclass
class SourceConfig:
    """Configuration for a content source"""
    enabled: bool = True
    subreddits: List[str] = field(default_factory=list)
    twitter_accounts: List[str] = field(default_factory=list)
    twitter_hashtags: List[str] = field(default_factory=list)
    rss_feeds: List[Dict[str, str]] = field(default_factory=list)
    youtube_channels: List[str] = field(default_factory=list)
    news_api_queries: List[str] = field(default_factory=list)
    custom_websites: List[str] = field(default_factory=list)
    
    max_sources_per_platform: int = 50
    days_back: int = 7


@dataclass
class AIConfig:
    """AI behavior configuration"""
    tone: ToneStyle = ToneStyle.CASUAL_CONVERSATIONAL
    audience: AudienceType = AudienceType.GENERAL_PUBLIC
    
    # Models
    research_model: str = "gemini-2.0-flash-exp"
    script_model: str = "gemini-2.0-flash-exp"
    newsletter_model: str = "gemini-2.0-flash-thinking-exp"
    
    # Behavior
    use_thinking_mode: bool = True
    fact_checking_enabled: bool = True
    min_credibility_score: float = 0.75
    
    # Content preferences
    preferred_content_types: List[str] = field(default_factory=lambda: ["articles", "discussions", "videos"])
    avoid_content_types: List[str] = field(default_factory=list)


@dataclass
class ProductionConfig:
    """Podcast production settings"""
    target_length_minutes: int = 20
    update_frequency: str = "weekly"  # daily, twice_weekly, weekly, biweekly, monthly
    
    # Hosts
    host_count: int = 2
    host_voices: List[str] = field(default_factory=lambda: ["en-US-Neural2-A", "en-US-Neural2-C"])
    host_personalities: List[str] = field(default_factory=lambda: ["analytical", "conversational"])
    
    # Quality
    min_source_count: int = 10
    enable_music: bool = True
    enable_sound_effects: bool = False


@dataclass
class NewsletterConfig:
    """Newsletter settings"""
    enabled: bool = True
    email_enabled: bool = False
    
    # Content
    max_sections: int = 5
    items_per_section: int = 5
    include_sources: bool = True
    
    # Distribution
    from_email: Optional[str] = None
    subject_template: str = "{podcast_name} - {date}"


@dataclass
class UniversalPodcastConfig:
    """
    Universal podcast configuration
    Works for ANY topic/niche
    """
    # Basic Info
    name: str
    description: str
    podcast_type: PodcastType = PodcastType.CUSTOM
    
    # Topics & Keywords
    topics: List[str] = field(default_factory=list)
    required_keywords: List[str] = field(default_factory=list)
    optional_keywords: List[str] = field(default_factory=list)
    exclude_keywords: List[str] = field(default_factory=list)
    
    # Configurations
    sources: SourceConfig = field(default_factory=SourceConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    production: ProductionConfig = field(default_factory=ProductionConfig)
    newsletter: NewsletterConfig = field(default_factory=NewsletterConfig)
    
    # Custom fields (for extensibility)
    custom_metadata: Dict = field(default_factory=dict)


# ============================================================================
# PRE-BUILT TEMPLATES
# ============================================================================

class ConfigTemplates:
    """Pre-built configuration templates for popular niches"""
    
    @staticmethod
    def tech_startups() -> UniversalPodcastConfig:
        """Tech & Startups podcast"""
        return UniversalPodcastConfig(
            name="Tech Pulse",
            description="Latest in tech startups and innovation",
            podcast_type=PodcastType.TECH_STARTUPS,
            topics=["startups", "ai", "saas", "venture capital"],
            required_keywords=["startup", "tech", "ai", "funding"],
            sources=SourceConfig(
                subreddits=["technology", "startups", "programming", "SaaS", "artificialintelligence"],
                twitter_accounts=["TechCrunch", "VentureBeat", "TheVerge", "ProductHunt"],
                twitter_hashtags=["startups", "techstartup", "ai"],
                rss_feeds=[
                    {"url": "https://techcrunch.com/feed", "name": "TechCrunch"},
                    {"url": "https://www.theverge.com/rss/index.xml", "name": "The Verge"}
                ],
                youtube_channels=["UCIzBSS46vcqhwmBZ7ZpY-yg"]  # Y Combinator
            ),
            ai=AIConfig(
                tone=ToneStyle.ENTHUSIASTIC_ENERGETIC,
                audience=AudienceType.PROFESSIONALS
            )
        )
    
    @staticmethod
    def gaming() -> UniversalPodcastConfig:
        """Gaming & Esports podcast"""
        return UniversalPodcastConfig(
            name="Gaming Pulse",
            description="Your weekly dose of gaming news",
            podcast_type=PodcastType.GAMING_ESPORTS,
            topics=["gaming", "esports", "game releases", "streaming"],
            required_keywords=["game", "gaming", "esports", "console"],
            sources=SourceConfig(
                subreddits=["gaming", "Games", "pcgaming", "esports", "leagueoflegends"],
                twitter_accounts=["IGN", "GameSpot", "Kotaku", "Steam"],
                rss_feeds=[
                    {"url": "https://www.ign.com/feed", "name": "IGN"},
                    {"url": "https://www.polygon.com/rss/index.xml", "name": "Polygon"}
                ],
                youtube_channels=["UCKy1dAqELo0zrOtPkf0eTMw"]  # IGN
            ),
            ai=AIConfig(
                tone=ToneStyle.CASUAL_CONVERSATIONAL,
                audience=AudienceType.ENTHUSIASTS
            ),
            production=ProductionConfig(
                target_length_minutes=25
            )
        )
    
    @staticmethod
    def business_finance() -> UniversalPodcastConfig:
        """Business & Finance podcast"""
        return UniversalPodcastConfig(
            name="Market Movers",
            description="Daily business and market insights",
            podcast_type=PodcastType.BUSINESS_FINANCE,
            topics=["stocks", "markets", "economics", "business"],
            required_keywords=["market", "stock", "finance", "economy"],
            sources=SourceConfig(
                subreddits=["stocks", "investing", "CryptoCurrency", "economics"],
                twitter_accounts=["WSJ", "FT", "Bloomberg", "CNBC"],
                rss_feeds=[
                    {"url": "https://www.wsj.com/xml/rss/3_7085.xml", "name": "WSJ"},
                    {"url": "https://www.ft.com/?format=rss", "name": "Financial Times"}
                ]
            ),
            ai=AIConfig(
                tone=ToneStyle.PROFESSIONAL_ANALYTICAL,
                audience=AudienceType.PROFESSIONALS
            ),
            production=ProductionConfig(
                target_length_minutes=15,
                update_frequency="daily"
            )
        )
    
    @staticmethod
    def sports() -> UniversalPodcastConfig:
        """Sports podcast"""
        return UniversalPodcastConfig(
            name="Sports Roundup",
            description="Daily sports news and highlights",
            podcast_type=PodcastType.SPORTS,
            topics=["nba", "nfl", "soccer", "sports news"],
            required_keywords=["sport", "game", "team", "player"],
            sources=SourceConfig(
                subreddits=["sports", "nba", "nfl", "soccer"],
                twitter_accounts=["ESPN", "BleacherReport", "TheAthletic"],
                rss_feeds=[
                    {"url": "https://www.espn.com/espn/rss/news", "name": "ESPN"}
                ]
            ),
            ai=AIConfig(
                tone=ToneStyle.ENTHUSIASTIC_ENERGETIC,
                audience=AudienceType.ENTHUSIASTS
            ),
            production=ProductionConfig(
                target_length_minutes=20,
                update_frequency="daily"
            )
        )
    
    @staticmethod
    def science() -> UniversalPodcastConfig:
        """Science & Education podcast"""
        return UniversalPodcastConfig(
            name="Science Simplified",
            description="Making science accessible to everyone",
            podcast_type=PodcastType.SCIENCE_EDUCATION,
            topics=["space", "climate", "medicine", "discoveries"],
            required_keywords=["science", "research", "study", "discovery"],
            sources=SourceConfig(
                subreddits=["science", "space", "Futurology", "askscience"],
                twitter_accounts=["NASA", "ScienceNews", "nature", "NatGeo"],
                rss_feeds=[
                    {"url": "https://www.sciencedaily.com/rss/all.xml", "name": "Science Daily"},
                    {"url": "https://www.nasa.gov/rss/dyn/breaking_news.rss", "name": "NASA"}
                ]
            ),
            ai=AIConfig(
                tone=ToneStyle.EDUCATIONAL_ACCESSIBLE,
                audience=AudienceType.GENERAL_PUBLIC,
                use_thinking_mode=True  # Deep explanations
            ),
            production=ProductionConfig(
                target_length_minutes=25,
                update_frequency="weekly"
            )
        )
    
    @staticmethod
    def custom(
        name: str,
        description: str,
        topics: List[str],
        sources: Dict[str, List[str]]
    ) -> UniversalPodcastConfig:
        """
        Create custom podcast configuration
        
        Example:
            config = ConfigTemplates.custom(
                name="My Podcast",
                description="About custom topic",
                topics=["topic1", "topic2"],
                sources={
                    "reddit": ["subreddit1", "subreddit2"],
                    "twitter": ["account1", "account2"],
                    "rss": ["https://feed1.com/rss"]
                }
            )
        """
        return UniversalPodcastConfig(
            name=name,
            description=description,
            podcast_type=PodcastType.CUSTOM,
            topics=topics,
            sources=SourceConfig(
                subreddits=sources.get("reddit", []),
                twitter_accounts=sources.get("twitter", []),
                rss_feeds=[{"url": url, "name": url} for url in sources.get("rss", [])],
                youtube_channels=sources.get("youtube", [])
            )
        )


# ============================================================================
# CONFIGURATION MANAGER
# ============================================================================

class ConfigManager:
    """Manages podcast configurations"""
    
    @staticmethod
    def load_template(template_name: str) -> UniversalPodcastConfig:
        """Load a built-in template"""
        templates = {
            "tech": ConfigTemplates.tech_startups,
            "gaming": ConfigTemplates.gaming,
            "business": ConfigTemplates.business_finance,
            "sports": ConfigTemplates.sports,
            "science": ConfigTemplates.science
        }
        
        if template_name not in templates:
            raise ValueError(f"Unknown template: {template_name}. Available: {list(templates.keys())}")
        
        return templates[template_name]()
    
    @staticmethod
    def save_config(config: UniversalPodcastConfig, filepath: str):
        """Save configuration to YAML file"""
        import yaml
        from dataclasses import asdict
        
        # Convert enums to strings
        config_dict = asdict(config)
        config_dict['podcast_type'] = config.podcast_type.value
        config_dict['ai']['tone'] = config.ai.tone.value
        config_dict['ai']['audience'] = config.ai.audience.value
        
        with open(filepath, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False)
    
    @staticmethod
    def load_config(filepath: str) -> UniversalPodcastConfig:
        """Load configuration from YAML file"""
        import yaml
        
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        
        # Convert strings back to enums
        data['podcast_type'] = PodcastType(data['podcast_type'])
        data['ai']['tone'] = ToneStyle(data['ai']['tone'])
        data['ai']['audience'] = AudienceType(data['ai']['audience'])
        
        return UniversalPodcastConfig(**data)


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    # Example 1: Use built-in template
    print("Example 1: Tech Podcast")
    tech_config = ConfigTemplates.tech_startups()
    print(f"  Name: {tech_config.name}")
    print(f"  Type: {tech_config.podcast_type.value}")
    print(f"  Subreddits: {tech_config.sources.subreddits}")
    
    # Example 2: Custom podcast
    print("\nExample 2: Custom Podcast")
    custom_config = ConfigTemplates.custom(
        name="My Custom Pod",
        description="About whatever I want!",
        topics=["topic1", "topic2"],
        sources={
            "reddit": ["my_subreddit"],
            "twitter": ["my_account"],
            "rss": ["https://my-feed.com/rss"]
        }
    )
    print(f"  Name: {custom_config.name}")
    print(f"  Topics: {custom_config.topics}")
    
    # Example 3: Save/Load configuration
    print("\nExample 3: Save & Load")
    ConfigManager.save_config(tech_config, "/tmp/tech_config.yaml")
    loaded_config = ConfigManager.load_config("/tmp/tech_config.yaml")
    print(f"  Loaded: {loaded_config.name}")
