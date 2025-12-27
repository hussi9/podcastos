"""
Database models for Podcast Production Webapp.
Uses SQLite with SQLAlchemy for easy migration to cloud later.
"""

import json
from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.pool import QueuePool

Base = declarative_base()


class PodcastProfile(Base):
    """A podcast profile with all its settings."""
    __tablename__ = 'podcast_profiles'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)

    # Target audience
    target_audience = Column(Text)

    # Tone and style settings
    tone = Column(String(50), default='conversational')  # conversational, formal, casual, educational
    language = Column(String(10), default='en-US')

    # Duration settings
    target_duration_minutes = Column(Integer, default=10)

    # Content settings
    topic_count = Column(Integer, default=5)
    categories = Column(JSON, default=list)  # List of categories to cover

    # Source configuration
    sources_config = Column(JSON, default=dict)  # Reddit subs, RSS feeds, etc.

    # Generation schedule
    schedule_enabled = Column(Boolean, default=False)  # Whether scheduling is active
    schedule_cron = Column(String(50))  # Cron expression for scheduling
    schedule_hour = Column(Integer, default=6)  # Hour to generate (0-23)
    schedule_minute = Column(Integer, default=0)  # Minute to generate (0-59)
    schedule_days = Column(JSON, default=lambda: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'])  # Days to run
    timezone = Column(String(50), default='America/New_York')
    last_scheduled_run = Column(DateTime)  # Track when last scheduled generation ran

    # Audio settings
    tts_model = Column(String(100), default='gemini-2.5-flash-preview-tts')

    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    hosts = relationship('Host', back_populates='profile', cascade='all, delete-orphan')
    episodes = relationship('Episode', back_populates='profile', cascade='all, delete-orphan')
    avoided_topics = relationship('TopicAvoidance', back_populates='profile', cascade='all, delete-orphan')
    sources = relationship('ContentSource', back_populates='profile', cascade='all, delete-orphan')
    newsletters = relationship('Newsletter', back_populates='profile', cascade='all, delete-orphan')
    
    # Normalized relationships (Future proofing)
    categories_rel = relationship('Category', secondary='profile_categories', back_populates='profiles')


class Category(Base):
    """Normalized category for better querying."""
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    slug = Column(String(50), unique=True, nullable=False)
    
    profiles = relationship('PodcastProfile', secondary='profile_categories', back_populates='categories_rel')


class ProfileCategory(Base):
    """Association table for Profile <-> Category."""
    __tablename__ = 'profile_categories'
    
    profile_id = Column(Integer, ForeignKey('podcast_profiles.id'), primary_key=True)
    category_id = Column(Integer, ForeignKey('categories.id'), primary_key=True)


class Host(Base):
    """Podcast host persona."""
    __tablename__ = 'hosts'
    __table_args__ = (
        Index('idx_host_profile', 'profile_id'),
    )

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('podcast_profiles.id'), nullable=False)

    name = Column(String(50), nullable=False)
    persona = Column(Text)  # Background, personality description
    voice_name = Column(String(50))  # TTS voice to use

    # Speaking style
    speaking_style = Column(Text)  # How they speak, their quirks
    expertise_areas = Column(JSON, default=list)  # What they know about

    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship('PodcastProfile', back_populates='hosts')


class Episode(Base):
    """Generated podcast episode."""
    __tablename__ = 'episodes'
    __table_args__ = (
        Index('idx_episode_profile', 'profile_id'),
        Index('idx_episode_date', 'date'),
        Index('idx_episode_status', 'status'),
        Index('idx_episode_profile_date', 'profile_id', 'date'),
    )

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('podcast_profiles.id'), nullable=False)

    episode_id = Column(String(50), unique=True, nullable=False)  # e.g., dd-20251213
    title = Column(String(200), nullable=False)
    date = Column(DateTime, nullable=False)

    # Content
    topics_covered = Column(JSON, default=list)  # List of topic titles
    script = Column(Text)  # Full dialogue script
    summary = Column(Text)  # Episode summary
    key_facts = Column(JSON, default=list)  # Key facts mentioned

    # Embeddings for similarity search (stored as JSON array)
    topic_embeddings = Column(JSON)  # Vector embeddings for topic continuity

    # Audio
    audio_path = Column(String(500))
    duration_seconds = Column(Integer)

    # Metadata
    sources_used = Column(JSON, default=list)
    generation_time_seconds = Column(Float)

    # Status
    status = Column(String(20), default='draft')  # draft, published, archived
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime)

    profile = relationship('PodcastProfile', back_populates='episodes')
    topics = relationship('TopicHistory', back_populates='episode', cascade='all, delete-orphan')
    segments = relationship('Segment', back_populates='episode', cascade='all, delete-orphan')
    newsletter = relationship('Newsletter', back_populates='episode', uselist=False, cascade='all, delete-orphan')


