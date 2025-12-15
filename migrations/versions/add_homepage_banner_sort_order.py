"""
add sort_order to homepage_banners
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_homepage_banner_sort_order'
down_revision = '134d16ded304'
branch_labels = None
depends_on = None


def upgrade():
    # Use inspector to avoid trying to add the column if it already exists
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'homepage_banners' in insp.get_table_names():
        cols = [c['name'] for c in insp.get_columns('homepage_banners')]
        if 'sort_order' not in cols:
            op.add_column('homepage_banners', sa.Column('sort_order', sa.Integer(), nullable=True, server_default='0'))
    # ensure column has default 0 and set non-nullable
    try:
        op.execute('UPDATE homepage_banners SET sort_order = 0 WHERE sort_order IS NULL')
    except Exception:
        # if the column was not added due to existing or other DB state, ignore
        pass
    with op.batch_alter_table('homepage_banners') as batch_op:
        batch_op.alter_column('sort_order', existing_type=sa.Integer(), nullable=False, server_default=None)


def downgrade():
    with op.batch_alter_table('homepage_banners') as batch_op:
        batch_op.drop_column('sort_order')
