from flask import Blueprint, render_template, request, Response, url_for, flash, redirect
from ...models import Product, Category, HomePageBanner, Review, Order, OrderItem, FlashSale, DeliveryZone, Coupon, ProductImage, CategoryHeroImage, Post
from flask import jsonify, session
from flask_login import login_required, current_user
from ...extensions import db, cache
from ...utils.email import send_email
from flask import current_app
import json
import urllib.request
import urllib.parse
from ...utils.media import upload_image

shop_bp = Blueprint("shop", __name__)

def make_cache_key():
    """Cache key that varies by path, query string, and user auth/admin state.
    Ensures navbar updates instantly on login/logout/admin by busting per-user cache.
    """
    try:
        uid = getattr(current_user, 'id', None)
        is_auth = getattr(current_user, 'is_authenticated', False)
        is_admin = getattr(current_user, 'is_admin', False)
    except Exception:
        uid = None
        is_auth = False
        is_admin = False
    # include full_path to vary by query params where applicable
    from flask import request
    path = getattr(request, 'full_path', getattr(request, 'path', '/'))
    return f"{path}|uid:{uid}|auth:{int(bool(is_auth))}|admin:{int(bool(is_admin))}"

@shop_bp.route("/")
@cache.cached(timeout=300, key_prefix=make_cache_key)
def home():
    # Debug: Print database connection info
    print("\n=== DEBUG: Homepage Data ===")
    try:
        # Top picks
        # Show top picks on homepage: admin-selected products first, then fall back to latest; target: 6 columns x 5 rows = 30 products
        TOP_PICKS_LIMIT = 30
        top_picks = Product.query.filter(Product.is_active.is_(True), Product.is_top_pick.is_(True)).order_by(Product.updated_at.desc()).limit(TOP_PICKS_LIMIT).all()
        top_ids = [p.id for p in top_picks]
        if len(top_picks) < TOP_PICKS_LIMIT:
            needed = TOP_PICKS_LIMIT - len(top_picks)
            filler = Product.query.filter(Product.is_active.is_(True)).filter(~Product.id.in_(top_ids)).order_by(Product.created_at.desc()).limit(needed).all()
            products = top_picks + filler
        else:
            products = top_picks
        print(f"Found {len(products)} products for top picks")

        categories = Category.query.all()
        print(f"Found {len(categories)} categories")

        banners = HomePageBanner.query.filter_by(is_active=True).order_by(HomePageBanner.sort_order.asc(), HomePageBanner.created_at.desc()).limit(10).all()
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
        # Admin-controlled new arrivals first, fall back to created_at if necessary
        NEW_ARRIVALS_LIMIT = 12
        new_arrivals = Product.query.filter(Product.is_active.is_(True), Product.is_new_arrival_featured.is_(True)).order_by(Product.updated_at.desc()).limit(NEW_ARRIVALS_LIMIT).all()
        if len(new_arrivals) < NEW_ARRIVALS_LIMIT:
            # Fill remaining with products created in 'since' window first
            recent = Product.query.filter(
                Product.is_active.is_(True),
                Product.created_at >= since,
                ~Product.id.in_([p.id for p in new_arrivals])
            ).order_by(Product.created_at.desc()).limit(NEW_ARRIVALS_LIMIT - len(new_arrivals)).all()
            new_arrivals = new_arrivals + recent
        if not new_arrivals:
            new_arrivals = Product.query.filter(Product.is_active.is_(True)).order_by(Product.created_at.desc()).limit(8).all()

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
    except Exception as exc:
        # Log and surface a helpful message for missing tables / DB schema errors
        import logging
        logging.exception('Homepage database query failed')
        # Show a friendly error recommending DB migration
        from flask import abort
        return render_template('500.html'), 500

@shop_bp.route("/deals")
@cache.cached(timeout=300, key_prefix=make_cache_key)
def deals_page():
    from datetime import datetime
    deals = Product.query.filter(
        Product.is_active.is_(True),
        Product.old_price.isnot(None),
        Product.old_price > Product.price,
    ).order_by(Product.updated_at.desc()).limit(24).all()
    # Find active flash sales for these products so templates can show countdowns
    sale_ends = {}
    try:
        now = datetime.utcnow()
        product_ids = [p.id for p in deals]
        if product_ids:
            fss = FlashSale.query.filter(
                FlashSale.product_id.in_(product_ids),
                FlashSale.is_active.is_(True),
                FlashSale.starts_at <= now,
                FlashSale.ends_at >= now,
            ).all()
            for fs in fss:
                if fs and fs.product_id:
                    sale_ends[fs.product_id] = fs.ends_at.isoformat()
    except Exception:
        pass
    return render_template("deals.html", deals=deals, sale_ends=sale_ends)