class Segment(Base):
    """Audio segment for an episode (enables interactive playback)."""
    __tablename__ = 'segments'
    __table_args__ = (
        Index('idx_segment_episode', 'episode_id'),
        Index('idx_segment_episode_seq', 'episode_id', 'sequence_index'),
    )

    id = Column(Integer, primary_key=True)
    episode_id = Column(Integer, ForeignKey('episodes.id'), nullable=False)

    # Ordering
    sequence_index = Column(Integer, nullable=False)  # 0, 1, 2...

    # Content Mapping
    topic_id = Column(String(50))  # generated from script
    title = Column(String(200))  # "Introduction", "H1B Update", etc.
    content_type = Column(String(20))  # "intro", "topic", "ad", "outro"

    # Audio
    audio_path = Column(String(500))
    duration_seconds = Column(Float)

    # Metadata
    transcript = Column(Text)

    episode = relationship('Episode', back_populates='segments')


class TopicHistory(Base):
    """Individual topics discussed in episodes (for avoiding repetition)."""
    __tablename__ = 'topic_history'
    __table_args__ = (
        Index('idx_topic_history_episode', 'episode_id'),
        Index('idx_topic_history_category', 'category'),
        Index('idx_topic_history_created', 'created_at'),
    )

    id = Column(Integer, primary_key=True)
    episode_id = Column(Integer, ForeignKey('episodes.id'), nullable=False)

    title = Column(String(200), nullable=False)
    category = Column(String(50))
    summary = Column(Text)

    # Key points discussed
    key_points = Column(JSON, default=list)
    facts_mentioned = Column(JSON, default=list)

    # Embedding for similarity search
    embedding = Column(JSON)  # Vector embedding

    # For tracking ongoing stories
    is_ongoing = Column(Boolean, default=False)  # Story continues in future episodes
    follow_up_notes = Column(Text)  # Notes for future coverage

    # Relevance scoring
    importance_score = Column(Float, default=0.5)
    discussion_depth = Column(String(20), default='medium')  # brief, medium, deep

    created_at = Column(DateTime, default=datetime.utcnow)

    episode = relationship('Episode', back_populates='topics')


class TopicAvoidance(Base):
    """Topics to avoid or de-prioritize."""
    __tablename__ = 'topic_avoidance'
    __table_args__ = (
        Index('idx_topic_avoid_profile', 'profile_id'),
        Index('idx_topic_avoid_active', 'profile_id', 'is_active'),
    )

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('podcast_profiles.id'), nullable=False)

    keyword = Column(String(100), nullable=False)
    reason = Column(Text)  # Why to avoid

    # Type of avoidance
    avoidance_type = Column(String(20), default='temporary')  # temporary, permanent, reduce_frequency

    # For temporary avoidance
    avoid_until = Column(DateTime)  # Don't cover until this date
    last_covered = Column(DateTime)  # When was it last discussed
    min_days_between = Column(Integer, default=7)  # Minimum days between coverage

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship('PodcastProfile', back_populates='avoided_topics')


class ContentSource(Base):
    """Content sources for a podcast profile."""
    __tablename__ = 'content_sources'
    __table_args__ = (
        Index('idx_content_source_profile', 'profile_id'),
        Index('idx_content_source_active', 'profile_id', 'is_active'),
        Index('idx_content_source_type', 'source_type'),
    )

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('podcast_profiles.id'), nullable=False)

    name = Column(String(100), nullable=False)
    source_type = Column(String(50), nullable=False)  # reddit, rss, google_news, api

    # Configuration
    config = Column(JSON, default=dict)  # URL, subreddit name, API key, etc.

    # Priority and weighting
    priority = Column(Integer, default=5)  # 1-10, higher = more important
    weight = Column(Float, default=1.0)  # Weight in content ranking

    # Categories this source covers
    categories = Column(JSON, default=list)

    is_active = Column(Boolean, default=True)
    last_fetched = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship('PodcastProfile', back_populates='sources')


