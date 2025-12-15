"""
Initialize or migrate the database in development.

Usage from the repository root (PowerShell):

    & ./.venv/Scripts/Activate.ps1
    python -m scripts.init_db

This script will attempt to run alembic/flask-migrate `upgrade` to apply migrations.
If that fails (or migrations aren't present), it will fall back to `db.create_all()` so development can continue.
"""

import os
import sys
# Ensure repository root is importable so `from app import create_app` works
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.extensions import db
from sqlalchemy import inspect

print('Initializing DB...')
app = create_app()
print('Using DB URI:', app.config.get('SQLALCHEMY_DATABASE_URI'))

with app.app_context():
    try:
        # Pre-migration backup: export products before applying alembic migrations
        try:
            from .backup_products import main as backup_main
            print('Backing up products before running migrations...')
            backup_main()
        except Exception as be:
            print('Product backup failed or could not be created (continuing):', str(be))
        # try to apply migrations using Flask-Migrate
        from flask_migrate import upgrade
        print('Attempting to apply migrations (flask_migrate.upgrade)')
        upgrade(directory='migrations')
        print('Migrations applied successfully')
    except Exception as e:
        print('Failed to run migrations:', str(e))
        # Only fall back to db.create_all() if explicitly requested to avoid
        # creating tables that later make migrations fail with duplicate column errors.
        if os.getenv('FORCE_CREATE_ALL', 'false').lower() == 'true':
            print('FORCE_CREATE_ALL is set; falling back to db.create_all() for development only')
            db.create_all()
            print('Tables created via db.create_all()')
        else:
            print("Skipping db.create_all(). To force fallback create-all, set FORCE_CREATE_ALL='true' and run again.")
    finally:
        try:
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print('Database tables present:', tables)
            # If there are no application tables (only alembic_version), create the tables
            app_tables = [t for t in tables if t != 'alembic_version']
            if not app_tables:
                    # Only create tables if explicitly requested via environment variable to avoid
                    # accidental table creation in a DB that previously had migrations applied.
                    if os.getenv('FORCE_CREATE_ALL', 'false').lower() == 'true':
                        print('FORCE_CREATE_ALL is set; creating application tables via db.create_all()')
                        db.create_all()
                        print('Created application tables via db.create_all()')
                    else:
                        print('No application tables detected: NOT creating tables automatically.\n' \
                              "To force table creation for development only, set FORCE_CREATE_ALL='true' and re-run this script.")
        except Exception:
            print('Could not inspect database tables')

print('Initialization complete')
