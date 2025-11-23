from app import create_app
from app.models import Product

app = create_app()

with app.app_context():
    total_products = Product.query.count()
    active_products = Product.query.filter_by(is_active=True).count()
    
    print(f"Total products: {total_products}")
    print(f"Active products: {active_products}")
    
    if total_products > 0:
        print("\nSample products:")
        for p in Product.query.limit(5).all():
            print(f"- {p.name} (ID: {p.id}, Active: {p.is_active}, Price: {p.price})")
    else:
        print("\nNo products found in the database.")
