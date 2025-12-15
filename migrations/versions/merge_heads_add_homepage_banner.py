"""
Merge multiple heads: merge add_homepage_banner_sort_order head with existing head
Revision ID: merge_heads_add_homepage_banner
Revises: 67e8364dc266, add_homepage_banner_sort_order
Create Date: 2025-11-29
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_heads_add_homepage_banner'
down_revision = ('67e8364dc266', 'add_homepage_banner_sort_order')
branch_labels = None
depends_on = None


def upgrade():
    # This migration merges multiple heads into a single lineage; no DB changes required.
    pass


def downgrade():
    # Downgrade can't split merged heads automatically; raise to avoid accidental downgrade
    raise NotImplementedError('Cannot downgrade a merge migration.')
