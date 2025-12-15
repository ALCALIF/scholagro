"""
Create a sample products JSON file for import into the DB.

Usage:
  & ./.venv/Scripts/Activate.ps1
  python -m scripts.seed_sample_products --out instance/sample_products.json [--import]

If --import is provided, the script will run `scripts.import_products` on the generated file.
"""

import argparse
import json
import os
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from datetime import datetime

def sample_products(n=10):
    products = []
    for i in range(1, n+1):
        slug = f'sample-prod-{i}'
        products.append({
            'slug': slug,
            'name': f'Sample Product {i}',
            'price': round(0.5 + i * 1.5, 2),
            'stock': 10 + i,
            'image_url': f'https://example.com/images/{slug}.jpg',
            'is_active': True,
            'is_top_pick': (i % 3 == 0),
            'is_new_arrival_featured': (i % 4 == 0),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
        })
    return products


def main(argv=None):
    argv = argv or sys.argv[1:]
    p = argparse.ArgumentParser(description='Create a sample products JSON file for import')
    p.add_argument('--out', default='instance/sample_products.json', help='Output JSON file path')
    p.add_argument('--count', type=int, default=10, help='Number of sample products to generate')
    p.add_argument('--import', dest='do_import', action='store_true', help='Import the generated file into DB via scripts.import_products')
    args = p.parse_args(argv)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    products = sample_products(args.count)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    print('Wrote sample products JSON to', args.out, '(count=', len(products), ')')
    if args.do_import:
        print('Importing generated file to DB (this will upsert by slug)')
        try:
            from .import_products import main as import_main
            import_main([args.out])
        except Exception as e:
            print('Failed to import generated file:', e)


if __name__ == '__main__':
    main()
