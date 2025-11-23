from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from ...extensions import db, cache
from ...utils.media import upload_image
from ...models import Product, Category, Order, HomePageBanner, Payment, User
from ...utils.email import send_email

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Admin access required", "danger")
            return redirect(url_for("auth.login"))
        return func(*args, **kwargs)
    return wrapper


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    product_count = Product.query.count()
    order_count = Order.query.count()
    user_count = db.session.query(db.func.count()).select_from(User).scalar()
    total_sales = db.session.query(db.func.sum(Order.total_amount)).scalar() or 0
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    return render_template("admin/dashboard.html", product_count=product_count, order_count=order_count, user_count=user_count, total_sales=total_sales, recent_orders=recent_orders)
@admin_bp.route("/analytics")
@login_required
@admin_required
def analytics():
    sales_by_day = db.session.query(db.func.date(Order.created_at), db.func.sum(Order.total_amount)).group_by(db.func.date(Order.created_at)).all()
    user_growth = db.session.query(db.func.date(User.created_at), db.func.count(User.id)).group_by(db.func.date(User.created_at)).all()
    return render_template("admin/analytics.html", sales_by_day=sales_by_day, user_growth=user_growth)
@admin_bp.route("/reports/advanced")
@login_required
@admin_required
def advanced_reports():
    from ...models import OrderItem
    sales_by_category = db.session.query(Category.name, db.func.sum(OrderItem.unit_price * OrderItem.quantity)).join(Product, Product.category_id == Category.id).join(OrderItem, OrderItem.product_id == Product.id).group_by(Category.name).all()
    top_products = db.session.query(Product.name, db.func.sum(OrderItem.quantity)).join(OrderItem, OrderItem.product_id == Product.id).group_by(Product.name).order_by(db.func.sum(OrderItem.quantity).desc()).limit(10).all()
    return render_template("admin/advanced_reports.html", sales_by_category=sales_by_category, top_products=top_products)


@admin_bp.route("/products", methods=["GET", "POST"])
@login_required
@admin_required
def products():
    if request.method == "POST":
        name = request.form.get("name")
        price = request.form.get("price")
        category_id = request.form.get("category_id")
        image_url = request.form.get("image_url")
        stock = request.form.get("stock", type=int)
        slug = request.form.get("slug") or name.lower().replace(" ", "-")
        # Optional file upload overrides image_url
        file = request.files.get("image_file")
        if file and file.filename:
            uploaded = upload_image(file, folder="scholagro/products")
            if uploaded:
                image_url = uploaded
        p = Product(name=name, price=price, category_id=category_id, slug=slug, image_url=image_url, stock=stock or 0)
        db.session.add(p)
        db.session.commit()
        try: cache.clear()
        except Exception: pass
        flash("Product added", "success")
    categories = Category.query.all()
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("admin/products.html", products=products, categories=categories)


@admin_bp.route("/orders")
@login_required
@admin_required
def orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template("admin/orders.html", orders=orders)


@admin_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@login_required
@admin_required
def update_order_status(order_id):
    from ...models import OrderStatusLog
    new_status = request.form.get("status")
    allowed = {"pending", "packed", "on_the_way", "delivered", "confirmed", "cancelled"}
    if new_status not in allowed:
        flash("Invalid status", "danger")
        return redirect(url_for("admin.orders"))

    order = Order.query.get_or_404(order_id)
    old_status = order.status
    order.status = new_status
    db.session.add(OrderStatusLog(order_id=order.id, status=new_status, notes=f"Admin updated from {old_status} to {new_status}"))
    db.session.commit()

    try:
        if order.user and order.user.email:
            send_email(
                to=order.user.email,
                subject=f"Your order #{order.id} is now {new_status.replace('_',' ').title()}",
                body=f"Hello,\n\nYour order #{order.id} status has changed from {old_status} to {new_status}.\n\nThank you for shopping with us."
            )
    except Exception:
        pass

    flash("Order status updated", "success")
    return redirect(url_for("admin.orders"))

@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_product(product_id):
    p = Product.query.get_or_404(product_id)
    if request.method == "POST":
        p.name = request.form.get("name") or p.name
        p.slug = request.form.get("slug") or p.slug
        p.price = request.form.get("price") or p.price
        p.stock = request.form.get("stock", type=int)
        p.category_id = request.form.get("category_id") or p.category_id
        image_url = request.form.get("image_url")
        file = request.files.get("image_file")
        if file and file.filename:
            uploaded = upload_image(file, folder="scholagro/products")
            if uploaded:
                image_url = uploaded
        if image_url:
            p.image_url = image_url
        db.session.commit()
        try: cache.clear()
        except Exception: pass
        flash("Product updated", "success")
        return redirect(url_for("admin.products"))
    categories = Category.query.all()
    return render_template("admin/product_edit.html", product=p, categories=categories)