class GenerationJob(Base):
    """Track podcast generation pipeline status."""
    __tablename__ = 'generation_jobs'
    __table_args__ = (
        Index('idx_job_profile', 'profile_id'),
        Index('idx_job_status', 'status'),
        Index('idx_job_created', 'created_at'),
        Index('idx_job_profile_status', 'profile_id', 'status'),
    )

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('podcast_profiles.id'), nullable=False)

    job_id = Column(String(50), unique=True, nullable=False)
    target_date = Column(DateTime, nullable=False)

    # Pipeline stages
    status = Column(String(20), default='pending')  # pending, running, completed, failed
    current_stage = Column(String(50))  # content_gathering, research, scripting, audio, etc.

    # Stage completion tracking
    stages_completed = Column(JSON, default=list)
    stages_pending = Column(JSON, default=list)

    # Progress
    progress_percent = Column(Integer, default=0)
    stage_details = Column(JSON, default=dict)  # Details for each stage

    # Job configuration (for recovery)
    options = Column(JSON, default=dict)  # Original job options for restart recovery
    
    # Results
    episode_id = Column(Integer, ForeignKey('episodes.id'))
    result_data = Column(JSON, default=dict)  # Final result data
    error_message = Column(Text)

    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Recovery support
    is_recoverable = Column(Boolean, default=True)  # Can this job be recovered on restart?
    last_checkpoint = Column(JSON, default=dict)  # Last known good state for recovery


class Newsletter(Base):
    """Generated newsletter for an episode."""
    __tablename__ = 'newsletters'
    __table_args__ = (
        Index('idx_newsletter_profile', 'profile_id'),
        Index('idx_newsletter_date', 'issue_date'),
    )

    id = Column(Integer, primary_key=True)
    episode_id = Column(Integer, ForeignKey('episodes.id'), nullable=False, unique=True)
    profile_id = Column(Integer, ForeignKey('podcast_profiles.id'), nullable=False)

    # Metadata
    title = Column(String(200))
    subtitle = Column(String(200))
    issue_date = Column(DateTime)
    
    # Content
    intro = Column(Text)
    outro = Column(Text)
    sections = Column(JSON, default=list) # List of section dicts
    
    # Formats
    markdown_content = Column(Text)
    html_content = Column(Text)
    
    # Stats
    total_word_count = Column(Integer)
    reading_time_minutes = Column(Integer)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    episode = relationship('Episode', back_populates='newsletter')
    profile = relationship('PodcastProfile', back_populates='newsletters')


class AppSettings(Base):
    """Global application settings."""
    __tablename__ = 'app_settings'

    id = Column(Integer, primary_key=True)

    # General settings
    theme = Column(String(20), default='system')  # light, dark, system
    language = Column(String(10), default='en')
    auto_save = Column(Boolean, default=True)
    show_tooltips = Column(Boolean, default=True)

    # Generation defaults
    default_duration = Column(Integer, default=15)  # minutes
    default_topics = Column(Integer, default=3)
    research_depth = Column(String(20), default='standard')  # quick, standard, deep
    ai_model = Column(String(50), default='gemini-pro')

    # Audio settings
    audio_quality = Column(String(20), default='high')  # standard, high, premium
    tts_provider = Column(String(30), default='google')  # google, elevenlabs, openai
    playback_speed = Column(Float, default=1.0)
    enable_background_music = Column(Boolean, default=False)

    # Notification settings
    enable_notifications = Column(Boolean, default=True)
    email_notifications = Column(Boolean, default=False)
    notification_email = Column(String(255))

    # Legacy key-value fields (for backward compatibility)
    key = Column(String(100))
    value = Column(Text)
    value_type = Column(String(20), default='string')
    description = Column(Text)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Database initialization
def init_db(db_path: str = 'podcast_studio.db'):
    """Initialize the database with connection pooling."""
    engine = create_engine(
        f'sqlite:///{db_path}',
        echo=False,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,  # Recycle connections after 30 minutes
        connect_args={'check_same_thread': False}  # Required for SQLite with threading
    )
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    """Get a database session."""
    Session = sessionmaker(bind=engine)
    return Session()
