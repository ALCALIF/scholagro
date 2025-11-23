from flask import Blueprint, render_template, request, Response, url_for, flash, redirect
from ...models import Product, Category, HomePageBanner, Review, Order, OrderItem, FlashSale, DeliveryZone, Coupon
from flask_login import login_required, current_user
from ...extensions import db, cache
from ...utils.email import send_email

shop_bp = Blueprint("shop", __name__)


@shop_bp.route("/")
@cache.cached(timeout=300)
def home():
    # Debug: Print database connection info
    print("\n=== DEBUG: Homepage Data ===")
    
    # Top picks
    products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).limit(12).all()
    print(f"Found {len(products)} products for top picks")
    
    categories = Category.query.all()
    print(f"Found {len(categories)} categories")
    
    banners = HomePageBanner.query.filter_by(is_active=True).order_by(HomePageBanner.created_at.desc()).limit(5).all()
    print(f"Found {len(banners)} active banners")
    
    # Daily deals (has a lower old_price than current price)
    deals = Product.query.filter(
        Product.is_active.is_(True),
        Product.old_price.isnot(None),
        Product.old_price > Product.price,
    ).order_by(Product.updated_at.desc()).limit(8).all()
    print(f"Found {len(deals)} daily deals")
    # New arrivals (last 14 days). If none, fall back to latest products so the section is not empty.
    from datetime import datetime, timedelta
    since = datetime.utcnow() - timedelta(days=14)
    new_arrivals = Product.query.filter(
        Product.is_active.is_(True),
        Product.created_at >= since
    ).order_by(Product.created_at.desc()).limit(8).all()
    if not new_arrivals:
        new_arrivals = Product.query.filter(
            Product.is_active.is_(True)
        ).order_by(Product.created_at.desc()).limit(8).all()
    # Top selling (by OrderItem quantity)
    from sqlalchemy import func
    top_ids = (
        OrderItem.query.with_entities(OrderItem.product_id, func.coalesce(func.sum(OrderItem.quantity), 0).label("qty"))
        .group_by(OrderItem.product_id)
        .order_by(func.coalesce(func.sum(OrderItem.quantity), 0).desc())
        .limit(8)
        .all()
    )
    top_ids_list = [pid for pid, _ in top_ids]
    top_selling = Product.query.filter(Product.id.in_(top_ids_list)).all() if top_ids_list else []
    # Active flash sales
    now = datetime.utcnow()
    flash_sales = FlashSale.query.filter(
        FlashSale.is_active.is_(True),
        FlashSale.starts_at <= now,
        FlashSale.ends_at >= now,
    ).limit(4).all()
    return render_template(
        "home.html",
        products=products,
        categories=categories,
        banners=banners,
        deals=deals,
        new_arrivals=new_arrivals,
        top_selling=top_selling,
        flash_sales=flash_sales,
    )


@shop_bp.route("/shop")
@cache.cached(timeout=300, query_string=True)
def shop():
    q = request.args.get("q")
    category_id = request.args.get("category")
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "newest")
    min_price = request.args.get("min", type=float)
    max_price = request.args.get("max", type=float)
    deals = request.args.get("deals") == '1'
    is_new = request.args.get("new") == '1'
    in_stock = request.args.get("in_stock") == '1'
    rating_min = request.args.get("rating", type=int)

    query = Product.query.filter_by(is_active=True)
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if deals:
        query = query.filter(Product.old_price.isnot(None), Product.old_price > Product.price)
    if is_new:
        from datetime import datetime, timedelta
        since = datetime.utcnow() - timedelta(days=14)
        query = query.filter(Product.created_at >= since)
    if in_stock:
        query = query.filter((Product.stock.is_(None)) | (Product.stock > 0))

    # Rating filter via subquery to avoid GROUP BY on main query
    if rating_min and 1 <= rating_min <= 5:
        from sqlalchemy import func, select
        avg_sub = (
            db.session.query(Review.product_id.label('pid'))
            .group_by(Review.product_id)
            .having(func.avg(Review.rating) >= rating_min)
            .subquery()
        )
        query = query.filter(Product.id.in_(select(avg_sub.c.pid)))

    if sort == 'price_asc':
        query = query.order_by(Product.price.asc())
    elif sort == 'price_desc':
        query = query.order_by(Product.price.desc())
    elif sort == 'rating':
        from sqlalchemy import func
        avg_sub = (
            db.session.query(Review.product_id.label('pid'), func.avg(Review.rating).label('avg_rating'))
            .group_by(Review.product_id)
            .subquery()
        )
        query = query.outerjoin(avg_sub, Product.id == avg_sub.c.pid).order_by(avg_sub.c.avg_rating.desc().nullslast())
    else:  # newest/default
        query = query.order_by(Product.created_at.desc())

    pagination = query.paginate(page=page, per_page=12, error_out=False)
    products = pagination.items
    categories = Category.query.all()
    return render_template("shop.html", products=products, categories=categories, pagination=pagination)


@shop_bp.route("/product/<slug>")
def product(slug):
    product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    reviews = Review.query.filter_by(product_id=product.id).order_by(Review.created_at.desc()).limit(20).all()
    avg = None
    if reviews:
        avg = round(sum(r.rating for r in reviews) / len(reviews), 1)

    # Flags for badges on the product page
    from datetime import datetime, timedelta
    is_new = False
    is_deal = False
    try:
        if product.created_at:
            is_new = product.created_at >= datetime.utcnow() - timedelta(days=14)
        if product.old_price is not None and product.price is not None:
            is_deal = float(product.old_price) > float(product.price)
    except Exception:
        pass

    # Related products (same category where possible, else recent active products), excluding current product
    related_products = []
    try:
        base_q = Product.query.filter(Product.is_active.is_(True), Product.id != product.id)
        if getattr(product, "category_id", None):
            base_q = base_q.filter(Product.category_id == product.category_id)
        related_products = base_q.order_by(Product.created_at.desc()).limit(8).all()
        if not related_products:
            related_products = Product.query.filter(
                Product.is_active.is_(True),
                Product.id != product.id,
            ).order_by(Product.created_at.desc()).limit(8).all()
    except Exception:
        pass

    return render_template(
        "product.html",
        product=product,
        reviews=reviews,
        avg_rating=avg,
        is_new=is_new,
        is_deal=is_deal,
        related_products=related_products,
    )


