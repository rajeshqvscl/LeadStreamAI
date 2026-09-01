"""Add draft_signature_id column to leads_raw table."""

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('leads_raw', sa.Column('draft_signature_id', sa.INTEGER(), nullable=True))


def downgrade():
    op.drop_column('leads_raw', 'draft_signature_id')
