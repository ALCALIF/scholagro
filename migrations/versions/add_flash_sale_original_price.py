"""add original_price field to flash_sales table

Revision ID: flash_sale_orig_price
Revises: 
Create Date: 2025-12-07 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'flash_sale_orig_price'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add original_price column to flash_sales if it doesn't exist
    with op.batch_alter_table('flash_sales', schema=None) as batch_op:
        batch_op.add_column(sa.Column('original_price', sa.Numeric(precision=10, scale=2), nullable=True))


def downgrade():
    # Remove original_price column from flash_sales
    with op.batch_alter_table('flash_sales', schema=None) as batch_op:
        batch_op.drop_column('original_price')
