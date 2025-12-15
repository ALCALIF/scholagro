"""
Seed hierarchical categories (with subcategories) and missing products.

Usage:
  python -m scripts.seed_hier_catalog

Notes:
- Idempotent: re-runs won't duplicate products (uses slug uniqueness).
- Creates parent categories and subcategories (Category.parent_id).
- Uses Unsplash query images as placeholders; you can replace later in Admin.
- Excludes regulated OTC medications by default.
"""
from app import create_app
from app.extensions import db
from app.models import Category, Product
from sqlalchemy import func
import re
import random

app = create_app()

DATA = {
    "Fresh Produce": {
        "Fruits": [
            ("Apples", 1.49, "apples"), ("Bananas", 0.99, "bananas"), ("Oranges", 1.29, "oranges"),
            ("Strawberries", 2.99, "strawberries"), ("Avocados", 1.49, "avocados"), ("Grapes", 2.59, "grapes"),
            ("Mangoes", 2.49, "mangoes"), ("Pineapples", 2.49, "pineapple"), ("Lemons", 1.09, "lemons"),
            ("Limes", 0.89, "limes"), ("Melons", 3.49, "melon"), ("Mixed Berries", 3.49, "berries")
        ],
        "Vegetables": [
            ("Onions", 1.09, "onions"), ("Potatoes", 1.19, "potatoes"), ("Carrots", 1.29, "carrots"),
            ("Bell Peppers", 1.49, "bell+pepper"), ("Tomatoes", 1.49, "tomatoes"), ("Cucumbers", 1.29, "cucumbers"),
            ("Broccoli", 1.79, "broccoli"), ("Spinach", 1.49, "spinach"), ("Lettuce", 1.49, "lettuce"),
            ("Garlic", 0.99, "garlic"), ("Ginger", 0.99, "ginger"), ("Mushrooms", 2.29, "mushrooms"),
            ("Coriander", 0.79, "coriander"), ("Parsley", 0.79, "parsley"), ("Basil", 0.99, "basil")
        ]
    },
    "Meat, Seafood, & Alternatives": {
        "Meat": [
            ("Chicken Breast", 6.99, "chicken+breast"), ("Beef Steak", 7.99, "beef+steak"),
            ("Pork Chops", 6.49, "pork+chops"), ("Lamb", 8.99, "lamb+meat"), ("Bacon", 4.99, "bacon"),
            ("Deli Ham", 3.99, "deli+ham")
        ],
        "Seafood": [
            ("Fresh Tilapia", 5.99, "tilapia+fish"), ("Salmon Fillet", 9.99, "salmon+fillet"),
            ("Prawns", 8.99, "prawns"), ("Shrimp", 8.49, "shrimp"), ("Mixed Shellfish", 7.99, "shellfish")
        ],
        "Meat Alternatives": [
            ("Paneer", 3.99, "paneer"), ("Tofu", 2.99, "tofu"), ("Tempeh", 3.49, "tempeh"),
            ("Plant-based Burger", 5.99, "plant+based+burger")
        ]
    },
    "Dairy, Eggs, & Refrigerated": {
        "Milk & Alternatives": [
            ("Whole Milk", 1.29, "milk+carton"), ("Skim Milk", 1.19, "milk+carton"), ("Chocolate Milk", 1.49, "flavoured+milk"),
            ("Almond Milk", 1.99, "almond+milk"), ("Oat Milk", 2.19, "oat+milk"), ("Soy Milk", 1.89, "soy+milk")
        ],
        "Cheese": [
            ("Cheddar", 2.99, "cheddar+cheese"), ("Mozzarella", 2.99, "mozzarella+cheese"), ("Parmesan", 3.49, "parmesan+cheese"),
            ("Cream Cheese", 2.49, "cream+cheese"), ("Cottage Cheese", 2.29, "cottage+cheese")
        ],
        "Yogurt": [
            ("Plain Yogurt", 1.69, "yogurt"), ("Greek Yogurt", 1.99, "greek+yogurt"), ("Flavored Yogurt", 1.89, "yogurt+fruit")
        ],
        "Other": [
            ("Butter", 3.49, "butter"), ("Margarine", 2.99, "margarine"), ("Eggs", 2.99, "eggs"), ("Cream", 2.49, "cream"),
            ("Refrigerated Dough", 2.99, "refrigerated+dough")
        ]
    },
    "Bakery": {
        "Bread": [
            ("Sliced Bread", 1.49, "bread+loaf"), ("Baguette", 1.29, "baguette"), ("Bagels", 1.49, "bagels"),
            ("Buns", 1.19, "buns"), ("Pita Bread", 1.29, "pita+bread"), ("Multigrain Loaf", 1.69, "bread+loaf")
        ],
        "Baked Goods": [
            ("Cakes", 8.99, "cake"), ("Muffins", 3.49, "muffins"), ("Croissants", 2.99, "croissants"),
            ("Pastries", 3.49, "pastry"), ("Cookies", 2.49, "cookies")
        ]
    },
    "Pantry Staples": {
        "Grains & Pulses": [
            ("Basmati Rice", 14.99, "basmati+rice"), ("Jasmine Rice", 12.99, "jasmine+rice"), ("Brown Rice", 12.49, "brown+rice"),
            ("All-purpose Flour", 5.49, "flour"), ("Whole Wheat Flour", 5.99, "whole+wheat+flour"), ("Oats", 4.49, "oats"),
            ("Pasta", 2.49, "pasta"), ("Red Lentils", 3.49, "lentils"), ("Black Beans", 2.99, "beans"), ("Quinoa", 4.99, "quinoa")
        ],
        "Canned & Jarred": [
            ("Tomato Paste", 1.49, "tomato+paste"), ("Pasta Sauce", 2.49, "pasta+sauce"), ("Baked Beans", 1.49, "baked+beans"),
            ("Canned Corn", 1.29, "canned+corn"), ("Canned Peas", 1.29, "canned+peas"), ("Pickles", 2.49, "pickles"),
            ("Jam", 2.49, "jam+jar"), ("Apple Sauce", 2.29, "apple+sauce")
        ],
        "Oils, Spices, & Condiments": [
            ("Olive Oil", 11.99, "olive+oil"), ("Vegetable Oil", 7.99, "vegetable+oil"), ("Mustard Oil", 9.49, "mustard+oil"),
            ("Salt", 1.49, "salt"), ("Sugar", 2.49, "sugar"), ("Honey", 5.99, "honey"),
            ("Turmeric", 2.19, "turmeric"), ("Cumin", 2.19, "cumin"), ("Black Pepper", 2.49, "black+pepper"),
            ("Ketchup", 1.99, "ketchup"), ("Mustard", 1.89, "mustard"), ("Mayonnaise", 2.29, "mayonnaise"),
            ("Salad Dressing", 2.49, "salad+dressing")
        ],
        "Cereals & Breakfast": [
            ("Cornflakes", 3.49, "cornflakes"), ("Granola", 4.49, "granola"), ("Pancake Mix", 3.49, "pancake+mix")
        ]
    },
    "Snacks & Confectionery": {
        "Snacks": [
            ("Chips", 1.49, "chips+snacks"), ("Pretzels", 1.49, "pretzels"), ("Popcorn", 1.99, "popcorn"),
            ("Nuts", 2.49, "mixed+nuts"), ("Trail Mix", 2.99, "trail+mix"), ("Crackers", 1.89, "crackers")
        ],
        "Biscuits": [
            ("Chocolate Cookies", 2.49, "cookies"), ("Digestive Biscuits", 1.99, "biscuits"), ("Savory Biscuits", 1.99, "savory+biscuits")
        ],
        "Sweets": [
            ("Chocolate Bars", 1.99, "chocolate+bar"), ("Candies", 1.49, "candies"), ("Gum", 0.99, "chewing+gum")
        ]
    },
    "Beverages": {
        "Hot Drinks": [
            ("Black Tea", 3.49, "tea+bags"), ("Green Tea", 3.99, "green+tea"), ("Herbal Tea", 3.99, "herbal+tea"),
            ("Ground Coffee", 6.49, "coffee+ground"), ("Instant Coffee", 5.49, "instant+coffee"), ("Hot Chocolate", 3.49, "hot+chocolate")
        ],
        "Cold Drinks": [
            ("Orange Juice", 2.99, "orange+juice"), ("Apple Juice", 2.99, "apple+juice"), ("Soda", 1.49, "soft+drink"),
            ("Sparkling Water", 1.49, "sparkling+water"), ("Energy Drinks", 2.49, "energy+drink"), ("Functional Drinks", 2.99, "functional+beverage")
        ]
    },
    "Frozen Foods": {
        "Frozen Meals": [
            ("Frozen Pizza", 5.99, "frozen+pizza"), ("Ready Meals", 4.99, "ready+meal"), ("Appetizers", 3.99, "frozen+appetizers")
        ],
        "Frozen Produce": [
            ("Frozen Peas", 1.29, "frozen+peas"), ("Frozen Corn", 1.29, "frozen+corn"), ("Mixed Veg", 1.49, "frozen+vegetables"), ("Frozen Berries", 2.49, "frozen+berries")
        ],
        "Desserts": [
            ("Ice Cream", 3.99, "ice+cream"), ("Frozen Dessert", 3.49, "frozen+dessert")
        ]
    },
    "Household Essentials": {
        "Cleaning Supplies": [
            ("Laundry Detergent", 3.49, "laundry+detergent"), ("Dish Soap", 2.49, "dish+soap"), ("All-purpose Cleaner", 2.99, "all+purpose+cleaner"),
            ("Bleach", 2.49, "bleach"), ("Glass Cleaner", 2.49, "glass+cleaner")
        ],
        "Paper Goods": [
            ("Toilet Paper", 3.49, "toilet+paper"), ("Paper Towels", 2.99, "paper+towels"), ("Tissues", 2.49, "tissues"), ("Napkins", 1.49, "napkins")
        ],
        "Home Goods": [
            ("Trash Bags", 1.99, "trash+bags"), ("Aluminum Foil", 2.49, "aluminum+foil"), ("Plastic Wrap", 1.99, "plastic+wrap"),
            ("Light Bulbs", 2.49, "light+bulb"), ("Batteries", 3.99, "batteries")
        ],
        "Pet Care": [
            ("Dog Food", 9.99, "dog+food"), ("Cat Food", 8.99, "cat+food"), ("Pet Treats", 3.49, "pet+treats"), ("Pet Accessories", 4.99, "pet+accessories")
        ]
    },
    "Personal Care & Health": {
        "Toiletries": [
            ("Bath Soap", 1.49, "bath+soap"), ("Shampoo", 2.99, "shampoo"), ("Conditioner", 2.99, "conditioner"),
            ("Toothpaste", 1.99, "toothpaste"), ("Mouthwash", 2.49, "mouthwash"), ("Deodorant", 2.49, "deodorant")
        ],
        "Hygiene": [
            ("Feminine Hygiene", 2.99, "sanitary+pads"), ("Razors", 2.49, "razor"), ("Shaving Cream", 2.49, "shaving+cream"), ("Hand Sanitizer", 1.99, "hand+sanitizer")
        ],
        "Baby Care": [
            ("Diapers", 5.99, "baby+diapers"), ("Baby Wipes", 3.49, "baby+wipes"), ("Baby Food", 4.99, "baby+food"), ("Infant Formula", 9.99, "baby+formula")
        ],
        # Excluding specific OTC medications; keep first aid, vitamins optional later
        "Health": [
            ("First Aid Kit", 6.99, "first+aid+kit"), ("Vitamins (General)", 4.99, "vitamins")
        ]
    }
}


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s or "item"


