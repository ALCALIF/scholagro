"""
Inspect the configured database, print table names, and optionally export products to JSON.

Usage (PowerShell):
    & ./.venv/Scripts/Activate.ps1
    python -m scripts.check_db_content

This script is read-only and will not modify the DB. It helps you verify whether products exist
in the configured database before running destructive operations.
"""

import json
import os
import sys
try:
    # python-dotenv may be installed; use it to find which .env was loaded
    import dotenv
except Exception:
    dotenv = None
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.extensions import db


def main():
    app = create_app()
    with app.app_context():
        # Diagnostics about env file & loaded DATABASE_URL
        env_path = os.path.join(ROOT, '.env')
        env_exists = os.path.exists(env_path)
        dotenv_found = None
        if dotenv is not None:
            try:
                dotenv_found = dotenv.find_dotenv()
            except Exception:
                dotenv_found = None
        print('Resolved .env path:', env_path)
        print('.env exists:', env_exists)
        print('python-dotenv find_dotenv():', dotenv_found)
        print('Environment variable DATABASE_URL (os.environ):', os.environ.get('DATABASE_URL'))
        from sqlalchemy import inspect
        insp = inspect(db.session.get_bind())
        tables = insp.get_table_names()
        print('DB URL (app.config.SQLALCHEMY_DATABASE_URI):', app.config.get('SQLALCHEMY_DATABASE_URI'))
        # Try to report the alembic revision stored in the database (if present)
        if 'alembic_version' in tables:
            try:
                from sqlalchemy import text
                ver = db.session.execute(text('SELECT version_num FROM alembic_version')).fetchone()
                print('Alembic revision in DB:', ver[0] if ver else None)
            except Exception as e:
                print('Could not read alembic_version:', e)
        print('Tables:', tables)
        if 'products' in tables:
            # Print a small sample and count via the ORM
            from app.models import Product
            prod_count = db.session.query(Product).count() or 0
            print('Product count:', prod_count)
            # Dump up to 10 products to json file for quick review
            rows = db.session.query(Product.id, Product.name, Product.slug, Product.image_url, Product.price).limit(10).all()
            sample = [dict(id=r[0], name=r[1], slug=r[2], image_url=r[3], price=str(r[4]) if r[4] is not None else None) for r in rows]
            print('Sample products (up to 10):')
            print(json.dumps(sample, indent=2, default=str))
            out = os.path.join(app.instance_path, 'products_backup_sample.json')
            try:
                os.makedirs(app.instance_path, exist_ok=True)
                with open(out, 'w', encoding='utf-8') as f:
                    json.dump(sample, f, ensure_ascii=False, indent=2)
                print('Wrote sample to', out)
            except Exception as e:
                print('Could not write sample to instance path:', e)
        else:
            print('`products` table not present in database.')


if __name__ == '__main__':
    main()
