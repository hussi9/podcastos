"""
Database Service for PodcastOS.

Uses Supabase for:
- User authentication
- Storing shows, episodes, subscribers
- Persisting user settings
"""

import os
import logging
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)


# Supabase client singleton
_supabase_client: Optional[Client] = None


def get_supabase() -> Client:
    """Get or create Supabase client."""
    global _supabase_client

    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")

        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

        _supabase_client = create_client(url, key)
        logger.info(f"Connected to Supabase: {url}")

    return _supabase_client


# ============== Models ==============

class UserProfile(BaseModel):
    """User profile stored in database."""
    id: str
    email: str
    full_name: Optional[str] = None
    brand_name: Optional[str] = None
    voice_config: Optional[dict] = None
    created_at: Optional[datetime] = None
    subscription_tier: str = "free"
    episodes_this_month: int = 0


class Show(BaseModel):
    """Podcast show."""
    id: Optional[str] = None
    user_id: str
    name: str
    description: Optional[str] = None
    voice_config: Optional[dict] = None
    rss_feed_id: Optional[str] = None
    created_at: Optional[datetime] = None


class Episode(BaseModel):
    """Generated episode."""
    id: Optional[str] = None
    show_id: str
    user_id: str
    title: str
    topic: Optional[str] = None
    audio_url: Optional[str] = None
    newsletter_url: Optional[str] = None
    duration_seconds: int = 0
    word_count: int = 0
    status: str = "pending"
    created_at: Optional[datetime] = None


class Subscriber(BaseModel):
    """Newsletter subscriber."""
    id: Optional[str] = None
    user_id: str
    email: str
    name: Optional[str] = None
    subscribed_at: Optional[datetime] = None


# ============== Database Operations ==============

class Database:
    """Database operations for PodcastOS."""

    def __init__(self):
        self.client = get_supabase()

    # === User Profiles ===

    async def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile by ID."""
        try:
            result = self.client.table("profiles").select("*").eq("id", user_id).single().execute()
            if result.data:
                return UserProfile(**result.data)
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
        return None

    async def create_user_profile(self, profile: UserProfile) -> Optional[UserProfile]:
        """Create a new user profile."""
        try:
            result = self.client.table("profiles").insert(profile.model_dump(exclude_none=True)).execute()
            if result.data:
                return UserProfile(**result.data[0])
        except Exception as e:
            logger.error(f"Error creating user profile: {e}")
        return None

    async def update_user_profile(self, user_id: str, updates: dict) -> bool:
        """Update user profile."""
        try:
            self.client.table("profiles").update(updates).eq("id", user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
        return False

    # === Shows ===

    async def create_show(self, show: Show) -> Optional[Show]:
        """Create a new show."""
        try:
            result = self.client.table("shows").insert(show.model_dump(exclude_none=True)).execute()
            if result.data:
                return Show(**result.data[0])
        except Exception as e:
            logger.error(f"Error creating show: {e}")
        return None

    async def get_user_shows(self, user_id: str) -> List[Show]:
        """Get all shows for a user."""
        try:
            result = self.client.table("shows").select("*").eq("user_id", user_id).execute()
            return [Show(**s) for s in result.data]
        except Exception as e:
            logger.error(f"Error getting user shows: {e}")
        return []

    async def get_show(self, show_id: str) -> Optional[Show]:
        """Get show by ID."""
        try:
            result = self.client.table("shows").select("*").eq("id", show_id).single().execute()
            if result.data:
                return Show(**result.data)
        except Exception as e:
            logger.error(f"Error getting show: {e}")
        return None

    # === Episodes ===

    async def create_episode(self, episode: Episode) -> Optional[Episode]:
        """Create a new episode."""
        try:
            result = self.client.table("episodes").insert(episode.model_dump(exclude_none=True)).execute()
            if result.data:
                return Episode(**result.data[0])
        except Exception as e:
            logger.error(f"Error creating episode: {e}")
        return None

    async def get_show_episodes(self, show_id: str) -> List[Episode]:
        """Get all episodes for a show."""
        try:
            result = self.client.table("episodes").select("*").eq("show_id", show_id).order("created_at", desc=True).execute()
            return [Episode(**e) for e in result.data]
        except Exception as e:
            logger.error(f"Error getting show episodes: {e}")
        return []

    async def get_user_episodes(self, user_id: str, limit: int = 20) -> List[Episode]:
        """Get recent episodes for a user."""
        try:
            result = self.client.table("episodes").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
            return [Episode(**e) for e in result.data]
        except Exception as e:
            logger.error(f"Error getting user episodes: {e}")
        return []

    async def update_episode(self, episode_id: str, updates: dict) -> bool:
        """Update an episode."""
        try:
            self.client.table("episodes").update(updates).eq("id", episode_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating episode: {e}")
        return False

    # === Subscribers ===

    async def add_subscriber(self, subscriber: Subscriber) -> Optional[Subscriber]:
        """Add a newsletter subscriber."""
        try:
            result = self.client.table("subscribers").insert(subscriber.model_dump(exclude_none=True)).execute()
            if result.data:
                return Subscriber(**result.data[0])
        except Exception as e:
            logger.error(f"Error adding subscriber: {e}")
        return None

    async def get_user_subscribers(self, user_id: str) -> List[Subscriber]:
        """Get all subscribers for a user."""
        try:
            result = self.client.table("subscribers").select("*").eq("user_id", user_id).execute()
            return [Subscriber(**s) for s in result.data]
        except Exception as e:
            logger.error(f"Error getting subscribers: {e}")
        return []

    async def remove_subscriber(self, user_id: str, email: str) -> bool:
        """Remove a subscriber."""
        try:
            self.client.table("subscribers").delete().eq("user_id", user_id).eq("email", email).execute()
            return True
        except Exception as e:
            logger.error(f"Error removing subscriber: {e}")
        return False

    # === Usage Tracking ===

    async def increment_episode_count(self, user_id: str) -> bool:
        """Increment user's episode count for the month."""
        try:
            # Get current count
            profile = await self.get_user_profile(user_id)
            if profile:
                new_count = profile.episodes_this_month + 1
                return await self.update_user_profile(user_id, {"episodes_this_month": new_count})
        except Exception as e:
            logger.error(f"Error incrementing episode count: {e}")
        return False

    async def reset_monthly_counts(self) -> bool:
        """Reset all users' monthly episode counts (run on 1st of month)."""
        try:
            self.client.table("profiles").update({"episodes_this_month": 0}).execute()
            return True
        except Exception as e:
            logger.error(f"Error resetting monthly counts: {e}")
        return False