def ensure_category(name: str, parent: Category | None = None):
    slug = slugify(name)
    q = Category.query.filter(func.lower(Category.slug) == slug)
    cat = q.first()
    if not cat:
        cat = Category(name=name, slug=slug, parent_id=parent.id if parent else None)
        db.session.add(cat)
        db.session.flush()
    else:
        # if existing and parent differs, set it (keeps hierarchy consistent)
        if parent and cat.parent_id != parent.id:
            cat.parent_id = parent.id
    return cat


def ensure_product(cat: Category, name: str, price: float, kw: str):
    slug = slugify(name)
    existing = Product.query.filter_by(slug=slug).first()
    if existing:
        # ensure correct category if missing
        if existing.category_id != cat.id:
            existing.category_id = cat.id
        return existing
    image_url = f"https://source.unsplash.com/featured/?{kw}"
    p = Product(name=name, price=float(price), category_id=cat.id, slug=slug, image_url=image_url, stock=random.randint(5, 50))
    db.session.add(p)
    return p


with app.app_context():
    created_products = 0
    for parent_name, subs in DATA.items():
        parent = ensure_category(parent_name)
        for sub_name, items in subs.items():
            subcat = ensure_category(sub_name, parent)
            for nm, pr, kw in items:
                if not Product.query.filter_by(slug=slugify(nm)).first():
                    ensure_product(subcat, nm, pr, kw)
                    created_products += 1
    db.session.commit()
    print(f"Hierarchical seed complete. Products created: {created_products}")
