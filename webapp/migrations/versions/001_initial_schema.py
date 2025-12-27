"""Initial schema - baseline from existing database

Revision ID: 001_initial
Revises: None
Create Date: 2024-12-27

This migration represents the initial database schema.
It serves as a baseline for future migrations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial schema.
    
    Note: This migration is a baseline. If the tables already exist,
    the operations will be skipped.
    """
    # Use batch mode for SQLite compatibility
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # PodcastProfile table
    if 'podcast_profiles' not in existing_tables:
        op.create_table(
            'podcast_profiles',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('target_audience', sa.String(length=200), nullable=True),
            sa.Column('tone', sa.String(length=50), nullable=True),
            sa.Column('language', sa.String(length=10), nullable=True),
            sa.Column('target_duration_minutes', sa.Integer(), nullable=True),
            sa.Column('topic_count', sa.Integer(), nullable=True),
            sa.Column('categories', sa.JSON(), nullable=True),
            sa.Column('schedule_enabled', sa.Boolean(), nullable=True),
            sa.Column('schedule_hour', sa.Integer(), nullable=True),
            sa.Column('schedule_minute', sa.Integer(), nullable=True),
            sa.Column('schedule_days', sa.JSON(), nullable=True),
            sa.Column('timezone', sa.String(length=50), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
    
    # Host table
    if 'hosts' not in existing_tables:
        op.create_table(
            'hosts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('profile_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('voice_id', sa.String(length=100), nullable=True),
            sa.Column('personality', sa.Text(), nullable=True),
            sa.Column('is_primary', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['profile_id'], ['podcast_profiles.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
    
    # Episode table
    if 'episodes' not in existing_tables:
        op.create_table(
            'episodes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('profile_id', sa.Integer(), nullable=False),
            sa.Column('episode_id', sa.String(length=50), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('date', sa.DateTime(), nullable=True),
            sa.Column('script', sa.Text(), nullable=True),
            sa.Column('audio_path', sa.String(length=500), nullable=True),
            sa.Column('duration_seconds', sa.Integer(), nullable=True),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('topics_covered', sa.JSON(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['profile_id'], ['podcast_profiles.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('episode_id')
        )
    
    # GenerationJob table
    if 'generation_jobs' not in existing_tables:
        op.create_table(
            'generation_jobs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('profile_id', sa.Integer(), nullable=False),
            sa.Column('job_id', sa.String(length=50), nullable=False),
            sa.Column('target_date', sa.DateTime(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('current_stage', sa.String(length=50), nullable=True),
            sa.Column('progress_percent', sa.Integer(), nullable=True),
            sa.Column('stages_completed', sa.JSON(), nullable=True),
            sa.Column('stages_pending', sa.JSON(), nullable=True),
            sa.Column('stage_details', sa.JSON(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('episode_id', sa.Integer(), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['profile_id'], ['podcast_profiles.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('job_id')
        )
    
    # ContentSource table
    if 'content_sources' not in existing_tables:
        op.create_table(
            'content_sources',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('profile_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('source_type', sa.String(length=50), nullable=False),
            sa.Column('config', sa.JSON(), nullable=True),
            sa.Column('priority', sa.Integer(), nullable=True),
            sa.Column('categories', sa.JSON(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['profile_id'], ['podcast_profiles.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
    
    # Newsletter table
    if 'newsletters' not in existing_tables:
        op.create_table(
            'newsletters',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('episode_id', sa.Integer(), nullable=True),
            sa.Column('profile_id', sa.Integer(), nullable=True),
            sa.Column('title', sa.String(length=200), nullable=True),
            sa.Column('subtitle', sa.String(length=300), nullable=True),
            sa.Column('issue_date', sa.DateTime(), nullable=True),
            sa.Column('intro', sa.Text(), nullable=True),
            sa.Column('outro', sa.Text(), nullable=True),
            sa.Column('sections', sa.JSON(), nullable=True),
            sa.Column('markdown_content', sa.Text(), nullable=True),
            sa.Column('html_content', sa.Text(), nullable=True),
            sa.Column('total_word_count', sa.Integer(), nullable=True),
            sa.Column('reading_time_minutes', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['episode_id'], ['episodes.id'], ),
            sa.ForeignKeyConstraint(['profile_id'], ['podcast_profiles.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
    
    # Create indexes
    try:
        op.create_index('ix_episodes_profile_id', 'episodes', ['profile_id'])
        op.create_index('ix_episodes_status', 'episodes', ['status'])
        op.create_index('ix_generation_jobs_profile_id', 'generation_jobs', ['profile_id'])
        op.create_index('ix_generation_jobs_status', 'generation_jobs', ['status'])
    except Exception:
        pass  # Indexes may already exist


def downgrade() -> None:
    """Drop all tables (use with caution!)."""
    op.drop_table('newsletters')
    op.drop_table('content_sources')
    op.drop_table('generation_jobs')
    op.drop_table('episodes')
    op.drop_table('hosts')
    op.drop_table('podcast_profiles')
