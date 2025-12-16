from datetime import datetime
from flask_login import UserMixin
from .extensions import db, login_manager

class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SubscriptionBasket(db.Model, TimestampMixin):
    __tablename__ = "subscription_baskets"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    basket_type = db.Column(db.String(64))  # e.g., "Weekly Fruit", "Monthly Veg"
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    next_delivery = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

class BlogPost(db.Model, TimestampMixin):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    content = db.Column(db.Text)
    author = db.Column(db.String(120))
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class Testimonial(db.Model, TimestampMixin):
    __tablename__ = "testimonials"
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(120))
    content = db.Column(db.Text)
    rating = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class SocialLink(db.Model, TimestampMixin):
    __tablename__ = "social_links"
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(64))
    url = db.Column(db.String(255))
    icon = db.Column(db.String(64))
    is_active = db.Column(db.Boolean, default=True)

 

class User(UserMixin, db.Model, TimestampMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120))
    phone = db.Column(db.String(32))
    is_admin = db.Column(db.Boolean, default=False)
    stripe_customer_id = db.Column(db.String(255), nullable=True)

    addresses = db.relationship("DeliveryAddress", backref="user", lazy=True)
    orders = db.relationship("Order", backref="user", lazy=True)
    reviews = db.relationship("Review", backref="user", lazy=True)
    wallet = db.relationship("Wallet", backref="user", uselist=False)
    loyalty = db.relationship("LoyaltyPoint", backref="user", uselist=False)
    activities = db.relationship("UserActivity", backref="user", lazy=True)


class Wallet(db.Model, TimestampMixin):
    __tablename__ = "wallets"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)


class LoyaltyPoint(db.Model, TimestampMixin):
    __tablename__ = "loyalty_points"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    points = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)


class UserActivity(db.Model, TimestampMixin):
    __tablename__ = "user_activities"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    action = db.Column(db.String(64))  # viewed, added_to_cart, purchased, etc.
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Recommendation(db.Model, TimestampMixin):
    __tablename__ = "recommendations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    reason = db.Column(db.String(128))  # e.g., "Buy Again", "Similar to past purchase"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    # Use session.get which is the modern API in SQLAlchemy 2.x
    return db.session.get(User, int(user_id))


class Category(db.Model, TimestampMixin):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"))

    products = db.relationship("Product", backref="category", lazy=True)


class Product(db.Model, TimestampMixin):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    old_price = db.Column(db.Numeric(10, 2))
    stock = db.Column(db.Integer, default=0)
    image_url = db.Column(db.String(500))
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    is_active = db.Column(db.Boolean, default=True)
    # Admin flags: allow admin to highlight products in homepage sections
    is_top_pick = db.Column(db.Boolean, default=False)
    is_new_arrival_featured = db.Column(db.Boolean, default=False)

    reviews = db.relationship("Review", backref="product", lazy=True)


class Review(db.Model, TimestampMixin):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    is_approved = db.Column(db.Boolean, default=True)


class DeliveryAddress(db.Model, TimestampMixin):
    __tablename__ = "delivery_addresses"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    line1 = db.Column(db.String(200), nullable=False)
    line2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    zone = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    is_default = db.Column(db.Boolean, default=False)


class DeliveryZone(db.Model, TimestampMixin):
    __tablename__ = "delivery_zones"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    fee = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    eta = db.Column(db.String(120))


class Order(db.Model, TimestampMixin):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rider_id = db.Column(db.Integer, db.ForeignKey("riders.id"))
    status = db.Column(db.String(32), default="pending")  # pending, packed, on_the_way, delivered
    total_amount = db.Column(db.Numeric(10, 2), default=0)
    delivery_fee = db.Column(db.Numeric(10, 2), default=0)
    address_id = db.Column(db.Integer, db.ForeignKey("delivery_addresses.id"))
    delivery_time_slot = db.Column(db.String(128))  # morning/afternoon/evening (expanded length)
    delivery_zone_id = db.Column(db.Integer, db.ForeignKey("delivery_zones.id"))
    coupon_code = db.Column(db.String(50))
    discount_amount = db.Column(db.Numeric(10, 2), default=0)
    instructions = db.Column(db.Text)

    items = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")
    payment = db.relationship("Payment", backref="order", uselist=False)
    delivery_zone = db.relationship("DeliveryZone")
    rider = db.relationship("Rider", back_populates="assigned_orders")


