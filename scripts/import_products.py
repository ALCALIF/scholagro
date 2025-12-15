"""
Import products from a JSON or CSV file into the DB. Non-destructive by default — it will upsert by slug.

Usage:
  & ./.venv/Scripts/Activate.ps1
  python -m scripts.import_products path/to/products.json
  python -m scripts.import_products path/to/products.csv

Accepted fields (case-sensitive headers for CSV):
  slug, name, price, stock, image_url, is_active, is_top_pick, is_new_arrival_featured, category, images
  - images can be a pipe/comma/semicolon-separated list of URLs
"""

import os
import sys
import json
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.extensions import db


def main(argv=None):
    argv = argv or sys.argv[1:]
    import argparse
    p = argparse.ArgumentParser(description='Import products from JSON or CSV. Upsert by slug.')
    p.add_argument('path', help='Path to products JSON or CSV file')
    p.add_argument('--dry-run', action='store_true', help='Show what will change without committing')
    p.add_argument('--overwrite', action='store_true', help='Overwrite existing fields even if they are present')
    args = p.parse_args(argv)
    path = args.path
    if not os.path.exists(path):
        print('File not found:', path)
        return
    ext = os.path.splitext(path)[1].lower()
    data = None
    if ext == '.json':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    elif ext == '.csv':
        import csv
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data = list(reader)
    else:
        print('Unsupported file type:', ext)
        return
    app = create_app()
    created = 0
    updated = 0
    skipped = 0
    updated_slugs = []
    created_slugs = []
    with app.app_context():
        from app.models import Product, Category, ProductImage
        for obj in data:
            # Normalize from CSV rows or JSON objects
            def _get(key):
                return obj.get(key) if isinstance(obj, dict) else None

            slug = _get('slug')
            if not slug and _get('name'):
                slug = str(_get('name')).lower().replace(' ', '-')
            if not slug:
                print('Skipping product without slug:', obj)
                continue
            p = Product.query.filter_by(slug=slug).first()
            if p:
                # Decide whether to overwrite fields
                changed = False
                if args.overwrite or _get('name'):
                    new_name = _get('name') or p.name
                    if new_name != p.name:
                        p.name = new_name
                        changed = True
                if args.overwrite or ('price' in obj):
                    val = _get('price')
                    try:
                        new_price = float(val) if val not in (None, '') else p.price
                    except Exception:
                        new_price = p.price
                    if new_price != p.price:
                        p.price = new_price
                        changed = True
                if args.overwrite or ('stock' in obj):
                    try:
                        new_stock = int(_get('stock')) if _get('stock') not in (None, '') else p.stock
                    except Exception:
                        new_stock = p.stock
                    if new_stock != p.stock:
                        p.stock = new_stock
                        changed = True
                if args.overwrite or _get('image_url'):
                    new_img = _get('image_url') or p.image_url
                    if new_img != p.image_url:
                        p.image_url = new_img
                        changed = True
                if args.overwrite or ('is_active' in obj):
                    new_active = bool(_get('is_active')) if ('is_active' in obj) else p.is_active
                    if new_active != p.is_active:
                        p.is_active = new_active
                        changed = True
                    
                if args.overwrite or ('is_top_pick' in obj):
                    new_top = bool(_get('is_top_pick')) if ('is_top_pick' in obj) else p.is_top_pick
                    if new_top != p.is_top_pick:
                        p.is_top_pick = new_top
                        changed = True
                if args.overwrite or ('is_new_arrival_featured' in obj):
                    new_new_rel = bool(_get('is_new_arrival_featured')) if ('is_new_arrival_featured' in obj) else p.is_new_arrival_featured
                    if new_new_rel != p.is_new_arrival_featured:
                        p.is_new_arrival_featured = new_new_rel
                        changed = True
                # category update if provided
                cat_name = _get('category') or _get('category_name')
                if (args.overwrite or cat_name) and cat_name:
                    cat = Category.query.filter_by(name=cat_name).first()
                    if not cat:
                        cat = Category(name=cat_name, slug=str(cat_name).lower().replace(' ','-'))
                        db.session.add(cat)
                        db.session.flush()
                    if p.category_id != cat.id:
                        p.category_id = cat.id
                        changed = True
                if changed:
                    updated += 1
                    updated_slugs.append(slug)
                    if not args.dry_run:
                        db.session.add(p)
                # Handle images for existing products if provided
                imgs_val = _get('images')
                if imgs_val and not args.dry_run:
                    imgs = imgs_val
                    if isinstance(imgs, str):
                        sep = '|' if '|' in imgs else (',' if ',' in imgs else ';')
                        imgs = [i.strip() for i in imgs.split(sep) if i.strip()]
                    # overwrite old images if --overwrite
                    if args.overwrite:
                        ProductImage.query.filter_by(product_id=p.id).delete()
                    existing_imgs = {pi.image_url for pi in ProductImage.query.filter_by(product_id=p.id).all()}
                    first = (len(existing_imgs) == 0)
                    for img in imgs:
                        if img in existing_imgs:
                            continue
                        db.session.add(ProductImage(product_id=p.id, image_url=img, is_primary=first))
                        first = False
                else:
                    skipped += 1
            else:
                created += 1
                created_slugs.append(slug)
                # Prepare fields
                name = _get('name') or slug
                try:
                    price = float(_get('price')) if _get('price') not in (None, '') else 0
                except Exception:
                    price = 0
                try:
                    stock = int(_get('stock')) if _get('stock') not in (None, '') else 0
                except Exception:
                    stock = 0
                image_url = _get('image_url')
                is_active = bool(_get('is_active')) if ('is_active' in (obj or {})) else True
                is_top_pick = bool(_get('is_top_pick'))
                is_new_arrival_featured = bool(_get('is_new_arrival_featured'))
                # Category
                cat_name = _get('category') or _get('category_name')
                cat_id = None
                if cat_name:
                    cat = Category.query.filter_by(name=cat_name).first()
                    if not cat:
                        cat = Category(name=cat_name, slug=str(cat_name).lower().replace(' ','-'))
                        db.session.add(cat)
                        db.session.flush()
                    cat_id = cat.id
                p = Product(name=name, slug=slug, price=price, stock=stock, image_url=image_url, is_active=is_active, is_top_pick=is_top_pick, is_new_arrival_featured=is_new_arrival_featured, category_id=cat_id)
                try:
                    if not args.dry_run:
                        db.session.add(p)
                except Exception as e:
                    print('Failed to add product', slug, ':', e)
                # (images handled above for new products)
                # Process product images if provided (images: list or comma/pipe-separated string)
                imgs_val = _get('images')
                if imgs_val and not args.dry_run:
                    imgs = imgs_val
                    if isinstance(imgs, str):
                        sep = '|' if '|' in imgs else (',' if ',' in imgs else ';')
                        imgs = [i.strip() for i in imgs.split(sep) if i.strip()]
                    first = True
                    for img in imgs:
                        db.session.add(ProductImage(product_id=p.id, image_url=img, is_primary=first))
                        first = False
        if args.dry_run:
            print('\nDRY RUN: no commit performed. Summary:')
            print('  Created:', created)
            print('  Updated:', updated)
            print('  Skipped:', skipped)
            if created_slugs:
                print('  Created slugs:', created_slugs[:20])
            if updated_slugs:
                print('  Updated slugs:', updated_slugs[:20])
            return
        try:
            db.session.commit()
            print('Import commit successful')
            print('Summary: Created:', created, ' Updated:', updated, ' Skipped:', skipped)
        except Exception as e:
            db.session.rollback()
            print('Failed to commit import:', e)


if __name__ == '__main__':
    main()
