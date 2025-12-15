"""
Reset or create an admin user (development only).

Usage:
    python -m scripts.reset_admin --email admin@scholagro.com --password newpass

If not provided, defaults to admin@scholagro.com / admin123

This script MUST NOT be used in production.
"""
import argparse
from app import create_app
from app.extensions import db
from app.models import User
from werkzeug.security import generate_password_hash

parser = argparse.ArgumentParser(description='Reset or create admin user (dev only).')
parser.add_argument('--email', default='admin@scholagro.com')
parser.add_argument('--password', default='admin123')
args = parser.parse_args()

app = create_app()
with app.app_context():
    u = User.query.filter_by(email=args.email).first()
    if u:
        u.password_hash = generate_password_hash(args.password, method='pbkdf2:sha256')
        # Ensure the user has admin privileges
        u.is_admin = True
        db.session.add(u)
        db.session.commit()
        print(f"Updated password and admin flag for {args.email}")
    else:
        u = User(name='Admin', email=args.email, password_hash=generate_password_hash(args.password, method='pbkdf2:sha256'), is_admin=True)
        db.session.add(u)
        db.session.commit()
        print(f"Created admin user {args.email}")
