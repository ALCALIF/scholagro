"""
Print details about the configured DB and optionally run migrations / re-import data.

Usage (PowerShell):
  & ./.venv/Scripts/Activate.ps1
  python -m scripts.print_db_state [--upgrade] [--import path/to/file.json] [--confirm]

Notes:
 - `--upgrade` will attempt to run `flask_migrate.upgrade`.
 - `--import` will import the specified JSON file using the existing import script.
 - For safety, both actions require `--confirm` to actually perform them.
"""

import argparse
import json
import os
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.extensions import db


def print_state(app):
    from sqlalchemy import inspect, text
    print('Resolved .env path:', os.path.join(ROOT, '.env'))
    print('.env exists:', os.path.exists(os.path.join(ROOT, '.env')))
    print('Environment variable DATABASE_URL (os.environ):', os.environ.get('DATABASE_URL'))
    print('DB URL (app.config.SQLALCHEMY_DATABASE_URI):', app.config.get('SQLALCHEMY_DATABASE_URI'))
    with app.app_context():
        engine = db.session.get_bind()
        insp = inspect(engine)
        tables = insp.get_table_names()
        print('Tables present:', tables)
        if 'alembic_version' in tables:
            try:
                ver = db.session.execute(text('SELECT version_num FROM alembic_version')).fetchone()
                print('Alembic version in DB:', ver[0] if ver else None)
            except Exception as e:
                print('Could not read alembic_version:', e)
        try:
            # Try to get server version (works for many DBs)
            try:
                res = db.session.execute(text('SELECT VERSION()')).fetchone()
                print('DB server version string:', res[0] if res else None)
            except Exception:
                # Fallback to driver-inspected server version if available
                sv = getattr(db.engine.dialect, 'server_version_info', None)
                print('DB server_version_info:', sv)
        except Exception as e:
            print('Could not determine DB server version:', e)


def main(argv=None):
    argv = argv or sys.argv[1:]
    p = argparse.ArgumentParser(description='Print DB state and optionally run migrations / import')
    p.add_argument('--upgrade', action='store_true', help='Run flask_migrate.upgrade (requires --confirm)')
    p.add_argument('--import', dest='import_path', help='Path to products JSON to import after upgrade (requires --confirm)')
    p.add_argument('--confirm', action='store_true', help='Confirm that you want to run destructive actions')
    p.add_argument('--repair', action='store_true', help='If DB is inconsistent (alembic present but no app tables), stamp base and re-run migrations (requires --confirm)')
    args = p.parse_args(argv)

    app = create_app()
    print_state(app)

    if args.upgrade or args.import_path:
        if not args.confirm:
            print('\nWARNING: You requested operations that change the DB state, but did not pass --confirm. No changes will be made. Re-run with --confirm to proceed.')
            return
    with app.app_context():
        if args.upgrade:
            # Run flask-migrate upgrade safely
            try:
                from flask_migrate import upgrade
                print('\nRunning migrations (flask_migrate.upgrade)')
                upgrade(directory='migrations')
                print('Migrations applied successfully')
            except Exception as e:
                print('Failed to apply migrations:', e)
        # If repair requested, and there are no app tables but alembic present: stamp base, then upgrade
        if args.repair:
            from sqlalchemy import inspect
            insp = inspect(db.session.get_bind())
            tables = insp.get_table_names()
            app_tables = [t for t in tables if t != 'alembic_version']
            if 'alembic_version' in tables and not app_tables:
                if not args.confirm:
                    print('\nWARNING: repair requested but not confirmed. Add --confirm to perform repair.')
                else:
                    try:
                        # Try to use flask_migrate.stamp & upgrade if available
                        try:
                            from flask_migrate import stamp
                            print('\nStamping DB to base and applying migrations (flask_migrate.stamp)')
                            stamp(revision='base', directory='migrations')
                        except Exception:
                            # Fallback to CLI stamp
                            import subprocess
                            print('\nUsing CLI fallback to stamp DB to base')
                            subprocess.check_call([sys.executable, '-m', 'flask', 'db', 'stamp', 'base'])
                        # Now upgrade
                        from flask_migrate import upgrade as fm_upgrade
                        print('Running migrations (flask_migrate.upgrade)')
                        fm_upgrade(directory='migrations')
                        print('Repair completed: migrations applied')
                    except Exception as e:
                        print('Repair failed:', e)
            else:
                print('Repair not required or DB has app tables present; skipping stamp/upgrade')
        if args.import_path:
            if not os.path.exists(args.import_path):
                print('Import file not found:', args.import_path)
            else:
                try:
                    from .import_products import main as import_main
                    print('\nImporting products from', args.import_path)
                    import_main([args.import_path])
                except Exception as e:
                    print('Import failed:', e)


if __name__ == '__main__':
    main()
