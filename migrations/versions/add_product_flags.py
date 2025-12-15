"""
Add product flags for Top Picks and New Arrivals
Revision ID: add_product_flags
Revises: merge_heads_add_homepage_banner
Create Date: 2025-12-01
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_product_flags'
down_revision = 'merge_heads_add_homepage_banner'
branch_labels = None
depends_on = None


def upgrade():
    # Add admin flags to products
    op.add_column('products', sa.Column('is_top_pick', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('products', sa.Column('is_new_arrival_featured', sa.Boolean(), nullable=False, server_default=sa.false()))
    # Set default to False in SQLAlchemy models explicitly (no runtime change required)
    # After adding columns, remove server default to clean schema if desired
    op.alter_column('products', 'is_top_pick', server_default=None)
    op.alter_column('products', 'is_new_arrival_featured', server_default=None)


def downgrade():
    # Remove columns in downgrade
    op.drop_column('products', 'is_new_arrival_featured')
    op.drop_column('products', 'is_top_pick')

