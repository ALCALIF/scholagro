"""
Fetch representative images for products missing image_url or with empty image_url.
Uses Unsplash Source (no API key) with query based on product name and category.
Downloads to static/uploads/scholagro/products and sets as primary image.

Usage:
  python -m scripts.fetch_images [--limit N]
"""
import os
import sys
import pathlib
import time
import random
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.extensions import db

import requests

SIZE = "600/600"
SAVE_DIR = pathlib.Path(ROOT) / "static" / "uploads" / "scholagro" / "products"
SAVE_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or f"img-{int(time.time())}"


def _try_fetch(session: requests.Session, url: str, dest_path: pathlib.Path) -> bool:
    try:
        r = session.get(url, timeout=15, allow_redirects=True)
        if r.status_code == 200 and r.content and len(r.content) > 1024:
            dest_path.write_bytes(r.content)
            return True
    except Exception:
        return False
    return False


def fetch_for_product(p, session: requests.Session, overwrite=False):
    # Skip if image already set and not overwriting
    if getattr(p, 'image_url', None) and not overwrite:
        return False
    q_parts = [str(getattr(p, 'name', '') or '').strip()]
    try:
        if getattr(p, 'category', None) and getattr(p.category, 'name', None):
            q_parts.append(p.category.name)
    except Exception:
        pass
    q = "+".join([x for x in q_parts if x]) or "grocery"
    fname = sanitize_filename(p.slug or p.name or f"p-{p.id}") + ".jpg"
    dest = SAVE_DIR / fname
    # Try multiple variants and locks to avoid repeated duplicates
    locks = [1, 2, 3, 4, 5]
    terms = [q, q + "+food", q + "+grocery"]
    urls = []
    for t in terms:
        for lk in locks:
            urls.append(f"https://loremflickr.com/{SIZE}/{t}?lock={lk}")
    urls.append(f"https://source.unsplash.com/random/{SIZE}/?{q}")
    for u in urls:
        if _try_fetch(session, u, dest):
            rel = f"/static/uploads/scholagro/products/{fname}"
            p.image_url = rel
            db.session.add(p)
            return True
    return False


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=200, help='Max number of products to process')
    ap.add_argument('--overwrite', action='store_true', help='Replace existing image_url')
    args = ap.parse_args(argv or sys.argv[1:])

    app = create_app()
    with app.app_context():
        from app.models import Product
        q = Product.query
        if not args.overwrite:
            q = q.filter((Product.image_url.is_(None)) | (Product.image_url == ""))
        products = q.order_by(Product.created_at.asc()).limit(args.limit).all()
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            "Accept": "image/*,application/octet-stream;q=0.9,*/*;q=0.8",
        })
        hits = 0
        for p in products:
            ok = fetch_for_product(p, session, overwrite=args.overwrite)
            if ok:
                hits += 1
                # small jitter to be polite
                time.sleep(0.2 + random.random() * 0.4)
        # Category-level fallback for any still missing
        remaining = Product.query.filter((Product.image_url.is_(None)) | (Product.image_url == "")).all()
        if remaining:
            by_cat = {}
            for p in remaining:
                cat = None
                try:
                    cat = p.category.name if p.category else None
                except Exception:
                    cat = None
                by_cat.setdefault(cat or "general", []).append(p)
            for cat_name, plist in by_cat.items():
                t = (cat_name or "grocery").lower().replace(" ", "+")
                # fetch one image for the category and reuse
                fname = sanitize_filename(f"cat-{t}") + ".jpg"
                dest = SAVE_DIR / fname
                got = False
                for lk in [1,2,3,4,5]:
                    if _try_fetch(session, f"https://loremflickr.com/{SIZE}/{t}?lock={lk}", dest):
                        got = True
                        break
                if not got:
                    _try_fetch(session, f"https://source.unsplash.com/random/{SIZE}/?{t}", dest)
                rel = f"/static/uploads/scholagro/products/{fname}"
                for p in plist:
                    if not p.image_url:
                        p.image_url = rel
                        db.session.add(p)
                        hits += 1
        db.session.commit()
        total = Product.query.count()
        print(f"Images attached this run: {hits}; remaining without image: {Product.query.filter((Product.image_url.is_(None)) | (Product.image_url == '')).count()}")


if __name__ == '__main__':
    main()
