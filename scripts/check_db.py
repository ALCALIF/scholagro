import os
import sys
# Ensure repository root is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from app import create_app
from app.extensions import db
from sqlalchemy import text
from app.models import Product
from sqlalchemy import inspect

def main():
    app = create_app()
    with app.app_context():
        engine = db.session.get_bind()
        print('DB URL:', app.config['SQLALCHEMY_DATABASE_URI'])
        insp = inspect(engine)
        tables = insp.get_table_names()
        print('Tables in DB:', tables)
        if 'products' in tables:
            try:
                # Use ORM to count rows to avoid textual SQL parsing errors in SQLAlchemy 2.x
                from sqlalchemy import func
                res = db.session.query(func.count(Product.id)).scalar()
                print('Products count:', res)
            except Exception:
                try:
                    res = db.session.execute(text('SELECT COUNT(*) FROM products')).fetchone()
                    print('Products count:', res[0])
                except Exception:
                    print('Could not count products')
        else:
            print('Products table not found')

if __name__ == '__main__':
    main()
