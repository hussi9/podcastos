"""
Configuration settings for Desi Podcast Engine
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Google Gemini
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")

    # ElevenLabs
    elevenlabs_api_key: str = Field(..., env="ELEVENLABS_API_KEY")
    elevenlabs_voice_1: str = Field(
        default="pNInz6obpgDQGcFmaJgB", env="ELEVENLABS_VOICE_1"
    )  # Male host
    elevenlabs_voice_2: str = Field(
        default="EXAVITQu4vr4xnSDxMaL", env="ELEVENLABS_VOICE_2"
    )  # Female host

    # Reddit API
    reddit_client_id: Optional[str] = Field(default=None, env="REDDIT_CLIENT_ID")
    reddit_client_secret: Optional[str] = Field(default=None, env="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(default="DesiPodcastBot/1.0", env="REDDIT_USER_AGENT")

    # Supabase
    supabase_url: Optional[str] = Field(default=None, env="SUPABASE_URL")
    supabase_service_key: Optional[str] = Field(default=None, env="SUPABASE_SERVICE_KEY")

    # AWS S3
    aws_access_key_id: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    aws_s3_bucket: str = Field(default="desi-podcast-episodes", env="AWS_S3_BUCKET")
    aws_region: str = Field(default="us-east-1", env="AWS_REGION")

    # Podcast Settings
    podcast_name: str = Field(default="Desi Daily", env="PODCAST_NAME")
    podcast_tagline: str = Field(
        default="Your daily dose of news and insights for the South Asian community in America",
        env="PODCAST_TAGLINE",
    )
    episode_length_minutes: int = Field(default=12, env="EPISODE_LENGTH_MINUTES")
    generation_hour: int = Field(default=6, env="GENERATION_HOUR")
    timezone: str = Field(default="America/New_York", env="TIMEZONE")

    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    debug: bool = Field(default=False, env="DEBUG")

    # Paths
    output_dir: str = Field(default="output", env="OUTPUT_DIR")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Host personas for the podcast
HOST_PERSONAS = {
    "raj": {
        "name": "Raj",
        "voice_id_key": "elevenlabs_voice_1",
        "personality": """You are Raj, a pragmatic and informative co-host. You're a tech professional
        who immigrated to the US 10 years ago. You focus on practical advice, facts, and actionable
        insights. You have deep knowledge about visa processes, career growth, and navigating
        corporate America as a South Asian. Your tone is warm but direct.""",
    },
    "priya": {
        "name": "Priya",
        "voice_id_key": "elevenlabs_voice_2",
        "personality": """You are Priya, an empathetic and community-focused co-host. You're a
        second-generation Indian-American who works in community organizing. You bring cultural
        context, emotional intelligence, and community perspectives. You often share relatable
        stories and focus on the human side of issues. Your tone is warm, engaging, and inclusive.""",
    },
}

# Content sources configuration
CONTENT_SOURCES = {
    "reddit": {
        "subreddits": [
            "ABCDesis",
            "indian",
            "h1b",
            "immigration",
            "USCIS",
            "f1visa",
            "greencard",
        ],
        "post_limit": 25,
        "time_filter": "day",
    },
    "rss_feeds": {
        "uscis": "https://www.uscis.gov/rss/news",
        "state_dept": "https://travel.state.gov/content/travel/en/News/rss-feeds.html",
    },
    "news_categories": [
        "immigration",
        "h1b visa",
        "green card",
        "indian american",
        "south asian",
        "desi community",
        "tech layoffs",
    ],
}

# Topic categories for the podcast
TOPIC_CATEGORIES = [
    {
        "id": "immigration",
        "name": "Immigration & Visas",
        "keywords": ["h1b", "green card", "visa", "uscis", "i-140", "i-485", "priority date"],
        "priority": 1,
    },
    {
        "id": "career",
        "name": "Career & Professional",
        "keywords": ["job", "layoff", "interview", "promotion", "salary", "tech", "startup"],
        "priority": 2,
    },
    {
        "id": "community",
        "name": "Community & Culture",
        "keywords": ["diwali", "temple", "wedding", "festival", "discrimination", "identity"],
        "priority": 3,
    },
    {
        "id": "finance",
        "name": "Finance & Money",
        "keywords": ["tax", "investment", "remittance", "property", "401k", "h1b tax"],
        "priority": 4,
    },
    {
        "id": "family",
        "name": "Family & Relationships",
        "keywords": ["parents", "marriage", "kids", "education", "elder care", "visiting"],
        "priority": 5,
    },
]


def get_settings() -> Settings:
    """Get application settings singleton"""
    return Settings()