@shop_bp.route("/shop")
@cache.cached(timeout=300, key_prefix=make_cache_key)
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


@shop_bp.route("/search")
@cache.cached(timeout=120, key_prefix=make_cache_key)
def search():
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "relevance")

    # Record recent searches in session (last 5)
    try:
        if q:
            rs = session.get("recent_searches", [])
            if q in rs:
                rs.remove(q)
            rs.insert(0, q)
            session["recent_searches"] = rs[:5]
    except Exception:
        pass

    query = Product.query.filter(Product.is_active.is_(True))
    if q:
        # Basic ILIKE search over name and description
        query = query.filter(
            (Product.name.ilike(f"%{q}%")) | (Product.description.ilike(f"%{q}%"))
        )
    # Sorting
    if sort == 'price_asc':
        query = query.order_by(Product.price.asc())
    elif sort == 'price_desc':
        query = query.order_by(Product.price.desc())
    elif sort == 'newest':
        query = query.order_by(Product.created_at.desc())
    else:  # relevance (fallback to newest for now)
        query = query.order_by(Product.created_at.desc())

    pagination = query.paginate(page=page, per_page=12, error_out=False)
    categories = Category.query.all()
    return render_template("shop.html", products=pagination.items, categories=categories, pagination=pagination)


@shop_bp.route("/api/search/suggest")
def search_suggest():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify([])
    items = (
        Product.query.with_entities(Product.name, Product.slug)
        .filter(Product.is_active.is_(True), Product.name.ilike(f"%{q}%"))
        .order_by(Product.created_at.desc())
        .limit(8)
        .all()
    )
    return jsonify([{"name": n, "slug": s} for (n, s) in items])


