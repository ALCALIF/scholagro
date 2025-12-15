import os
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        res = db.session.execute(text('SELECT * FROM alembic_version')).fetchall()
        print('alembic_version table content:')
        print(res)
    except Exception as e:
        print('Error querying alembic_version:', e)
