"""Add stripe_customer_id to users (guarded)

Revision ID: e1b2c3d4
Revises: aa23716e80c7
Create Date: 2025-11-26 19:21:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e1b2c3d4'
down_revision = 'aa23716e80c7'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    from sqlalchemy import inspect
    inspector = inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('users')}
    if 'stripe_customer_id' not in cols:
        op.add_column('users', sa.Column('stripe_customer_id', sa.String(length=255), nullable=True))


def downgrade():
    bind = op.get_bind()
    from sqlalchemy import inspect
    inspector = inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('users')}
    if 'stripe_customer_id' in cols:
        op.drop_column('users', 'stripe_customer_id')
