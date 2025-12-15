import os
from app import create_app
from app.extensions import db
from app.models import Category, Product, User, DeliveryZone, Coupon
from werkzeug.security import generate_password_hash

app = create_app()

sample_categories = [
    ("Vegetables", "vegetables"),
    ("Fruits", "fruits"),
    ("Cereals", "cereals"),
    ("Household", "household"),
]

sample_products = [
    ("Fresh Tomatoes 1kg", "fresh-tomatoes-1kg", 120.00, "Vegetables", "https://images.unsplash.com/photo-1546471180-5f6a89ad870b?q=80&w=1200&auto=format&fit=crop"),
    ("Kales (Sukuma) Bunch", "kales-sukuma-bunch", 30.00, "Vegetables", "https://images.unsplash.com/photo-1510626176961-4b57d4fbad03?q=80&w=1200&auto=format&fit=crop"),
    ("Bananas 1kg", "bananas-1kg", 90.00, "Fruits", "https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?q=80&w=1200&auto=format&fit=crop"),
    ("Apples 1kg", "apples-1kg", 250.00, "Fruits", "https://images.unsplash.com/photo-1560807707-8cc77767d783?q=80&w=1200&auto=format&fit=crop"),
    ("Rice 2kg", "rice-2kg", 450.00, "Cereals", "https://images.unsplash.com/photo-1596040033229-a9821ebd058c?q=80&w=1200&auto=format&fit=crop"),
    ("Beans 1kg", "beans-1kg", 220.00, "Cereals", "https://images.unsplash.com/photo-1586201375761-83865001e31b?q=80&w=1200&auto=format&fit=crop"),
    ("Tissue Paper (4 pack)", "tissue-paper-4-pack", 180.00, "Household", "https://images.unsplash.com/photo-1584118624012-df056829fbd0?q=80&w=1200&auto=format&fit=crop"),
    ("Dish Soap 1L", "dish-soap-1l", 220.00, "Household", "https://images.unsplash.com/photo-1605296867304-46d5465a13f1?q=80&w=1200&auto=format&fit=crop"),
]

with app.app_context():
    # Admin user
    if not User.query.filter_by(email="adminscholagro@gmail.com").first():
        admin = User(
            name="Admin",
            email="adminscholagro@gmail.com",
            password_hash=generate_password_hash("@scholalcalif2030", method='pbkdf2:sha256'),
            is_admin=True
        )
        db.session.add(admin)
        print("Created admin user: adminscholagro@gmail.com / @scholalcalif2030")

    # Categories
    cat_map = {}
    for name, slug in sample_categories:
        c = Category.query.filter_by(slug=slug).first()
        if not c:
            c = Category(name=name, slug=slug)
            db.session.add(c)
        cat_map[name] = c

    db.session.flush()

    # Products
    for name, slug, price, cat_name, img in sample_products:
        if not Product.query.filter_by(slug=slug).first():
            # For development, mark every 3rd product as a top pick and every 4th as a featured new arrival
            p = Product(name=name, slug=slug, price=price, category=cat_map[cat_name], image_url=img, stock=50)
            if len(Product.query.all()) % 3 == 0:
                p.is_top_pick = True
            if len(Product.query.all()) % 4 == 0:
                p.is_new_arrival_featured = True
            db.session.add(p)

    # Delivery zones
    zones = [
        ("Nairobi", 200.0, "~2-4 hrs"),
        ("Kiambu", 250.0, "~3-5 hrs"),
        ("Juja", 150.0, "~2-4 hrs"),
        ("Ruiru", 150.0, "~2-4 hrs"),
        ("KU", 120.0, "~1-3 hrs"),
    ]
    for name, fee, eta in zones:
        if not DeliveryZone.query.filter_by(name=name).first():
            db.session.add(DeliveryZone(name=name, fee=fee, eta=eta))

    # Coupon
    if not Coupon.query.filter_by(code="FRESH10").first():
        db.session.add(Coupon(code="FRESH10", discount_percent=10, is_active=True))

    # Banners
    from app.models import HomePageBanner
    banner_imgs = [
        ("Daily Fresh Deals", "https://images.unsplash.com/photo-1501004318641-b39e6451bec6?q=80&w=1600&auto=format&fit=crop"),
        ("Household Essentials", "https://images.unsplash.com/photo-1542831371-29b0f74f9713?q=80&w=1600&auto=format&fit=crop"),
    ]
    for title, url in banner_imgs:
        if not HomePageBanner.query.filter_by(image_url=url).first():
            db.session.add(HomePageBanner(title=title, image_url=url, link_url="/shop", is_active=True))

    db.session.commit()
    print("Seed complete.")
