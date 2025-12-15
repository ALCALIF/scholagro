"""merge multiple heads into a single head

Revision ID: merge_all_heads_20251207
Revises: 
Create Date: 2025-12-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_all_heads_20251207'
down_revision = ('20251207_resize_delivery_time_slot', 'flash_sale_orig_price', 'add_product_flags')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge-only migration to unify multiple heads. No DB changes.
    pass


def downgrade():
    # Downgrade not supported for merge-only migration
    pass