# ============== Schema Setup ==============

SCHEMA_SQL = """
-- Profiles table (extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    brand_name TEXT,
    voice_config JSONB DEFAULT '{}',
    subscription_tier TEXT DEFAULT 'free',
    episodes_this_month INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Shows table
CREATE TABLE IF NOT EXISTS shows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    voice_config JSONB DEFAULT '{}',
    rss_feed_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Episodes table
CREATE TABLE IF NOT EXISTS episodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    show_id UUID REFERENCES shows(id) ON DELETE CASCADE,
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    topic TEXT,
    audio_url TEXT,
    newsletter_url TEXT,
    duration_seconds INTEGER DEFAULT 0,
    word_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Subscribers table
CREATE TABLE IF NOT EXISTS subscribers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    name TEXT,
    subscribed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, email)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_shows_user_id ON shows(user_id);
CREATE INDEX IF NOT EXISTS idx_episodes_show_id ON episodes(show_id);
CREATE INDEX IF NOT EXISTS idx_episodes_user_id ON episodes(user_id);
CREATE INDEX IF NOT EXISTS idx_subscribers_user_id ON subscribers(user_id);

-- Enable RLS
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE shows ENABLE ROW LEVEL SECURITY;
ALTER TABLE episodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY IF NOT EXISTS "Users can view own profile" ON profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY IF NOT EXISTS "Users can update own profile" ON profiles FOR UPDATE USING (auth.uid() = id);

CREATE POLICY IF NOT EXISTS "Users can view own shows" ON shows FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY IF NOT EXISTS "Users can create own shows" ON shows FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY IF NOT EXISTS "Users can update own shows" ON shows FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY IF NOT EXISTS "Users can delete own shows" ON shows FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY IF NOT EXISTS "Users can view own episodes" ON episodes FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY IF NOT EXISTS "Users can create own episodes" ON episodes FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY IF NOT EXISTS "Users can update own episodes" ON episodes FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY IF NOT EXISTS "Users can view own subscribers" ON subscribers FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY IF NOT EXISTS "Users can manage own subscribers" ON subscribers FOR ALL USING (auth.uid() = user_id);

-- Function to auto-create profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (NEW.id, NEW.email, NEW.raw_user_meta_data->>'full_name');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger for auto-creating profile
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
"""


def get_schema_sql() -> str:
    """Return the SQL schema for setup."""
    return SCHEMA_SQL


# Convenience instance
db = Database()
