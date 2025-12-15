"""resize delivery_time_slot to 128 chars

Revision ID: 20251207_resize_delivery_time_slot
Revises: 
Create Date: 2025-12-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251207_resize_delivery_time_slot'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Increase delivery_time_slot column length to 128
    with op.batch_alter_table('orders') as batch_op:
        batch_op.alter_column('delivery_time_slot', type_=sa.String(length=128), existing_type=sa.String(length=32), existing_nullable=True)


def downgrade():
    # Revert delivery_time_slot column length back to 32
    with op.batch_alter_table('orders') as batch_op:
        batch_op.alter_column('delivery_time_slot', type_=sa.String(length=32), existing_type=sa.String(length=128), existing_nullable=True)