@shop_bp.route("/product/<slug>")
def product(slug):
    p = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    # Only approved reviews
    reviews = Review.query.filter_by(product_id=p.id, is_approved=True).order_by(Review.created_at.desc()).limit(50).all()
    avg = None
    if reviews:
        avg = round(sum(r.rating for r in reviews) / len(reviews), 1)
    # Flags
    from datetime import datetime, timedelta
    is_new = p.created_at and p.created_at >= (datetime.utcnow() - timedelta(days=14))
    is_deal = p.old_price and p.price and (float(p.old_price) > float(p.price))
    # Gallery images
    images = ProductImage.query.filter_by(product_id=p.id).order_by(ProductImage.is_primary.desc(), ProductImage.created_at.desc()).all()
    # Related
    related = Product.query.filter(
        Product.category_id == p.category_id,
        Product.id != p.id,
        Product.is_active.is_(True),
    ).order_by(Product.created_at.desc()).limit(8).all()
    # Verified purchasers (user ids who bought this product)
    from sqlalchemy import select
    buyer_ids = [uid for (uid,) in db.session.query(Order.user_id).join(OrderItem, OrderItem.order_id == Order.id).filter(OrderItem.product_id == p.id).distinct().all()]
    # Delivery ETA if user has default address with zone
    eta_text = None
    try:
        from flask_login import current_user
        if getattr(current_user, 'is_authenticated', False):
            addr = next((a for a in current_user.addresses or [] if getattr(a, 'is_default', False)), None)
            if addr:
                zone = db.session.query(DeliveryZone).filter_by(name=addr.zone).first()
                if zone and zone.eta:
                    eta_text = zone.eta
    except Exception:
        eta_text = None

    return render_template(
        "product.html",
        product=p,
        reviews=reviews,
        avg_rating=avg,
        is_new=is_new,
        is_deal=is_deal,
        product_images=images,
        related_products=related,
        verified_buyer_ids=buyer_ids,
        eta_text=eta_text,
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
    r = Review(rating=rating, comment=comment, user_id=current_user.id, product_id=product.id, is_approved=False)
    db.session.add(r)
    db.session.commit()
    # handle photo uploads (multiple files named 'photos')
    try:
        files = request.files.getlist('photos') or []
        # Limit to 5 files, allow only certain mime/extensions, max 5MB per file
        allowed_ext = {'.jpg', '.jpeg', '.png', '.webp'}
        import os
        files = files[:5]
        from ...models import ReviewPhoto
        for f in files:
            if not f or not getattr(f, 'filename', ''):
                continue
            name = f.filename.lower()
            ext = os.path.splitext(name)[1]
            if ext not in allowed_ext:
                continue
            # try size validation (<= 5MB)
            too_big = False
            size = getattr(f, 'content_length', None)
            try:
                pos = f.stream.tell()
                f.stream.seek(0, 2)
                end = f.stream.tell()
                f.stream.seek(pos)
                size = end
            except Exception:
                pass
            if size and size > 5 * 1024 * 1024:
                too_big = True
            if too_big:
                continue
            up = upload_image(f, folder="scholagro/reviews")
            if up:
                db.session.add(ReviewPhoto(review_id=r.id, image_url=up))
        db.session.commit()
    except Exception:
        db.session.rollback()
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
@shop_bp.route("/CONTACT", methods=["GET", "POST"])
@shop_bp.route("/pages/contact", methods=["GET", "POST"])
def contact():
    # If redirected back from Web3Forms
    if request.method == "GET" and request.args.get('sent'):
        flash("Thank you for contacting us. We have received your message.", "success")
        return render_template("pages/contact.html")

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
        # Try Web3Forms first
        try:
            access_key = (
                request.form.get("access_key")
                or current_app.config.get("WEB3FORMS_ACCESS_KEY")
            )
            if access_key:
                payload = {
                    "access_key": access_key,
                    "subject": f"[Contact] {subject}",
                    "from_name": name,
                    "from_email": email,
                    "message": message,
                    # Optional: let Web3Forms set reply-to header
                    "replyto": email,
                }
                data = urllib.parse.urlencode(payload).encode("utf-8")
                req = urllib.request.Request(
                    "https://api.web3forms.com/submit",
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        result = json.loads(resp.read().decode("utf-8") or "{}")
                        ok = bool(result.get("success", True))
        except Exception:
            ok = False

        # Fallback to SMTP if Web3Forms not available or failed
        if not ok:
            try:
                default_to = current_app.config.get("CONTACT_TO") or "scholagro@gmail.com"
                ok = send_email(
                    to=request.form.get("to", default_to),
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


@shop_bp.route("/refund")
@shop_bp.route("/pages/refund")
def refund():
    return render_template("pages/refund.html")


# Blog storefront
@shop_bp.route("/blog")
def blog_index():
    page = request.args.get('page', 1, type=int)
    q = (request.args.get('q') or '').strip()
    query = Post.query.filter_by(is_published=True)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Post.title.ilike(like), Post.slug.ilike(like)))
    pagination = query.order_by(Post.published_at.desc().nullslast(), Post.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template('blog/index.html', posts=pagination.items, pagination=pagination, q=q)


@shop_bp.route("/blog/<slug>")
def blog_detail(slug):
    p = Post.query.filter_by(slug=slug, is_published=True).first_or_404()
    # Simple related: latest 5 besides this
    related = Post.query.filter(Post.is_published.is_(True), Post.id != p.id).order_by(Post.published_at.desc().nullslast(), Post.created_at.desc()).limit(5).all()
    return render_template('blog/detail.html', post=p, related=related)


@shop_bp.route("/category/<slug>")
@cache.cached(timeout=300, key_prefix=make_cache_key)
def category(slug):
    c = Category.query.filter_by(slug=slug).first_or_404()
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "newest")
    min_price = request.args.get("min", type=float)
    max_price = request.args.get("max", type=float)
    in_stock = request.args.get("in_stock") == '1'
    rating_min = request.args.get("rating", type=int)
    sub_slug = request.args.get("sub")

    # Determine category scope: if parent category, include its children by default
    child_q = Category.query.filter(Category.parent_id == c.id)
    children = child_q.all()
    category_ids = [c.id]
    if children:
        category_ids.extend([ch.id for ch in children])

    # If a specific subcategory is requested, narrow to it
    if sub_slug:
        subcat = Category.query.filter_by(slug=sub_slug, parent_id=c.id).first()
        if subcat:
            category_ids = [subcat.id]

    query = Product.query.filter(Product.is_active.is_(True), Product.category_id.in_(category_ids))

    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if in_stock:
        query = query.filter((Product.stock.is_(None)) | (Product.stock > 0))

    # Rating filter via subquery
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
    else:
        query = query.order_by(Product.created_at.desc())

    pagination = query.paginate(page=page, per_page=12, error_out=False)
    cats = Category.query.all()
    # Load active/scheduled hero images (max 10)
    from datetime import datetime
    now = datetime.utcnow()
    hero_images = (
        CategoryHeroImage.query
        .filter(
            CategoryHeroImage.category_id == c.id,
            CategoryHeroImage.is_active.is_(True),
            (CategoryHeroImage.starts_at.is_(None)) | (CategoryHeroImage.starts_at <= now),
            (CategoryHeroImage.ends_at.is_(None)) | (CategoryHeroImage.ends_at >= now),
        )
        .order_by(CategoryHeroImage.sort_order.asc(), CategoryHeroImage.created_at.desc())
        .limit(10)
        .all()
    )
    hero_urls = [h.image_url for h in hero_images]
    return render_template(
        "category.html",
        category=c,
        products=pagination.items,
        pagination=pagination,
        categories=cats,
        subcategories=children,
        selected_sub=sub_slug,
        hero_images=hero_urls,
    )


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
