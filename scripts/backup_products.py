"""
Backup all products (and their images) to a JSON file in the instance folder.

Usage:
  & ./.venv/Scripts/Activate.ps1
  python -m scripts.backup_products

This script is non-destructive: it only reads from the DB and writes a JSON file.
"""

import os
import sys
import json
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.extensions import db


def main():
    app = create_app()
    with app.app_context():
        from app.models import Product
        products = db.session.query(Product).all()
        count = len(products)
        print(f'Found {count} products. Exporting...')
        out = os.path.join(app.instance_path, 'products_backup_full.json')
        payload = []
        for p in products:
            payload.append({
                'id': p.id,
                'name': p.name,
                'slug': p.slug,
                'price': str(p.price) if p.price is not None else None,
                'stock': p.stock,
                'is_active': p.is_active,
                'is_top_pick': p.is_top_pick,
                'is_new_arrival_featured': p.is_new_arrival_featured,
                'image_url': p.image_url,
                'category_id': p.category_id,
                'created_at': str(p.created_at) if p.created_at else None,
                'updated_at': str(p.updated_at) if p.updated_at else None,
            })
        os.makedirs(app.instance_path, exist_ok=True)
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print('Backup written to', out)
        print('Export summary: rows=', count)


if __name__ == '__main__':
    main()