@shop_bp.route('/why-us')
def why_us():
    # Simple static page with information about the service
    return render_template('pages/why-us.html')


@shop_bp.route("/product/<slug>/review", methods=["POST"])
@login_required
def add_review(slug):
    product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment')
    if not rating or rating < 1 or rating > 5:
        return redirect(url_for('shop.product', slug=slug))
    # Allow only users who have purchased this product to review
    has_bought = db.session.query(OrderItem.id).join(Order, OrderItem.order_id == Order.id).filter(
        Order.user_id == current_user.id,
        OrderItem.product_id == product.id
    ).first() is not None
    if not has_bought:
        return redirect(url_for('shop.product', slug=slug))
    r = Review(rating=rating, comment=comment, user_id=current_user.id, product_id=product.id)
    db.session.add(r)
    db.session.commit()
    return redirect(url_for('shop.product', slug=slug))


@shop_bp.route("/api/suggest")
def suggest():
    q = request.args.get("q", "").strip()
    if not q:
        return {"items": []}
    items = Product.query.filter(Product.name.ilike(f"%{q}%"), Product.is_active.is_(True)).with_entities(Product.id, Product.name, Product.slug).limit(5).all()
    return {"items": [{"id": i.id, "name": i.name, "slug": i.slug} for i in items]}


@shop_bp.route("/about")
@shop_bp.route("/pages/about")
def about():
    return render_template("pages/about.html")


@shop_bp.route("/contact", methods=["GET", "POST"])
@shop_bp.route("/pages/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        subject = (request.form.get("subject") or "").strip()
        message = (request.form.get("message") or "").strip()

        if not name or not email or not subject or not message:
            flash("Please fill in all fields before sending your message.", "warning")
            return redirect(url_for("shop.contact"))

        body_lines = [
            f"From: {name} <{email}>",
            "-------------------------------------",
            message,
        ]
        ok = False
        try:
            ok = send_email(
                to=request.form.get("to", "support@scholagro.com"),
                subject=f"[Contact] {subject}",
                body="\n".join(body_lines),
            )
        except Exception:
            ok = False

        if ok:
            flash("Thank you for contacting us. We have received your message.", "success")
        else:
            flash("We could not send your message right now. Please try again later.", "danger")
        return redirect(url_for("shop.contact"))

    return render_template("pages/contact.html")


@shop_bp.route("/faqs")
@shop_bp.route("/pages/faqs")
def faqs():
    from datetime import datetime

    now = datetime.utcnow()
    coupons = Coupon.query.filter(
        Coupon.is_active.is_(True),
        (Coupon.expires_at.is_(None)) | (Coupon.expires_at >= now),
    ).order_by(Coupon.created_at.desc()).limit(10).all()
    return render_template("pages/faqs.html", coupons=coupons)


@shop_bp.route("/delivery")
@shop_bp.route("/pages/delivery")
def delivery():
    zones = DeliveryZone.query.order_by(DeliveryZone.name.asc()).all()
    return render_template("pages/delivery.html", zones=zones)


@shop_bp.route("/privacy")
@shop_bp.route("/pages/privacy")
def privacy():
    return render_template("pages/privacy.html")


@shop_bp.route("/terms")
@shop_bp.route("/pages/terms")
def terms():
    return render_template("pages/terms.html")


@shop_bp.route("/category/<slug>")
@cache.cached(timeout=300, query_string=True)
def category(slug):
    c = Category.query.filter_by(slug=slug).first_or_404()
    page = request.args.get("page", 1, type=int)
    q = Product.query.filter_by(is_active=True, category_id=c.id).order_by(Product.created_at.desc())
    pagination = q.paginate(page=page, per_page=12, error_out=False)
    return render_template("category.html", category=c, products=pagination.items, pagination=pagination)


@shop_bp.route("/sitemap.xml")
def sitemap_xml():
    from datetime import datetime
    urls = []
    # Static pages
    static_endpoints = ["shop.home", "shop.shop", "shop.about", "shop.contact", "shop.faqs", "shop.delivery", "shop.privacy", "shop.terms"]
    for ep in static_endpoints:
        try:
            urls.append(url_for(ep, _external=True))
        except Exception:
            pass
    # Categories
    for c in Category.query.all():
        urls.append(url_for('shop.category', slug=c.slug, _external=True))
    # Products (cap to 200)
    for p in Product.query.filter_by(is_active=True).order_by(Product.updated_at.desc()).limit(200):
        urls.append(url_for('shop.product', slug=p.slug, _external=True))
    xml = ['<?xml version="1.0" encoding="UTF-8"?>','<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    now = datetime.utcnow().strftime('%Y-%m-%d')
    for u in urls:
        xml.append(f"<url><loc>{u}</loc><lastmod>{now}</lastmod><changefreq>daily</changefreq><priority>0.7</priority></url>")
    xml.append('</urlset>')
    return Response('\n'.join(xml), mimetype='application/xml')


@shop_bp.route("/robots.txt")
def robots_txt():
    lines = [
        "User-agent: *",
        "Allow: /",
        "Sitemap: " + url_for('shop.sitemap_xml', _external=True)
    ]
    return Response('\n'.join(lines), mimetype='text/plain')