@admin_bp.route("/products/<int:product_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_product(product_id):
    p = Product.query.get_or_404(product_id)
    db.session.delete(p)
    db.session.commit()
    try: cache.clear()
    except Exception: pass
    flash("Product deleted", "info")
    return redirect(url_for("admin.products"))


@admin_bp.route("/categories", methods=["GET", "POST"])
@login_required
@admin_required
def categories():
    if request.method == "POST":
        name = request.form.get("name")
        slug = request.form.get("slug") or name.lower().replace(" ", "-")
        if not name:
            flash("Name required", "danger")
        else:
            if not Category.query.filter_by(slug=slug).first():
                db.session.add(Category(name=name, slug=slug))
                db.session.commit()
                try: cache.clear()
                except Exception: pass
                flash("Category added", "success")
            else:
                flash("Slug already exists", "warning")
    cats = Category.query.order_by(Category.name).all()
    return render_template("admin/categories.html", categories=cats)


@admin_bp.route("/categories/<int:cat_id>/edit", methods=["POST"])
@login_required
@admin_required
def edit_category(cat_id):
    c = Category.query.get_or_404(cat_id)
    name = request.form.get("name")
    slug = request.form.get("slug")
    if name:
        c.name = name
    if slug:
        c.slug = slug
    db.session.commit()
    try: cache.clear()
    except Exception: pass
    flash("Category updated", "success")
    return redirect(url_for("admin.categories"))


@admin_bp.route("/categories/<int:cat_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_category(cat_id):
    c = Category.query.get_or_404(cat_id)
    db.session.delete(c)
    db.session.commit()
    try: cache.clear()
    except Exception: pass
    flash("Category deleted", "info")
    return redirect(url_for("admin.categories"))


@admin_bp.route("/banners", methods=["GET", "POST"])
@login_required
@admin_required
def banners():
    if request.method == "POST":
        title = request.form.get("title")
        image_url = request.form.get("image_url")
        link_url = request.form.get("link_url")
        # Optional file upload overrides image_url
        file = request.files.get("image_file")
        if file and file.filename:
            uploaded = upload_image(file, folder="scholagro/banners")
            if uploaded:
                image_url = uploaded
        db.session.add(HomePageBanner(title=title, image_url=image_url, link_url=link_url, is_active=True))
        db.session.commit()
        try: cache.clear()
        except Exception: pass
        flash("Banner added", "success")
    banners = HomePageBanner.query.order_by(HomePageBanner.created_at.desc()).all()
    return render_template("admin/banners.html", banners=banners)


@admin_bp.route("/banners/<int:banner_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_banner(banner_id):
    b = HomePageBanner.query.get_or_404(banner_id)
    b.is_active = not b.is_active
    db.session.commit()
    flash("Banner updated", "success")
    return redirect(url_for("admin.banners"))


@admin_bp.route("/banners/<int:banner_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_banner(banner_id):
    b = HomePageBanner.query.get_or_404(banner_id)
    db.session.delete(b)
    db.session.commit()
    flash("Banner deleted", "info")
    return redirect(url_for("admin.banners"))


@admin_bp.route("/import", methods=["GET", "POST"])
@login_required
@admin_required
def bulk_import():
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("Please upload a CSV file", "warning")
            return redirect(url_for("admin.bulk_import"))
        import csv, io
        stream = io.StringIO(file.stream.read().decode('utf-8'))
        reader = csv.DictReader(stream)
        created = 0
        for row in reader:
            name = row.get('name'); slug = row.get('slug') or (name or '').lower().replace(' ','-')
            price = row.get('price'); image_url = row.get('image_url'); stock = int(row.get('stock') or 0)
            cat_name = row.get('category');
            category = None
            if cat_name:
                category = Category.query.filter_by(name=cat_name).first()
                if not category:
                    category = Category(name=cat_name, slug=(cat_name or '').lower().replace(' ','-'))
                    db.session.add(category)
                    db.session.flush()
            if name and price:
                if not Product.query.filter_by(slug=slug).first():
                    p = Product(name=name, slug=slug, price=price, image_url=image_url, stock=stock, category_id=category.id if category else None)
                    db.session.add(p)
                    created += 1
        db.session.commit()
        flash(f"Imported {created} products", "success")
        return redirect(url_for("admin.products"))
    return render_template("admin/import.html")


@admin_bp.route("/reports/orders.csv")
@login_required
@admin_required
def orders_report_csv():
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["OrderID","User","Status","Total","DeliveryFee","Discount","Zone","CreatedAt"])
    for o in Order.query.order_by(Order.created_at.desc()).all():
        writer.writerow([o.id, (o.user.email if o.user else ''), o.status, o.total_amount, o.delivery_fee, o.discount_amount, (o.delivery_zone.name if o.delivery_zone else ''), o.created_at])
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=orders.csv'})


@admin_bp.route("/payments")
@login_required
@admin_required
def payments():
    q = Payment.query.order_by(Payment.created_at.desc())
    status = request.args.get('status')
    if status:
        q = q.filter_by(status=status)
    items = q.limit(500).all()
    return render_template("admin/payments.html", payments=items, status=status)
