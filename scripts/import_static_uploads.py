#!/usr/bin/env python3
r"""
Copy static upload files from a copied site into this project's `static/uploads` and optionally update DB `image_url` and `product_images` entries.

Usage (PowerShell):
  & .\.venv\Scripts\Activate.ps1
  python -m scripts.import_static_uploads --src "C:\path\to\Scholagro - Copy\static\uploads" --commit

Options:
    --src: Source uploads directory from copied site (required)
    --dest: Destination uploads directory inside the repo (default: static/uploads)
  --dry-run: Show what would be done without copying or making DB changes
  --commit: Actually copy files and update DB records
  --rename-conflict: If true, rename files on conflict by prefixing 'copied-'
"""
from __future__ import annotations
import argparse
import os
import shutil
import pathlib
from urllib.parse import urlparse
from pathlib import Path
import hashlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
import sys
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.extensions import db
from app.models import Product, ProductImage


def copy_files(src_root: Path, dest_root: Path, rename_conflict: bool = True, dry_run=False):
    copied = []
    for root, dirs, files in os.walk(src_root):
        root_p = Path(root)
        for f in files:
            src_file = root_p / f
            # preserve subfolder structure relative to src_root
            rel = src_file.relative_to(src_root)
            dest_file = dest_root / rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            if dest_file.exists():
                if rename_conflict:
                    dest_file = dest_file.parent / (f'copied-{f}')
                else:
                    # skip copying if conflict and not renaming
                    continue
            if dry_run:
                copied.append((str(src_file), str(dest_file)))
            else:
                shutil.copy2(str(src_file), str(dest_file))
                copied.append((str(src_file), str(dest_file)))
    return copied


def update_db_image_urls(dest_root: Path, dry_run=False):
    # map filename -> relative path (posix style) under /static/uploads
    mapping = {}
    for p in dest_root.rglob('*'):
        if p.is_file():
            rel_path = '/' + str(p).replace(str(Path.cwd()).replace('\\', '/'), '').lstrip('/')
            mapping[p.name] = rel_path
            # if the file was copied with a 'copied-' prefix, also map the original name without the prefix
            if p.name.startswith('copied-'):
                mapping[p.name[len('copied-'):]] = rel_path

    created = 0
    updated = 0
    skipped = 0
    changes = []
    with create_app().app_context():
        # update Product.image_url
        for pr in Product.query.all():
            if not pr.image_url:
                skipped += 1
                continue
            # if image_url has a filename we can match
            parsed = urlparse(pr.image_url)
            fname = os.path.basename(parsed.path)
            if fname in mapping:
                new_url = mapping[fname]
                if new_url != pr.image_url:
                    changes.append(('product', pr.id, pr.image_url, new_url))
                    if not dry_run:
                        pr.image_url = new_url
                        db.session.add(pr)
                    updated += 1
                else:
                    skipped += 1
            else:
                skipped += 1

        # update product_images table
        for img in ProductImage.query.all():
            parsed = urlparse(img.image_url)
            fname = os.path.basename(parsed.path)
            if fname in mapping:
                new_url = mapping[fname]
                if new_url != img.image_url:
                    changes.append(('product_image', img.id, img.image_url, new_url))
                    if not dry_run:
                        img.image_url = new_url
                        db.session.add(img)
                    updated += 1
                else:
                    skipped += 1
            else:
                skipped += 1

        if not dry_run:
            db.session.commit()
    return changes, updated, skipped


def parse_args():
    p = argparse.ArgumentParser(description='Copy upload files and optionally update DB image paths')
    p.add_argument('--src', required=True, help='Source static/uploads directory (copied site)')
    p.add_argument('--dest', default='static/uploads', help='Destination static uploads dir relative to repo root')
    p.add_argument('--dry-run', action='store_true', help='Show actions without copying or changing DB')
    p.add_argument('--commit', action='store_true', help='Perform copy and DB updates')
    p.add_argument('--rename-conflict', action='store_true', help='Rename files on conflict instead of skipping')
    return p.parse_args()


def main(argv=None):
    args = parse_args() if argv is None else parse_args(argv)
    src = Path(args.src)
    if not src.exists() or not src.is_dir():
        print(f'Source not found or not directory: {src}')
        return
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    print('Preparing copy...')
    copied = copy_files(src, dest, rename_conflict=args.rename_conflict, dry_run=args.dry_run or not args.commit)
    print(f'Files to copy (count): {len(copied)}')
    if args.dry_run or not args.commit:
        print('\nDRY RUN (no files copied, no DB changes):')
        for s, d in copied[:50]:
            print(s, '->', d)
        if len(copied) > 50:
            print('... and', len(copied)-50, 'more')
        return

    print('Files copied:')
    for s, d in copied:
        print(s, '->', d)

    print('Updating DB records to point to local uploads...')
    changes, updated, skipped = update_db_image_urls(dest, dry_run=False)
    print('DB update complete. Updated:', updated, 'Skipped:', skipped)
    if changes:
        print('Sample changes:')
        for c in changes[:20]:
            print(c)


if __name__ == '__main__':
    main()
