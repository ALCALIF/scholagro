"""fix rider relationship

Revision ID: fix_rider_relationship
Revises: 134d16ded304
Create Date: 2025-11-16 15:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_rider_relationship'
down_revision = '134d16ded304'
branch_labels = None
depends_on = None

def upgrade():
    # Add rider_id column with a foreign key constraint
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rider_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_orders_rider_id',
            'riders',
            ['rider_id'],
            ['id'],
            ondelete='SET NULL'
        )


def downgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('fk_orders_rider_id', type_='foreignkey')
        batch_op.drop_column('rider_id')