class OrderItem(db.Model, TimestampMixin):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)


class Payment(db.Model, TimestampMixin):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    method = db.Column(db.String(32), default="mpesa")
    reference = db.Column(db.String(120))
    amount = db.Column(db.Numeric(10, 2))
    status = db.Column(db.String(32), default="pending")  # pending, paid, failed
    raw_payload = db.Column(db.Text)


class CartItem(db.Model, TimestampMixin):
    __tablename__ = "cart_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    
    # Relationship to conveniently access the product from templates/controllers
    product = db.relationship("Product", lazy=True)


class WishlistItem(db.Model, TimestampMixin):
    __tablename__ = "wishlist_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product = db.relationship("Product", lazy=True)


class SavedItem(db.Model, TimestampMixin):
    __tablename__ = "saved_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product = db.relationship("Product", lazy=True)


class HomePageBanner(db.Model, TimestampMixin):
    __tablename__ = "homepage_banners"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    image_url = db.Column(db.String(500))
    link_url = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)


class Coupon(db.Model, TimestampMixin):
    __tablename__ = "coupons"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    discount_percent = db.Column(db.Integer, default=0)
    discount_amount = db.Column(db.Numeric(10, 2), default=0)
    min_order_value = db.Column(db.Numeric(10, 2), default=0)
    is_active = db.Column(db.Boolean, default=True)
    usage_count = db.Column(db.Integer, default=0)
    max_usage = db.Column(db.Integer)
    expires_at = db.Column(db.DateTime)


class Rider(db.Model, TimestampMixin):
    __tablename__ = "riders"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(32), unique=True)
    vehicle = db.Column(db.String(50))  # bike, car, etc.
    is_active = db.Column(db.Boolean, default=True)
    current_location = db.Column(db.String(500))  # JSON: {"lat": x, "lon": y}
    assigned_orders = db.relationship("Order", back_populates="rider")


class OrderStatusLog(db.Model, TimestampMixin):
    __tablename__ = "order_status_logs"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    status = db.Column(db.String(32), nullable=False)  # placed, confirmed, packed, picked, out, delivered
    notes = db.Column(db.Text)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"))




class Notification(db.Model, TimestampMixin):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    type = db.Column(db.String(32))  # order_update, promo, system
    is_read = db.Column(db.Boolean, default=False)


class Post(db.Model, TimestampMixin):
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False)
    body = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    is_published = db.Column(db.Boolean, default=False)
    published_at = db.Column(db.DateTime)


class ProductImage(db.Model, TimestampMixin):
    __tablename__ = "product_images"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)


class ReviewPhoto(db.Model, TimestampMixin):
    __tablename__ = "review_photos"
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey("reviews.id"), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)


class CategoryHeroImage(db.Model, TimestampMixin):
    __tablename__ = "category_hero_images"
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)


class FlashSale(db.Model, TimestampMixin):
    __tablename__ = "flash_sales"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    discount_percent = db.Column(db.Integer, default=0)
    original_price = db.Column(db.Numeric(10, 2), nullable=True)  # Store original price for safe reversion
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    quantity_available = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=True)
    product = db.relationship("Product", backref="flash_sales")



class AdminEvent(db.Model, TimestampMixin):
    __tablename__ = 'admin_events'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime)
    color = db.Column(db.String(16))
    url = db.Column(db.String(500))
    notes = db.Column(db.Text)
    zone = db.Column(db.String(120))  # optional delivery zone name


__all__ = [
    User, Category, Product, Review, DeliveryAddress, DeliveryZone,
    Order, OrderItem, Payment, CartItem, WishlistItem, SavedItem, HomePageBanner, Coupon
]
