"""
Drop all application tables (development only).

USAGE (PowerShell):
  & ./.venv/Scripts/Activate.ps1
  python -m scripts.drop_app_tables_dev --confirm

This script will drop all application tables (except alembic_version by default),
and should be used only in local development. It requires --confirm to run.
"""

import argparse
import os
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.extensions import db


def main(argv=None):
    argv = argv or sys.argv[1:]
    p = argparse.ArgumentParser(description='Drop app tables (development only).')
    p.add_argument('--confirm', action='store_true', help='Confirm that you want to drop app tables')
    p.add_argument('--drop-alembic', action='store_true', help='Also drop alembic_version table (rare)')
    args = p.parse_args(argv)

    if not args.confirm:
        print("This will drop app tables: re-run with --confirm to proceed.")
        return

    app = create_app()
    with app.app_context():
        from sqlalchemy import inspect, text
        insp = inspect(db.engine)
        tables = insp.get_table_names()
        # Exclude alembic_version unless explicitly requested
        to_drop = [t for t in tables if t != 'alembic_version']
        if args.drop_alembic:
            to_drop = tables
        if not to_drop:
            print('No application tables to drop')
            return
        print('Dropping tables:', to_drop)
        try:
            dialect = db.engine.dialect.name
            with db.engine.begin() as conn:
                # Disable foreign key checks where supported (MySQL / SQLite)
                if dialect in ('mysql', 'mysql+pymysql'):
                    print('Disabling FOREIGN_KEY_CHECKS for MySQL before dropping tables')
                    conn.execute(text('SET FOREIGN_KEY_CHECKS = 0'))
                elif dialect == 'sqlite':
                    print('Disabling foreign key checks for SQLite before dropping tables')
                    conn.execute(text('PRAGMA foreign_keys = OFF'))
                for t in to_drop:
                    print('Dropping', t)
                    if dialect in ('postgresql', 'pg8000', 'psycopg2'):
                        # Use CASCADE for Postgres
                        conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
                    else:
                        conn.execute(text(f'DROP TABLE IF EXISTS `{t}`'))
                # Re-enable FK checks
                if dialect in ('mysql', 'mysql+pymysql'):
                    conn.execute(text('SET FOREIGN_KEY_CHECKS = 1'))
                elif dialect == 'sqlite':
                    conn.execute(text('PRAGMA foreign_keys = ON'))
            print('Dropped tables successfully')
        except Exception as e:
            print('Error dropping tables:', e)


if __name__ == '__main__':
    main()
