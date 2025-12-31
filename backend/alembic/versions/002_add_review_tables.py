"""add_review_tables

Revision ID: 002_add_review_tables
Revises: c3f7ba949ceb
Create Date: 2025-12-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_review_tables'
down_revision: Union[str, Sequence[str], None] = '001_add_feedback_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create review_sessions and review_comments tables."""
    
    # Create review_sessions table
    op.create_table('review_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('org', sa.String(length=255), nullable=False),
        sa.Column('repo', sa.String(length=255), nullable=False),
        sa.Column('pr_number', sa.Integer(), nullable=False),
        sa.Column('base_branch', sa.String(length=255), nullable=True, server_default='main'),
        sa.Column('head_sha', sa.String(length=64), nullable=True),
        sa.Column('files_reviewed', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_comments', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=True, server_default='pending'),
        sa.Column('github_review_id', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_review_sessions_session_id'), 'review_sessions', ['session_id'], unique=True)
    op.create_index(op.f('ix_review_sessions_org'), 'review_sessions', ['org'], unique=False)
    op.create_index(op.f('ix_review_sessions_repo'), 'review_sessions', ['repo'], unique=False)
    op.create_index(op.f('ix_review_sessions_pr_number'), 'review_sessions', ['pr_number'], unique=False)
    op.create_index('ix_review_session_pr_lookup', 'review_sessions', ['org', 'repo', 'pr_number'], unique=False)
    
    # Create review_comments table
    op.create_table('review_comments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('review_session_id', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('line', sa.Integer(), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=True),
        sa.Column('side', sa.String(length=8), nullable=True, server_default='RIGHT'),
        sa.Column('start_side', sa.String(length=8), nullable=True),
        sa.Column('title', sa.String(length=512), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=True, server_default='medium'),
        sa.Column('category', sa.String(length=32), nullable=True, server_default='other'),
        sa.Column('suggestion', sa.Text(), nullable=True),
        sa.Column('github_comment_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['review_session_id'], ['review_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_review_comments_review_session_id'), 'review_comments', ['review_session_id'], unique=False)
    op.create_index('ix_review_comment_file', 'review_comments', ['review_session_id', 'file_path'], unique=False)


def downgrade() -> None:
    """Drop review_sessions and review_comments tables."""
    
    # Drop review_comments table first (has FK to review_sessions)
    op.drop_index('ix_review_comment_file', table_name='review_comments')
    op.drop_index(op.f('ix_review_comments_review_session_id'), table_name='review_comments')
    op.drop_table('review_comments')
    
    # Drop review_sessions table
    op.drop_index('ix_review_session_pr_lookup', table_name='review_sessions')
    op.drop_index(op.f('ix_review_sessions_pr_number'), table_name='review_sessions')
    op.drop_index(op.f('ix_review_sessions_repo'), table_name='review_sessions')
    op.drop_index(op.f('ix_review_sessions_org'), table_name='review_sessions')
    op.drop_index(op.f('ix_review_sessions_session_id'), table_name='review_sessions')
    op.drop_table('review_sessions')
