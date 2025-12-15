#!/usr/bin/env python3
"""
Export products from a SQLite DB to the JSON format we use for imports.

Usage (Windows PowerShell):
    & .\.venv\Scripts\Activate.ps1
    python -m scripts.export_sqlite_products --db "C:\path\to\scholagro.db" --out .\instance\products_from_copy.json

This script maps the local SQLite schema to the import format: it reads `products`,
`categories`, and `product_images` and builds a JSON list of products with fields expected by
`scripts.import_products`.
"""
import argparse
import json
import sqlite3
from pathlib import Path


def map_row_to_product(row, categories_by_id, images_by_product_id):
    # row is a sqlite3.Row so access by column name
    def getbool(val):
        return bool(val) if val is not None else False

    def getval(r, name, default=None):
        # sqlite3.Row supports mapping protocol but not .get(); support missing columns
        try:
            return r[name]
        except Exception:
            return default

    product = {
        "slug": getval(row, "slug") or f"product-{getval(row,'id')}",
        "name": getval(row, "name") or "",
        "short_description": None,
        "description": getval(row, "description"),
        "price": str(getval(row, "price")) if getval(row, "price") is not None else None,
        "list_price": str(getval(row, "old_price")) if getval(row, "old_price") is not None else None,
        "currency": "USD",
        "is_active": getbool(getval(row, "is_active")),
        "inventory_qty": int(getval(row, "stock") or 0),
        "category_slugs": [],
        "images": images_by_product_id.get(getval(row, "id"), []),
        "is_top_pick": getbool(getval(row, "is_top_pick")),
        "is_new_arrival_featured": getbool(getval(row, "is_new_arrival_featured")),
        "attributes": {},
    }
    # Map category id to slug if available
    category_id = getval(row, "category_id")
    if category_id:
        slug = categories_by_id.get(category_id)
        if slug:
            product["category_slugs"].append(slug)

    return product


def export_products(db_path: Path, out_path: Path, limit=None):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # categories map
    categories_by_id = {}
    try:
        cur.execute("SELECT id, slug FROM categories")
        for r in cur.fetchall():
            categories_by_id[r[0]] = r[1]
    except sqlite3.OperationalError:
        # no categories table or error reading; continue
        pass

    # product images map
    images_by_product_id = {}
    try:
        cur.execute("SELECT product_id, image_url, is_primary FROM product_images ORDER BY is_primary DESC")
        for r in cur.fetchall():
            pid = r[0]
            images_by_product_id.setdefault(pid, []).append(r[1])
    except sqlite3.OperationalError:
        # missing table
        pass

    # Read products
    query = "SELECT * FROM products"
    if limit:
        query += f" LIMIT {int(limit)}"

    cur.execute(query)
    products = []
    for row in cur.fetchall():
        product = map_row_to_product(row, categories_by_id, images_by_product_id)
        products.append(product)

    # Write JSON file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)

    print(f"Exported {len(products)} products to {out_path}")


def parse_args():
    p = argparse.ArgumentParser(description="Export products from SQLite DB to JSON import format")
    p.add_argument("--db", required=True, help="Path to SQLite DB file")
    p.add_argument("--out", default="instance/products_from_copy.json", help="Output JSON file path")
    p.add_argument("--limit", type=int, help="Limit the number of exported products")
    return p.parse_args()


def main():
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    if not db_path.exists():
        print(f"DB file not found: {db_path}")
        raise SystemExit(1)
    export_products(db_path, out_path, limit=args.limit)


if __name__ == "__main__":
    main()
