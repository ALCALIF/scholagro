"""
Seed categories and products from a predefined catalog.

Usage:
    python -m scripts.seed_catalog

Notes:
- Safe to run multiple times; it will upsert by name/slug.
- Image URLs use Unsplash featured queries as placeholders. You can replace later in Admin.
"""
from app import create_app
from app.extensions import db
from app.models import Category, Product
from sqlalchemy import func
import re
import random

app = create_app()

CATALOG = {
    "Groceries / Food Items": [
        ("Long Grain Rice", 12.99, "long+grain+rice"),
        ("Local Rice", 10.49, "rice+bag"),
        ("Basmati Rice", 14.99, "basmati+rice"),
        ("Wheat Flour", 5.49, "wheat+flour"),
        ("Maize Flour", 4.99, "maize+flour"),
        ("Millet", 3.49, "millet+grain"),
        ("Corn", 2.99, "corn+kernels"),
        ("Oats", 4.49, "rolled+oats"),
        ("Vegetable Oil", 7.99, "vegetable+oil+bottle"),
        ("Palm Oil", 8.49, "palm+oil"),
        ("Sunflower Oil", 9.49, "sunflower+oil"),
        ("Groundnut Oil", 9.99, "peanut+oil"),
        ("Olive Oil", 11.99, "olive+oil+bottle"),
        ("Butter", 3.99, "butter+block"),
        ("Margarine", 2.99, "margarine"),
        ("Salt", 1.49, "table+salt"),
        ("Black Pepper", 2.49, "black+pepper"),
        ("Curry Powder", 2.29, "curry+powder"),
        ("Thyme", 1.99, "thyme+spice"),
        ("Ginger Powder", 2.19, "ginger+powder"),
        ("Garlic Powder", 2.19, "garlic+powder"),
        ("Chili Pepper", 1.99, "chili+pepper+spice"),
        ("Bay Leaves", 1.49, "bay+leaves"),
        ("White Sugar", 2.49, "white+sugar"),
        ("Brown Sugar", 2.69, "brown+sugar"),
        ("Honey", 5.99, "honey+jar"),
        ("Maple Syrup", 6.99, "maple+syrup"),
        ("Sweetener Cubes", 2.59, "sugar+cubes"),
        ("Tea Bags", 3.49, "tea+bags"),
        ("Coffee", 6.49, "coffee+beans"),
        ("Cocoa Powder", 4.99, "cocoa+powder"),
        ("Soft Drinks", 1.49, "soft+drink+cans"),
        ("Fruit Juice", 2.99, "fruit+juice+carton"),
        ("Energy Drinks", 2.49, "energy+drink+can"),
        ("Bottled Water", 0.99, "bottled+water"),
        ("Potato Chips", 1.49, "potato+chips+pack"),
        ("Popcorn", 1.99, "popcorn+pack"),
        ("Crackers", 1.89, "crackers+biscuits"),
        ("Cookies", 2.49, "cookies+pack"),
        ("Biscuits", 1.79, "biscuits+pack"),
        ("Peanuts", 1.59, "roasted+peanuts"),
        ("Chocolate Bars", 1.99, "chocolate+bar"),
    ],
    "Fresh Food": [
        ("Apples", 1.49, "fresh+apples"),
        ("Oranges", 1.29, "fresh+oranges"),
        ("Bananas", 0.99, "bananas+fruit"),
        ("Pineapple", 2.49, "pineapple+fruit"),
        ("Watermelon", 3.99, "watermelon+fruit"),
        ("Mangoes", 2.49, "mango+fruit"),
        ("Grapes", 2.99, "grapes+fruit"),
        ("Tomatoes", 1.49, "fresh+tomatoes"),
        ("Onions", 1.09, "red+onions"),
        ("Pepper", 1.19, "bell+pepper"),
        ("Carrots", 1.29, "carrots"),
        ("Spinach", 1.49, "spinach+leaves"),
        ("Cabbage", 1.99, "cabbage"),
        ("Lettuce", 1.79, "lettuce"),
        ("Chicken", 6.99, "raw+chicken"),
        ("Beef", 7.99, "beef+steak"),
        ("Mutton", 8.99, "mutton"),
        ("Turkey", 8.49, "turkey+meat"),
        ("Fresh Fish", 5.99, "fresh+fish"),
        ("Frozen Fish", 4.99, "frozen+fish"),
        ("Crayfish", 3.49, "crayfish"),
        ("Eggs", 2.99, "eggs+carton"),
    ],
    "Bakery & Dairy": [
        ("Bread", 1.49, "bread+loaf"),
        ("Buns", 1.19, "buns+bread"),
        ("Cakes", 8.99, "cake+slice"),
        ("Yogurt", 1.99, "yogurt+cups"),
        ("Milk", 1.29, "milk+carton"),
        ("Cheese", 2.99, "cheddar+cheese"),
        ("Custard", 2.49, "custard+dessert"),
    ],
    "Household Cleaning Products": [
        ("Detergent Powder", 3.49, "laundry+detergent+powder"),
        ("Liquid Soap", 2.99, "liquid+soap"),
        ("Washing Powder", 3.29, "washing+powder"),
        ("Fabric Softener", 3.49, "fabric+softener"),
        ("Bleach", 2.49, "bleach+bottle"),
        ("Disinfectant", 3.49, "disinfectant+cleaner"),
        ("Toilet Cleaner", 2.99, "toilet+cleaner"),
        ("Floor Cleaner", 2.99, "floor+cleaner"),
        ("Dishwashing Liquid", 2.49, "dishwashing+liquid"),
        ("Sponge", 0.99, "kitchen+sponge"),
        ("Scrub Brush", 1.49, "scrub+brush"),
    ],
    "Personal Care": [
        ("Bath Soap", 1.49, "bath+soap+bar"),
        ("Shampoo", 2.99, "shampoo+bottle"),
        ("Conditioner", 2.99, "conditioner+bottle"),
        ("Toothpaste", 1.99, "toothpaste+tube"),
        ("Toothbrush", 1.49, "toothbrush"),
        ("Body Cream", 3.49, "body+lotion"),
        ("Deodorant", 2.49, "deodorant"),
        ("Sanitary Pads", 2.99, "sanitary+pads"),
        ("Baby Diapers", 5.99, "baby+diapers"),
    ],
    "Kitchen & Household Equipment": [
        ("Plates", 1.99, "plates+ceramic"),
        ("Bowls", 1.79, "kitchen+bowls"),
        ("Cups", 1.69, "cups+mugs"),
        ("Spoons", 1.29, "spoons+cutlery"),
        ("Cooking Pots", 12.99, "cooking+pots"),
        ("Frying Pans", 9.99, "frying+pan"),
        ("Gas Stove", 49.99, "gas+stove"),
        ("Blender", 24.99, "kitchen+blender"),
        ("Electric Kettle", 19.99, "electric+kettle"),
        ("Food Storage Containers", 8.99, "food+storage+containers"),
    ],
    "Baby & Kids Products": [
        ("Baby Milk Formula", 9.99, "baby+milk+formula"),
        ("Baby Food", 4.99, "baby+food+jar"),
        ("Baby Wipes", 3.49, "baby+wipes"),
        ("Baby Soap", 2.49, "baby+soap"),
        ("Baby Lotion", 3.49, "baby+lotion"),
        ("Baby Toys", 5.99, "baby+toys"),
    ],
    "Pet Supplies": [
        ("Dog Food", 9.99, "dog+food"),
        ("Cat Food", 8.99, "cat+food"),
        ("Pet Shampoo", 3.99, "pet+shampoo"),
        ("Pet Bowls", 2.99, "pet+bowls"),
        ("Pet Toys", 4.99, "pet+toys"),
    ],
    "Home Essentials": [
        ("Light Bulbs", 2.49, "light+bulb"),
        ("Extension Cables", 4.99, "extension+cable"),
        ("Candles", 1.49, "candles"),
        ("Matches", 0.49, "matches+box"),
        ("Air Fresheners", 2.49, "air+freshener"),
        ("Insecticide Spray", 3.99, "insecticide+spray"),
    ],
    "Packaging & Storage": [
        ("Nylon Bags", 1.29, "plastic+bags"),
        ("Aluminum Foil", 2.49, "aluminum+foil"),
        ("Plastic Wrap", 1.99, "plastic+wrap"),
        ("Storage Buckets", 6.99, "storage+buckets"),
        ("Dust Bins", 7.99, "trash+bin"),
    ],
}


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s or "item"


def ensure_category(name: str):
    slug = slugify(name)
    cat = Category.query.filter(func.lower(Category.slug) == slug).first()
    if not cat:
        cat = Category(name=name, slug=slug)
        db.session.add(cat)
        db.session.flush()
    return cat


def ensure_product(cat: Category, name: str, price: float, kw: str):
    slug = slugify(name)
    existing = Product.query.filter_by(slug=slug).first()
    if existing:
        return existing
    # Unsplash featured placeholder query (safe to change later)
    image_url = f"https://source.unsplash.com/featured/?{kw}"
    p = Product(name=name, price=float(price), category_id=cat.id, slug=slug, image_url=image_url, stock=random.randint(5, 50))
    db.session.add(p)
    return p


with app.app_context():
    created_cats = 0
    created_products = 0
    for cat_name, items in CATALOG.items():
        cat = ensure_category(cat_name)
        created_cats += 1 if cat.id else 0
        for (nm, pr, kw) in items:
            if not Product.query.filter_by(slug=slugify(nm)).first():
                ensure_product(cat, nm, pr, kw)
                created_products += 1
    db.session.commit()
    print(f"Seed completed. Categories processed: {len(CATALOG)}, products created: {created_products}")
