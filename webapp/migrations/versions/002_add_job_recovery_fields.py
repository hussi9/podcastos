"""Add job recovery fields

Revision ID: 002_job_recovery
Revises: 001_initial
Create Date: 2024-12-27

Adds fields to GenerationJob for better job state persistence and recovery.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '002_job_recovery'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add job recovery fields."""
    # Check if columns already exist (SQLite compatibility)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('generation_jobs')]
    
    # Add options column
    if 'options' not in existing_columns:
        op.add_column('generation_jobs', sa.Column('options', sa.JSON(), nullable=True))
    
    # Add result_data column
    if 'result_data' not in existing_columns:
        op.add_column('generation_jobs', sa.Column('result_data', sa.JSON(), nullable=True))
    
    # Add is_recoverable column
    if 'is_recoverable' not in existing_columns:
        op.add_column('generation_jobs', sa.Column('is_recoverable', sa.Boolean(), default=True))
    
    # Add last_checkpoint column
    if 'last_checkpoint' not in existing_columns:
        op.add_column('generation_jobs', sa.Column('last_checkpoint', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove job recovery fields."""
    op.drop_column('generation_jobs', 'last_checkpoint')
    op.drop_column('generation_jobs', 'is_recoverable')
    op.drop_column('generation_jobs', 'result_data')
    op.drop_column('generation_jobs', 'options')
