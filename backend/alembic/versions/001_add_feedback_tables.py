"""add feedback tables

Revision ID: 001_add_feedback_tables
Revises: 
Create Date: 2024-12-30 12:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_add_feedback_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create review_feedback table
    op.create_table(
        'review_feedback',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('comment_id', sa.String(64), nullable=False),
        sa.Column('review_session_id', sa.String(64), nullable=True),
        sa.Column('owner', sa.String(255), nullable=False),
        sa.Column('repo', sa.String(255), nullable=False),
        sa.Column('pr_number', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(512), nullable=True),
        sa.Column('line_number', sa.Integer(), nullable=True),
        sa.Column('ai_comment', sa.Text(), nullable=False),
        sa.Column('feedback_type', sa.String(32), nullable=False),
        sa.Column('reaction_type', sa.String(32), nullable=True),
        sa.Column('user_feedback', sa.Text(), nullable=True),
        sa.Column('github_user', sa.String(255), nullable=True),
        sa.Column('reaction_weight', sa.Float(), nullable=True, default=0.0),
        sa.Column('processed', sa.Boolean(), nullable=True, default=False),
        sa.Column('learning_id', sa.String(64), nullable=True),
        sa.Column('extracted_learning', sa.Text(), nullable=True),
        sa.Column('learning_category', sa.String(64), nullable=True),
        sa.Column('learning_type', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for review_feedback
    op.create_index('ix_review_feedback_comment_id', 'review_feedback', ['comment_id'])
    op.create_index('ix_review_feedback_review_session_id', 'review_feedback', ['review_session_id'])
    op.create_index('ix_review_feedback_owner', 'review_feedback', ['owner'])
    op.create_index('ix_review_feedback_repo', 'review_feedback', ['repo'])
    op.create_index('ix_review_feedback_pr_number', 'review_feedback', ['pr_number'])
    op.create_index('ix_review_feedback_feedback_type', 'review_feedback', ['feedback_type'])
    op.create_index('ix_review_feedback_github_user', 'review_feedback', ['github_user'])
    op.create_index('ix_review_feedback_processed', 'review_feedback', ['processed'])
    
    # Create kb_learnings table
    op.create_table(
        'kb_learnings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('kb_id', sa.String(64), nullable=True),
        sa.Column('scope', sa.String(32), nullable=True, default='repo'),
        sa.Column('owner', sa.String(255), nullable=True),
        sa.Column('repo', sa.String(255), nullable=True),
        sa.Column('learning', sa.Text(), nullable=False),
        sa.Column('category', sa.String(64), nullable=True),
        sa.Column('learning_type', sa.String(64), nullable=True),
        sa.Column('language', sa.String(64), nullable=True),
        sa.Column('file_pattern', sa.String(255), nullable=True),
        sa.Column('source_pr', sa.String(255), nullable=True),
        sa.Column('source_feedback_id', sa.Integer(), nullable=True),
        sa.Column('learnt_from', sa.String(255), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True, default=0.5),
        sa.Column('positive_reactions', sa.Integer(), nullable=True, default=0),
        sa.Column('negative_reactions', sa.Integer(), nullable=True, default=0),
        sa.Column('active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for kb_learnings
    op.create_index('ix_kb_learnings_kb_id', 'kb_learnings', ['kb_id'], unique=True)
    op.create_index('ix_kb_learnings_scope', 'kb_learnings', ['scope'])
    op.create_index('ix_kb_learnings_owner', 'kb_learnings', ['owner'])
    op.create_index('ix_kb_learnings_repo', 'kb_learnings', ['repo'])
    op.create_index('ix_kb_learnings_category', 'kb_learnings', ['category'])
    op.create_index('ix_kb_learnings_learning_type', 'kb_learnings', ['learning_type'])
    op.create_index('ix_kb_learnings_language', 'kb_learnings', ['language'])
    op.create_index('ix_kb_learnings_active', 'kb_learnings', ['active'])


def downgrade() -> None:
    # Drop kb_learnings indexes and table
    op.drop_index('ix_kb_learnings_active', 'kb_learnings')
    op.drop_index('ix_kb_learnings_language', 'kb_learnings')
    op.drop_index('ix_kb_learnings_learning_type', 'kb_learnings')
    op.drop_index('ix_kb_learnings_category', 'kb_learnings')
    op.drop_index('ix_kb_learnings_repo', 'kb_learnings')
    op.drop_index('ix_kb_learnings_owner', 'kb_learnings')
    op.drop_index('ix_kb_learnings_scope', 'kb_learnings')
    op.drop_index('ix_kb_learnings_kb_id', 'kb_learnings')
    op.drop_table('kb_learnings')
    
    # Drop review_feedback indexes and table
    op.drop_index('ix_review_feedback_processed', 'review_feedback')
    op.drop_index('ix_review_feedback_github_user', 'review_feedback')
    op.drop_index('ix_review_feedback_feedback_type', 'review_feedback')
    op.drop_index('ix_review_feedback_pr_number', 'review_feedback')
    op.drop_index('ix_review_feedback_repo', 'review_feedback')
    op.drop_index('ix_review_feedback_owner', 'review_feedback')
    op.drop_index('ix_review_feedback_review_session_id', 'review_feedback')
    op.drop_index('ix_review_feedback_comment_id', 'review_feedback')
    op.drop_table('review_feedback')
