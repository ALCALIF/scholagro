from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, abort, current_app
import json
import os
import pathlib
import requests
from urllib.parse import urlparse
from flask_login import login_required, current_user
from ...extensions import db, cache
from werkzeug.security import generate_password_hash, check_password_hash
from ...utils.media import upload_image
from ...models import Product, Category, Order, HomePageBanner, Payment, User, Review, DeliveryZone, CategoryHeroImage, FlashSale, Coupon, AdminEvent
from ...models import ReviewPhoto
from ...models import Post
from ...utils.search import index_product
from ...models import Notification
from ...utils.email import send_email
from ...extensions import csrf
from ...extensions import socketio
from werkzeug.security import generate_password_hash

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
    from datetime import date, datetime, timedelta
    import calendar
    import json
    product_count = Product.query.count()
    order_count = Order.query.count()
    user_count = db.session.query(db.func.count()).select_from(User).scalar()
    total_sales = db.session.query(db.func.sum(Order.total_amount)).scalar() or 0
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    recent_payments = Payment.query.order_by(Payment.created_at.desc()).limit(5).all()
    latest_reviews = Review.query.order_by(Review.created_at.desc()).limit(5).all()
    # Revenue by zone (top 5)
    revenue_by_zone = (
        db.session.query(DeliveryZone.name, db.func.sum(Order.total_amount))
        .join(DeliveryZone, DeliveryZone.id == Order.delivery_zone_id)
        .group_by(DeliveryZone.name)
        .order_by(db.func.sum(Order.total_amount).desc())
        .limit(5)
        .all()
    )
    # Build last 12 months analytics series for charts
    def month_range(d: date):
        start = d.replace(day=1)
        last_day = calendar.monthrange(start.year, start.month)[1]
        end = start.replace(day=last_day) + timedelta(days=1)  # exclusive
        return start, end
    today = date.today()
    months = []
    for i in range(11, -1, -1):
        y = today.year
        m = today.month - i
        while m <= 0:
            m += 12
            y -= 1
        months.append(date(y, m, 1))
    labels = [d.strftime('%b %Y') for d in months]
    sales_series = []
    orders_series = []
    users_series = []
    products_series = []
    for d in months:
        start, end = month_range(d)
        sales = db.session.query(db.func.coalesce(db.func.sum(Order.total_amount), 0)) \
            .filter(Order.created_at >= start, Order.created_at < end).scalar() or 0
        sales_series.append(float(sales))
        oc = db.session.query(db.func.count(Order.id)) \
            .filter(Order.created_at >= start, Order.created_at < end).scalar() or 0
        orders_series.append(int(oc))
        uc = db.session.query(db.func.count(User.id)) \
            .filter(User.created_at >= start, User.created_at < end).scalar() or 0
        users_series.append(int(uc))
        pc = db.session.query(db.func.count(Product.id)) \
            .filter(Product.created_at >= start, Product.created_at < end).scalar() or 0
        products_series.append(int(pc))
    # Active homepage banners preview
    active_banners = HomePageBanner.query.filter_by(is_active=True).order_by(HomePageBanner.sort_order.asc(), HomePageBanner.created_at.desc()).all()
    # Announcement messages (best-effort load from instance file)
    promo_messages = [
        'Fresh groceries delivered to your doorstep—fast and affordable!',
        'Order today and enjoy same-day delivery across KU, Ruiru & Nairobi!',
        'Get the best prices on fruits, veggies, and household essentials!',
        'ScholaGro—We deliver exactly what you ordered, fresh and clean!',
        'Save more this season with our daily offers and discounts!'
    ]
    try:
        inst = current_app.instance_path if hasattr(current_app, 'instance_path') else os.path.join(os.getcwd(), 'instance')
        os.makedirs(inst, exist_ok=True)
        p = os.path.join(inst, 'announcements.json')
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    promo_messages = [str(x) for x in data if str(x).strip()]
    except Exception:
        pass
    return render_template(
        "admin/dashboard.html",
        product_count=product_count,
        order_count=order_count,
        user_count=user_count,
        total_sales=total_sales,
        recent_orders=recent_orders,
        recent_payments=recent_payments,
        latest_reviews=latest_reviews,
        revenue_by_zone=revenue_by_zone,
        chart_labels=labels,
        chart_sales=sales_series,
        chart_orders=orders_series,
        chart_users=users_series,
        chart_products=products_series,
        active_banners=active_banners,
        promo_messages=promo_messages,
    )
@admin_bp.route("/calendar")
@login_required
@admin_required
def calendar_view():
    zones = DeliveryZone.query.order_by(DeliveryZone.name.asc()).all()
    return render_template("admin/calendar.html", zones=zones)

@admin_bp.route("/calendar/events")
@login_required
@admin_required
def calendar_events():
    from datetime import datetime
    # Optional range filtering
    start = request.args.get('start')
    end = request.args.get('end')
    status = (request.args.get('status') or '').strip()
    zone_id = request.args.get('zone_id', type=int)
    q = Order.query
    try:
        if start:
            start_dt = datetime.fromisoformat(start.replace('Z',''))
            q = q.filter(Order.created_at >= start_dt)
        if end:
            end_dt = datetime.fromisoformat(end.replace('Z',''))
            q = q.filter(Order.created_at <= end_dt)
    except Exception:
        pass
    try:
        if status:
            q = q.filter(Order.status == status)
    except Exception:
        pass
    try:
        if zone_id:
            q = q.filter(Order.delivery_zone_id == zone_id)
    except Exception:
        pass
    events = []
    for o in q.order_by(Order.created_at.desc()).limit(1000).all():
        title = f"Order #{o.id} — {o.status.title() if o.status else 'pending'}"
        events.append({
            'id': o.id,
            'title': title,
            'start': (o.created_at.isoformat() if o.created_at else None),
            'url': url_for('admin.orders') + f"?q={o.id}",
            'color': '#10b981' if (o.status or '').startswith('delivered') else '#3b82f6'
        })
    # Include admin-created events
    try:
        s_raw = request.args.get('start')
        e_raw = request.args.get('end')
        evq = AdminEvent.query
        if s_raw and e_raw:
            from datetime import datetime
            s = datetime.fromisoformat(s_raw[:19])
            e = datetime.fromisoformat(e_raw[:19])
            evq = evq.filter(AdminEvent.start_at < e, (AdminEvent.end_at.is_(None)) | (AdminEvent.end_at >= s))
        for ev in evq.order_by(AdminEvent.start_at.asc()).all():
            events.append({
                'id': f"ev-{ev.id}",
                'title': ev.title,
                'start': ev.start_at.isoformat() if ev.start_at else None,
                'end': ev.end_at.isoformat() if ev.end_at else None,
                'url': ev.url,
                'color': ev.color or '#f59e0b',
                'notes': ev.notes,
            })
    except Exception:
        pass
    return Response(json.dumps(events), mimetype='application/json')

@admin_bp.route('/calendar/events', methods=['POST'])
@login_required
@admin_required
def create_calendar_event():
    from datetime import datetime
    title = (request.form.get('title') or '').strip()
    start_raw = request.form.get('start_at')
    end_raw = request.form.get('end_at')
    color = request.form.get('color')
    urlf = request.form.get('url')
    notes = request.form.get('notes')
    if not title or not start_raw:
        return Response('Missing title or start_at', status=400)
    try:
        start_at = datetime.fromisoformat(start_raw)
        end_at = datetime.fromisoformat(end_raw) if end_raw else None
    except Exception:
        return Response('Invalid datetime', status=400)
    ev = AdminEvent(title=title, start_at=start_at, end_at=end_at, color=color, url=urlf, notes=notes)
    db.session.add(ev)
    db.session.commit()
    return Response(json.dumps({'id': ev.id}), mimetype='application/json')

@admin_bp.route('/calendar/events/<int:event_id>', methods=['POST'])
@login_required
@admin_required
def update_calendar_event(event_id):
    from datetime import datetime
    ev = db.session.get(AdminEvent, event_id)
    if not ev:
        return Response('Not found', status=404)
    title = request.form.get('title')
    start_raw = request.form.get('start_at')
    end_raw = request.form.get('end_at')
    if title is not None:
        ev.title = title
    if start_raw:
        try:
            ev.start_at = datetime.fromisoformat(start_raw)
        except Exception:
            pass
    if end_raw:
        try:
            ev.end_at = datetime.fromisoformat(end_raw)
        except Exception:
            pass
    for key in ['color','url','notes']:
        val = request.form.get(key)
        if val is not None:
            setattr(ev, key, val)
    db.session.commit()
    return Response('OK', status=200)

@admin_bp.route('/calendar/events/<int:event_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_calendar_event(event_id):
    ev = db.session.get(AdminEvent, event_id)
    if not ev:
        return Response('Not found', status=404)
    db.session.delete(ev)
    db.session.commit()
    return Response('OK', status=200)

@admin_bp.route('/analytics/series')
@login_required
@admin_required
def analytics_series():
    from datetime import datetime, timedelta, date
    mode = (request.args.get('mode') or 'm').lower()  # d=days, w=weeks, m=months
    days = request.args.get('days', type=int)
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    now = datetime.utcnow()
    if start_str and end_str:
        try:
            start = datetime.fromisoformat(start_str[:19])
            end = datetime.fromisoformat(end_str[:19])
        except Exception:
            start = now - timedelta(days=30)
            end = now
    else:
        if mode == 'd':
            days = days or 30
            start = now - timedelta(days=days-1)
            end = now
        elif mode == 'w':
            weeks = (days // 7) if days else 12
            start = now - timedelta(weeks=weeks-1)
            end = now
        else:
            months = 12
            # approx 365 days
            start = now - timedelta(days=365)
            end = now
    # Build buckets
    labels = []
    buckets = []
    if mode == 'd':
        cur = datetime(start.year, start.month, start.day)
        while cur.date() <= end.date():
            nxt = cur + timedelta(days=1)
            labels.append(cur.strftime('%Y-%m-%d'))
            buckets.append((cur, nxt))
            cur = nxt
    elif mode == 'w':
        # week buckets starting Mondays
        cur = datetime(start.year, start.month, start.day) - timedelta(days=datetime(start.year, start.month, start.day).weekday())
        while cur <= end:
            nxt = cur + timedelta(days=7)
            labels.append('Wk ' + cur.strftime('%Y-%m-%d'))
            buckets.append((cur, nxt))
            cur = nxt
    else:
        # month buckets
        cur = date(start.year, start.month, 1)
        while cur <= date(end.year, end.month, 1):
            from calendar import monthrange
            last_day = monthrange(cur.year, cur.month)[1]
            s = datetime(cur.year, cur.month, 1)
            e = s.replace(day=last_day) + timedelta(days=1)
            labels.append(cur.strftime('%b %Y'))
            buckets.append((s, e))
            # next month
            if cur.month == 12:
                cur = date(cur.year+1, 1, 1)
            else:
                cur = date(cur.year, cur.month+1, 1)
    # Fetch data in one go and bucket in Python
    orders_q = Order.query.filter(Order.created_at >= buckets[0][0], Order.created_at < buckets[-1][1]).all() if buckets else []
    users_q = User.query.filter(User.created_at >= buckets[0][0], User.created_at < buckets[-1][1]).all() if buckets else []
    products_q = Product.query.filter(Product.created_at >= buckets[0][0], Product.created_at < buckets[-1][1]).all() if buckets else []
    sales = [0.0 for _ in buckets]
    orders = [0 for _ in buckets]
    users = [0 for _ in buckets]
    products = [0 for _ in buckets]
    def find_bucket(dt):
        for i,(s,e) in enumerate(buckets):
            if s <= dt < e:
                return i
        return None
    for o in orders_q:
        if not o.created_at: continue
        i = find_bucket(o.created_at)
        if i is None: continue
        try:
            sales[i] += float(o.total_amount or 0)
        except Exception:
            pass
        try:
            orders[i] += 1
        except Exception:
            pass
    for u in users_q:
        if not u.created_at: continue
        i = find_bucket(u.created_at)
        if i is None: continue
        users[i] += 1
    for p in products_q:
        if not p.created_at: continue
        i = find_bucket(p.created_at)
        if i is None: continue
        products[i] += 1
    # Derived metrics
    aov = [ (sales[i]/orders[i]) if orders[i] else 0 for i in range(len(buckets)) ]
    # conversion approximated as orders/new users; avoid div by zero
    conversion = [ (orders[i]/users[i])*100 if users[i] else 0 for i in range(len(buckets)) ]
    payload = {
        'labels': labels,
        'sales': [round(x,2) for x in sales],
        'orders': orders,
        'users': users,
        'products': products,
        'aov': [round(x,2) for x in aov],
        'conversion': [round(x,2) for x in conversion],
    }
    return Response(json.dumps(payload), mimetype='application/json')

# --- Coupons management ---
@admin_bp.route("/coupons", methods=["GET", "POST"])
@csrf.exempt
@login_required
@admin_required
def coupons():
    if request.method == 'POST':
        code = (request.form.get('code') or '').strip().upper()
        discount_percent = request.form.get('discount_percent', type=int)
        discount_amount = request.form.get('discount_amount', type=float)
        min_order_value = request.form.get('min_order_value', type=float)
        is_active = (request.form.get('is_active') or '') in {'1','true','on','yes'}
        if not code:
            flash('Coupon code is required', 'warning')
            return redirect(url_for('admin.coupons'))
        if Coupon.query.filter_by(code=code).first():
            flash('Coupon code already exists', 'warning')
            return redirect(url_for('admin.coupons'))
        c = Coupon(
            code=code,
            discount_percent=discount_percent or 0,
            discount_amount=discount_amount or 0,
            min_order_value=min_order_value or 0,
            is_active=is_active
        )
        db.session.add(c)
        db.session.commit()
        flash('Coupon created', 'success')
        return redirect(url_for('admin.coupons'))
    q = (request.args.get('q') or '').strip()
    query = Coupon.query
    if q:
        like = f"%{q}%"
        query = query.filter(Coupon.code.ilike(like))
    items = query.order_by(Coupon.created_at.desc()).all() if hasattr(Coupon, 'created_at') else query.all()
    return render_template('admin/coupons.html', coupons=items, q=q)

@admin_bp.route('/coupons/<int:coupon_id>/edit', methods=['GET','POST'])
@csrf.exempt
@login_required
@admin_required
def edit_coupon(coupon_id):
    c = db.session.get(Coupon, coupon_id)
    if not c:
        abort(404)
    if request.method == 'POST':
        c.code = (request.form.get('code') or c.code).strip().upper()
        c.discount_percent = request.form.get('discount_percent', type=int) or 0
        c.discount_amount = request.form.get('discount_amount', type=float) or 0
        c.min_order_value = request.form.get('min_order_value', type=float) or 0
        c.is_active = (request.form.get('is_active') or '') in {'1','true','on','yes'}
        db.session.commit()
        flash('Coupon saved', 'success')
        return redirect(url_for('admin.coupons'))
    return render_template('admin/coupon_edit.html', coupon=c)

@admin_bp.route('/coupons/<int:coupon_id>/toggle', methods=['POST'])
@csrf.exempt
@login_required
@admin_required
def toggle_coupon(coupon_id):
    c = db.session.get(Coupon, coupon_id)
    if not c:
        abort(404)
    c.is_active = not bool(c.is_active)
    db.session.commit()
    return redirect(url_for('admin.coupons'))

@admin_bp.route('/coupons/<int:coupon_id>/delete', methods=['POST'])
@csrf.exempt
@login_required
@admin_required
def delete_coupon(coupon_id):
    c = db.session.get(Coupon, coupon_id)
    if not c:
        abort(404)
    db.session.delete(c)
    db.session.commit()
    flash('Coupon deleted', 'info')
    return redirect(url_for('admin.coupons'))

# --- Blog/CMS management ---
@admin_bp.route('/posts', methods=['GET','POST'])
@login_required
@admin_required
def posts():
    if request.method == 'POST':
        try:
            title = (request.form.get('title') or '').strip()
            slug = (request.form.get('slug') or '').strip().lower()
            body = request.form.get('body')
            image_url = (request.form.get('image_url') or '').strip()
            is_published = (request.form.get('is_published') or '') in {'1','true','on','yes'}
            if not title:
                flash('Title is required', 'warning')
                return redirect(url_for('admin.posts'))
            if not slug:
                import re
                slug = re.sub(r"[^a-z0-9\-]+","-", title.lower()).strip('-')
            if Post.query.filter_by(slug=slug).first():
                flash('Slug already exists', 'warning')
                return redirect(url_for('admin.posts'))
            p = Post(title=title, slug=slug, body=body, image_url=image_url, is_published=is_published)
            if is_published:
                from datetime import datetime
                p.published_at = datetime.utcnow()
            db.session.add(p)
            db.session.commit()
            flash('Post created', 'success')
            return redirect(url_for('admin.posts'))
        except Exception as e:
            db.session.rollback()
            flash('Cannot create post until the database is migrated (missing table). Please run migrations.', 'danger')
            return redirect(url_for('admin.posts'))
    q = (request.args.get('q') or '').strip()
    query = Post.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Post.title.ilike(like), Post.slug.ilike(like)))
    try:
        items = query.order_by(Post.created_at.desc()).all() if hasattr(Post, 'created_at') else query.all()
    except Exception:
        # Likely the posts table doesn't exist yet
        items = []
        flash('Blog posts table is not created yet. Run DB migrations to enable Blog.', 'warning')
    return render_template('admin/posts.html', posts=items, q=q)

@admin_bp.route('/settings', methods=['GET','POST'])
@login_required
@admin_required
def settings():
    inst = current_app.instance_path if hasattr(current_app, 'instance_path') else os.path.join(os.getcwd(), 'instance')
    os.makedirs(inst, exist_ok=True)
    path = os.path.join(inst, 'admin_settings.json')
    data = {}
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f) or {}
    except Exception:
        data = {}
    if request.method == 'POST':
        try:
            data['read_only'] = bool(request.form.get('read_only'))
            passphrase = (request.form.get('passphrase') or '').strip()
            if passphrase:
                data['delete_pass_hash'] = generate_password_hash(passphrase)
            # Site & contacts
            data['site_name'] = request.form.get('site_name') or data.get('site_name')
            data['contact_email'] = request.form.get('contact_email') or data.get('contact_email')
            data['contact_phone'] = request.form.get('contact_phone') or data.get('contact_phone')
            data['contact_address'] = request.form.get('contact_address') or data.get('contact_address')
            data['whatsapp_number'] = request.form.get('whatsapp_number') or data.get('whatsapp_number')
            # Checkout
            data['allow_cod'] = bool(request.form.get('allow_cod'))
            data['allow_pickup'] = bool(request.form.get('allow_pickup'))
            data['pickup_location'] = request.form.get('pickup_location') or ''
            try:
                data['free_delivery_threshold'] = float(request.form.get('free_delivery_threshold') or 0)
            except Exception:
                data['free_delivery_threshold'] = 0
            # Socials
            for key in ['social_facebook_url','social_instagram_url','social_twitter_url','social_whatsapp_url','social_tiktok_handle']:
                data[key] = request.form.get(key) or ''
            # Analytics
            data['google_tag_id'] = request.form.get('google_tag_id') or ''
            data['sentry_dsn'] = request.form.get('sentry_dsn') or ''
            # SMTP
            for key in ['smtp_host','smtp_port','smtp_username','smtp_password','smtp_sender','contact_to']:
                data[key] = request.form.get(key) or ''
            # Stripe
            for key in ['stripe_publishable_key','stripe_secret_key','stripe_webhook_secret']:
                data[key] = request.form.get(key) or ''
            # M-Pesa
            for key in ['mpesa_consumer_key','mpesa_consumer_secret','mpesa_short_code','mpesa_passkey','mpesa_callback_url','mpesa_base_url','mpesa_till_number','mpesa_transaction_type']:
                data[key] = request.form.get(key) or ''
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            try:
                current_app.config.update({
                    'SITE_NAME': data.get('site_name') or current_app.config.get('SITE_NAME'),
                    'CONTACT_EMAIL': data.get('contact_email') or current_app.config.get('CONTACT_EMAIL'),
                    'CONTACT_PHONE': data.get('contact_phone') or current_app.config.get('CONTACT_PHONE'),
                    'CONTACT_ADDRESS': data.get('contact_address') or current_app.config.get('CONTACT_ADDRESS'),
                    'WHATSAPP_NUMBER': data.get('whatsapp_number') or current_app.config.get('WHATSAPP_NUMBER'),
                    'FREE_DELIVERY_THRESHOLD': data.get('free_delivery_threshold') or 0,
                    'SOCIAL_FACEBOOK_URL': data.get('social_facebook_url'),
                    'SOCIAL_INSTAGRAM_URL': data.get('social_instagram_url'),
                    'SOCIAL_TWITTER_URL': data.get('social_twitter_url'),
                    'SOCIAL_WHATSAPP_URL': data.get('social_whatsapp_url'),
                    'SOCIAL_TIKTOK_HANDLE': data.get('social_tiktok_handle'),
                    'GOOGLE_TAG_ID': data.get('google_tag_id'),
                })
            except Exception:
                pass
            flash('Settings saved', 'success')
            return redirect(url_for('admin.settings'))
        except Exception:
            flash('Failed to save settings', 'danger')
            return redirect(url_for('admin.settings'))
    class Obj:
        def __init__(self, d):
            self.__dict__.update(d)
        def get(self, k, default=None):
            return getattr(self, k, default)
    settings_obj = Obj(data)
    return render_template('admin/settings.html', settings=settings_obj)

@admin_bp.route('/posts/<int:post_id>/edit', methods=['GET','POST'])
@login_required
@admin_required
def edit_post(post_id):
    p = db.session.get(Post, post_id)
    if not p:
        abort(404)
    if request.method == 'POST':
        p.title = request.form.get('title') or p.title
        p.slug = (request.form.get('slug') or p.slug).lower()
        p.body = request.form.get('body')
        p.image_url = request.form.get('image_url')
        was_published = bool(p.is_published)
        p.is_published = (request.form.get('is_published') or '') in {'1','true','on','yes'}
        if p.is_published and not was_published:
            from datetime import datetime
            p.published_at = datetime.utcnow()
        db.session.commit()
        flash('Post saved', 'success')
        return redirect(url_for('admin.posts'))
    return render_template('admin/post_edit.html', post=p)

@admin_bp.route('/posts/<int:post_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_post(post_id):
    p = db.session.get(Post, post_id)
    if not p:
        abort(404)
    p.is_published = not bool(p.is_published)
    if p.is_published and not p.published_at:
        from datetime import datetime
        p.published_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for('admin.posts'))

@admin_bp.route('/posts/<int:post_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_post(post_id):
    p = db.session.get(Post, post_id)
    if not p:
        abort(404)
    db.session.delete(p)
    db.session.commit()
    flash('Post deleted', 'info')
    return redirect(url_for('admin.posts'))
    # Build last 12 months buckets (oldest -> newest)
    def month_range(d: date):
        start = d.replace(day=1)
        last_day = calendar.monthrange(start.year, start.month)[1]
        end = start.replace(day=last_day) + timedelta(days=1)  # exclusive
        return start, end
    today = date.today()
    months = []
    for i in range(11, -1, -1):
        y = today.year
        m = today.month - i
        while m <= 0:
            m += 12
            y -= 1
        d = date(y, m, 1)
        months.append(d)
    labels = [d.strftime('%b %Y') for d in months]

    sales_series = []
    orders_series = []
    users_series = []
    products_series = []
    for d in months:
        start, end = month_range(d)
        # sales sum
        sales = db.session.query(db.func.coalesce(db.func.sum(Order.total_amount), 0))\
            .filter(Order.created_at >= start, Order.created_at < end).scalar() or 0
        sales_series.append(float(sales))
        # orders count
        oc = db.session.query(db.func.count(Order.id))\
            .filter(Order.created_at >= start, Order.created_at < end).scalar() or 0
        orders_series.append(int(oc))
        # users count
        uc = db.session.query(db.func.count(User.id))\
            .filter(User.created_at >= start, User.created_at < end).scalar() or 0
        users_series.append(int(uc))
        # products count
        pc = db.session.query(db.func.count(Product.id))\
            .filter(Product.created_at >= start, Product.created_at < end).scalar() or 0
        products_series.append(int(pc))
    # Active homepage banners for quick management preview
    active_banners = HomePageBanner.query.filter_by(is_active=True).order_by(HomePageBanner.sort_order.asc(), HomePageBanner.created_at.desc()).all()
    # Announcement bar messages from instance file
    promo_messages = [
        'Fresh groceries delivered to your doorstep—fast and affordable!',
        'Order today and enjoy same-day delivery across KU, Ruiru & Nairobi!',
        'Get the best prices on fruits, veggies, and household essentials!',
        'ScholaGro—We deliver exactly what you ordered, fresh and clean!',
        'Save more this season with our daily offers and discounts!'
    ]
    try:
        import os, json
        inst = current_app.instance_path if hasattr(current_app, 'instance_path') else os.path.join(os.getcwd(), 'instance')
        os.makedirs(inst, exist_ok=True)
        p = os.path.join(inst, 'announcements.json')
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    promo_messages = [str(x) for x in data if str(x).strip()]
    except Exception:
        pass

    return render_template(
        "admin/dashboard.html",
        product_count=product_count,
        order_count=order_count,
        user_count=user_count,
        total_sales=total_sales,
        recent_orders=recent_orders,
        recent_payments=recent_payments,
        latest_reviews=latest_reviews,
        revenue_by_zone=revenue_by_zone,
        chart_labels=labels,
        chart_sales=sales_series,
        chart_orders=orders_series,
        chart_users=users_series,
        chart_products=products_series,
        active_banners=active_banners,
        promo_messages=promo_messages,
    )

@admin_bp.route("/announcements", methods=["GET", "POST"])
@login_required
@admin_required
def announcements():
    from flask import request
    msgs = []
    default_msgs = [
        'Fresh groceries delivered to your doorstep—fast and affordable!',
        'Order today and enjoy same-day delivery across KU, Ruiru & Nairobi!',
        'Get the best prices on fruits, veggies, and household essentials!',
        'ScholaGro—We deliver exactly what you ordered, fresh and clean!',
        'Save more this season with our daily offers and discounts!'
    ]
    try:
        import os, json
        inst = current_app.instance_path if hasattr(current_app, 'instance_path') else os.path.join(os.getcwd(), 'instance')
        os.makedirs(inst, exist_ok=True)
        path = os.path.join(inst, 'announcements.json')
        if request.method == 'POST':
            raw = (request.form.get('messages') or '').splitlines()
            msgs = [s.strip() for s in raw if s and s.strip()]
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(msgs, f, ensure_ascii=False, indent=2)
            try: cache.clear()
            except Exception: pass
            flash('Announcements saved', 'success')
            return redirect(url_for('admin.announcements'))
        else:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        msgs = [str(x) for x in data]
            if not msgs:
                msgs = default_msgs
    except Exception:
        msgs = default_msgs
    return render_template('admin/announcements.html', messages=msgs)
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
        name = (request.form.get("name") or '').strip()
        price = request.form.get("price")
        # normalize numeric fields
        try:
            price = float(price)
        except Exception:
            price = None
        stock = request.form.get("stock", type=int)
        category_id = request.form.get("category_id")
        try:
            category_id = int(category_id) if category_id is not None else None
        except Exception:
            category_id = None
        image_url = (request.form.get("image_url") or '').strip()
        # slugify: lowercase, hyphenate spaces, remove invalid chars
        import re
        raw_slug = (request.form.get("slug") or name).lower()
        raw_slug = re.sub(r"[^a-z0-9\s-]", "", raw_slug)
        raw_slug = re.sub(r"\s+", "-", raw_slug).strip("-")
        slug = raw_slug or 'product'
        # ensure unique slug
        if Product.query.filter_by(slug=slug).first():
            base = slug
            i = 2
            while Product.query.filter_by(slug=f"{base}-{i}").first():
                i += 1
            slug = f"{base}-{i}"
        # Optional file upload overrides image_url
        file = request.files.get("image_file")
        if file and file.filename:
            uploaded = upload_image(file, folder="scholagro/products")
            if uploaded:
                image_url = uploaded
        p = Product(name=name, price=price, category_id=category_id, slug=slug, image_url=image_url, stock=stock or 0)
        # new admin flags
        try:
            p.is_top_pick = bool(request.form.get('is_top_pick'))
            p.is_new_arrival_featured = bool(request.form.get('is_new_arrival_featured'))
        except Exception:
            pass
        db.session.add(p)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash("Could not add product. Please check inputs and try again.", "danger")
            return redirect(url_for("admin.products"))
        try:
            index_product(p)
        except Exception:
            pass
        try: cache.clear()
        except Exception: pass
        flash("Product added", "success")
    categories = Category.query.all()
    q = (request.args.get('q') or '').strip()
    page = max(1, request.args.get('page', type=int, default=1))
    per_page = request.args.get('per_page', type=int, default=50)
    query = Product.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Product.name.ilike(like), Product.slug.ilike(like)))
    total = query.count()
    products = query.order_by(Product.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()
    return render_template("admin/products.html", products=products, categories=categories, total=total, page=page, per_page=per_page, q=q)


@admin_bp.route('/products/top-picks', methods=['GET'])
@login_required
@admin_required
def top_picks_page():
    # Show a management view for top picks
    q = (request.args.get('q') or '').strip()
    page = max(1, request.args.get('page', type=int, default=1))
    per_page = request.args.get('per_page', type=int, default=200)
    query = Product.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Product.name.ilike(like), Product.slug.ilike(like)))
    total = query.count()
    products = query.order_by(Product.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()
    # Prepare list of all product ids for clear-all action
    # include all product ids for clear-all convenience; if DB large, consider paginated clear
    all_ids = [p.id for p in Product.query.with_entities(Product.id).all()]
    return render_template('admin/top_picks.html', products=products, total=total, page=page, per_page=per_page, q=q, all_product_ids=all_ids)


@admin_bp.route("/orders")
@login_required
@admin_required
def orders():
    q = (request.args.get('q') or '').strip()
    page = max(1, request.args.get('page', type=int, default=1))
    per_page = request.args.get('per_page', type=int, default=50)
    query = Order.query
    if q:
        like = f"%{q}%"
        # search by id, user email, or status
        query = query.join(User, isouter=True).filter(db.or_(
            Order.id.cast(db.String).ilike(like),
            User.email.ilike(like),
            Order.status.ilike(like)
        ))
    total = query.count()
    orders = query.order_by(Order.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()
    try:
        from ...models import Rider
        riders = Rider.query.filter_by(is_active=True).order_by(Rider.name.asc()).all()
    except Exception:
        riders = []
    return render_template("admin/orders.html", orders=orders, riders=riders, total=total, page=page, per_page=per_page, q=q)


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

    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
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

    try:
        dest_phone = getattr(order.user, 'phone', None)
        if dest_phone:
            from flask import current_app
            msg = f"Order #{order.id} status: {new_status.replace('_',' ').title()}"
            try:
                sid = current_app.config.get('TWILIO_ACCOUNT_SID')
                tok = current_app.config.get('TWILIO_AUTH_TOKEN')
                wa_from = current_app.config.get('TWILIO_WHATSAPP_FROM')  # e.g. 'whatsapp:+14155238886'
                if sid and tok and wa_from and dest_phone:
                    try:
                        from twilio.rest import Client  # type: ignore
                        client = Client(sid, tok)
                        to_wa = dest_phone
                        if to_wa.startswith('+'):
                            to_wa = to_wa
                        elif to_wa.startswith('0'):
                            to_wa = '+254' + to_wa[1:]
                        elif to_wa.startswith('254'):
                            to_wa = '+' + to_wa
                        client.messages.create(from_=wa_from, to='whatsapp:' + to_wa, body=msg)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                at_user = current_app.config.get('AFRICASTALKING_USERNAME')
                at_key = current_app.config.get('AFRICASTALKING_API_KEY')
                sender = current_app.config.get('SMS_SENDER_ID') or current_app.config.get('TWILIO_SMS_FROM')
                if at_user and at_key and sender:
                    try:
                        import africastalking  # type: ignore
                        africastalking.initialize(at_user, at_key)
                        sms = africastalking.SMS
                        to_sms = dest_phone
                        if to_sms.startswith('+'):
                            to_sms = to_sms
                        elif to_sms.startswith('0'):
                            to_sms = '+254' + to_sms[1:]
                        elif to_sms.startswith('254'):
                            to_sms = '+' + to_sms
                        sms.send(msg, [to_sms], sender)
                    except Exception:
                        pass
                elif current_app.config.get('TWILIO_ACCOUNT_SID') and current_app.config.get('TWILIO_AUTH_TOKEN') and current_app.config.get('TWILIO_SMS_FROM'):
                    try:
                        from twilio.rest import Client  # type: ignore
                        client = Client(current_app.config['TWILIO_ACCOUNT_SID'], current_app.config['TWILIO_AUTH_TOKEN'])
                        to_sms = dest_phone
                        if to_sms.startswith('+'):
                            to_sms = to_sms
                        elif to_sms.startswith('0'):
                            to_sms = '+254' + to_sms[1:]
                        elif to_sms.startswith('254'):
                            to_sms = '+' + to_sms
                        client.messages.create(from_=current_app.config['TWILIO_SMS_FROM'], to=to_sms, body=msg)
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass

    # Emit real-time notification for the user if socketio available
    try:
        if order.user_id:
            socketio.emit('order.status', {
                'order_id': order.id,
                'status': order.status,
            }, namespace='/', room=f'user_{order.user_id}')
            # Add notification entry
            try:
                db.session.add(Notification(user_id=order.user_id, title=f"Order #{order.id} status updated", message=f"Your order status is now {order.status.replace('_',' ')}", type='order_update'))
                db.session.commit()
            except Exception:
                db.session.rollback()
    except Exception:
        pass

    flash("Order status updated", "success")
    return redirect(url_for("admin.orders"))

@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_product(product_id):
    p = db.session.get(Product, product_id)
    if not p:
        abort(404)
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
        # admin-controlled flags
        try:
            p.is_top_pick = bool(request.form.get('is_top_pick'))
            p.is_new_arrival_featured = bool(request.form.get('is_new_arrival_featured'))
        except Exception:
            pass
        db.session.commit()
        try: cache.clear()
        except Exception: pass
        flash("Product updated", "success")
        try:
            index_product(p)
        except Exception:
            pass
        return redirect(url_for("admin.products"))
    categories = Category.query.all()
    return render_template("admin/product_edit.html", product=p, categories=categories)


@admin_bp.route("/products/<int:product_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_product(product_id):
    p = db.session.get(Product, product_id)
    if not p:
        abort(404)
    # If admin read-only, require passphrase
    try:
        inst = current_app.instance_path
        import json
        sfile = os.path.join(inst, 'admin_settings.json')
        if os.path.exists(sfile):
            with open(sfile, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        else:
            settings = {}
        if settings.get('read_only'):
            from werkzeug.security import check_password_hash
            passphrase = request.form.get('confirm_passphrase') or ''
            if not passphrase or not settings.get('delete_pass_hash') or not check_password_hash(settings.get('delete_pass_hash'), passphrase):
                flash('Admin read-only mode is enabled. Provide correct passphrase to delete this product.', 'danger')
                return redirect(url_for('admin.products'))
    except Exception:
        pass
    db.session.delete(p)
    db.session.commit()
    try: cache.clear()
    except Exception: pass
    flash("Product deleted", "info")
    return redirect(url_for("admin.products"))


@admin_bp.route("/products/bulk-delete", methods=["POST"])
@login_required
@admin_required
def bulk_delete_products():
    ids = request.form.getlist('ids') or request.form.getlist('ids[]')
    # If admin read-only mode is enabled, require passphrase
    try:
        inst = current_app.instance_path
        import json
        sfile = os.path.join(inst, 'admin_settings.json')
        if os.path.exists(sfile):
            with open(sfile, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        else:
            settings = {}
        if settings.get('read_only'):
            from werkzeug.security import check_password_hash
            passphrase = request.form.get('confirm_passphrase') or ''
            if not passphrase or not settings.get('delete_pass_hash') or not check_password_hash(settings.get('delete_pass_hash'), passphrase):
                flash('Admin read-only mode is enabled. Provide correct passphrase to delete products.', 'danger')
                return redirect(url_for('admin.products'))
    except Exception:
        pass
    # Normalize to ints and filter valid
    try:
        id_list = [int(x) for x in ids if str(x).isdigit()]
    except Exception:
        id_list = []
    if not id_list:
        flash("No products selected", "warning")
        return redirect(url_for("admin.products"))
    try:
        db.session.query(Product).filter(Product.id.in_(id_list)).delete(synchronize_session=False)
        db.session.commit()
        try: cache.clear()
        except Exception: pass
        flash(f"Deleted {len(id_list)} products", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to delete selected products", "danger")
    return redirect(url_for("admin.products"))


@admin_bp.route("/products/delete-all", methods=["POST"])
@login_required
@admin_required
def delete_all_products():
    confirm = (request.form.get('confirm') or '').lower() in {"1","true","yes","y"}
    # If read-only mode is enabled, require passphrase
    try:
        inst = current_app.instance_path
        import json
        sfile = os.path.join(inst, 'admin_settings.json')
        if os.path.exists(sfile):
            with open(sfile, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        else:
            settings = {}
        if settings.get('read_only'):
            from werkzeug.security import check_password_hash
            passphrase = request.form.get('confirm_passphrase') or ''
            if not passphrase or not settings.get('delete_pass_hash') or not check_password_hash(settings.get('delete_pass_hash'), passphrase):
                flash('Admin read-only mode is enabled. Provide correct passphrase to delete all products.', 'danger')
                return redirect(url_for('admin.products'))
    except Exception:
        pass
    if not confirm:
        flash("Confirmation required to delete all products", "warning")
        return redirect(url_for("admin.products"))
    try:
        db.session.query(Product).delete(synchronize_session=False)
        db.session.commit()
        try: cache.clear()
        except Exception: pass
        flash("All products deleted", "info")
    except Exception:
        db.session.rollback()
        flash("Failed to delete all products", "danger")
    return redirect(url_for("admin.products"))


@admin_bp.route('/products/<int:product_id>/toggle-top-pick', methods=['POST'])
@login_required
@admin_required
def toggle_top_pick(product_id):
    p = db.session.get(Product, product_id)
    if not p:
        return Response(json.dumps({'ok': False, 'error': 'Not found'}), status=404, mimetype='application/json')
    try:
        val = request.json.get('value') if request.is_json else (request.form.get('value') if request.method == 'POST' else None)
        # If value is not provided, toggle
        if val is None:
            p.is_top_pick = not bool(p.is_top_pick)
        else:
            p.is_top_pick = bool(val)
        db.session.add(p)
        db.session.commit()
        try: cache.clear()
        except Exception: pass
        return Response(json.dumps({'ok': True, 'is_top_pick': p.is_top_pick}), status=200, mimetype='application/json')
    except Exception:
        db.session.rollback()
        return Response(json.dumps({'ok': False, 'error': 'Failed to set value'}), status=500, mimetype='application/json')


@admin_bp.route('/products/<int:product_id>/toggle-new-arrival', methods=['POST'])
@login_required
@admin_required
def toggle_new_arrival(product_id):
    p = db.session.get(Product, product_id)
    if not p:
        return Response(json.dumps({'ok': False, 'error': 'Not found'}), status=404, mimetype='application/json')
    try:
        val = request.json.get('value') if request.is_json else (request.form.get('value') if request.method == 'POST' else None)
        if val is None:
            p.is_new_arrival_featured = not bool(p.is_new_arrival_featured)
        else:
            p.is_new_arrival_featured = bool(val)
        db.session.add(p)
        db.session.commit()
        try: cache.clear()
        except Exception: pass
        return Response(json.dumps({'ok': True, 'is_new_arrival_featured': p.is_new_arrival_featured}), status=200, mimetype='application/json')
    except Exception:
        db.session.rollback()
        return Response(json.dumps({'ok': False, 'error': 'Failed to set value'}), status=500, mimetype='application/json')


@admin_bp.route('/products/bulk-toggle-top-pick', methods=['POST'])
@login_required
@admin_required
def bulk_toggle_top_pick():
    # Accepts JSON { ids: [1,2,3] } or form data ids[]
    ids = request.json.get('ids') if request.is_json else request.form.getlist('ids') if request.method == 'POST' else []
    try:
        id_list = [int(x) for x in ids if str(x).isdigit()]
    except Exception:
        id_list = []
    if not id_list:
        return Response(json.dumps({'ok': False, 'error': 'No ids provided'}), status=400, mimetype='application/json')
    results = {}
    try:
        products = db.session.query(Product).filter(Product.id.in_(id_list)).all()
        for p in products:
            p.is_top_pick = not bool(p.is_top_pick)
            results[str(p.id)] = p.is_top_pick
            db.session.add(p)
        db.session.commit()
        try: cache.clear()
        except Exception: pass
        return Response(json.dumps({'ok': True, 'results': results}), status=200, mimetype='application/json')
    except Exception as e:
        db.session.rollback()
        return Response(json.dumps({'ok': False, 'error': 'Failed to toggle flags'}), status=500, mimetype='application/json')


@admin_bp.route('/products/bulk-set-top-pick', methods=['POST'])
@login_required
@admin_required
def bulk_set_top_pick():
    # Accepts JSON { ids: [1,2,3], value: true } or form data
    ids = request.json.get('ids') if request.is_json else request.form.getlist('ids') if request.method == 'POST' else []
    val = request.json.get('value') if request.is_json else (request.form.get('value') if request.method == 'POST' else None)
    try:
        val_bool = bool(val)
    except Exception:
        val_bool = False
    try:
        id_list = [int(x) for x in ids if str(x).isdigit()]
    except Exception:
        id_list = []
    if not id_list:
        return Response(json.dumps({'ok': False, 'error': 'No ids provided'}), status=400, mimetype='application/json')
    try:
        products = db.session.query(Product).filter(Product.id.in_(id_list)).all()
        for p in products:
            p.is_top_pick = val_bool
            db.session.add(p)
        db.session.commit()
        try: cache.clear()
        except Exception: pass
        results = {str(p.id): p.is_top_pick for p in products}
        return Response(json.dumps({'ok': True, 'results': results}), status=200, mimetype='application/json')
    except Exception:
        db.session.rollback()
        return Response(json.dumps({'ok': False, 'error': 'Failed to set flags'}), status=500, mimetype='application/json')


    @admin_bp.route('/products/bulk-toggle-new-arrival', methods=['POST'])
    @login_required
    @admin_required
    def bulk_toggle_new_arrival():
        ids = request.json.get('ids') if request.is_json else request.form.getlist('ids') if request.method == 'POST' else []
        try:
            id_list = [int(x) for x in ids if str(x).isdigit()]
        except Exception:
            id_list = []
        if not id_list:
            return Response(json.dumps({'ok': False, 'error': 'No ids provided'}), status=400, mimetype='application/json')
        results = {}
        try:
            products = db.session.query(Product).filter(Product.id.in_(id_list)).all()
            for p in products:
                p.is_new_arrival_featured = not bool(p.is_new_arrival_featured)
                results[str(p.id)] = p.is_new_arrival_featured
                db.session.add(p)
            db.session.commit()
            try: cache.clear()
            except Exception: pass
            return Response(json.dumps({'ok': True, 'results': results}), status=200, mimetype='application/json')
        except Exception:
            db.session.rollback()
            return Response(json.dumps({'ok': False, 'error': 'Failed to toggle flags'}), status=500, mimetype='application/json')


    @admin_bp.route('/products/bulk-set-new-arrival', methods=['POST'])
    @login_required
    @admin_required
    def bulk_set_new_arrival():
        ids = request.json.get('ids') if request.is_json else request.form.getlist('ids') if request.method == 'POST' else []
        val = request.json.get('value') if request.is_json else (request.form.get('value') if request.method == 'POST' else None)
        try:
            val_bool = bool(val)
        except Exception:
            val_bool = False
        try:
            id_list = [int(x) for x in ids if str(x).isdigit()]
        except Exception:
            id_list = []
        if not id_list:
            return Response(json.dumps({'ok': False, 'error': 'No ids provided'}), status=400, mimetype='application/json')
        try:
            products = db.session.query(Product).filter(Product.id.in_(id_list)).all()
            for p in products:
                p.is_new_arrival_featured = val_bool
                db.session.add(p)
            db.session.commit()
            try: cache.clear()
            except Exception: pass
            results = {str(p.id): p.is_new_arrival_featured for p in products}
            return Response(json.dumps({'ok': True, 'results': results}), status=200, mimetype='application/json')
        except Exception:
            db.session.rollback()
            return Response(json.dumps({'ok': False, 'error': 'Failed to set flags'}), status=500, mimetype='application/json')
    # end bulk_set_new_arrival


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
    c = db.session.get(Category, cat_id)
    if not c:
        abort(404)
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
    c = db.session.get(Category, cat_id)
    if not c:
        abort(404)
    db.session.delete(c)
    db.session.commit()
    try: cache.clear()
    except Exception: pass
    flash("Category deleted", "info")
    return redirect(url_for("admin.categories"))


@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_settings():
    inst = current_app.instance_path
    sfile = os.path.join(inst, 'admin_settings.json')
    settings = {}
    if os.path.exists(sfile):
        with open(sfile, 'r', encoding='utf-8') as f:
            try: settings = json.load(f)
            except Exception: settings = {}
    if request.method == 'POST':
        # Admin controls
        read_only = (request.form.get('read_only') or '').lower() in {'1','true','yes','on'}
        passphrase = (request.form.get('passphrase') or '').strip()
        if passphrase:
            settings['delete_pass_hash'] = generate_password_hash(passphrase)
        settings['read_only'] = bool(read_only)
        # Site & contact
        settings['site_name'] = (request.form.get('site_name') or '').strip()
        settings['contact_email'] = (request.form.get('contact_email') or '').strip()
        settings['contact_phone'] = (request.form.get('contact_phone') or '').strip()
        settings['contact_address'] = (request.form.get('contact_address') or '').strip()
        # Social links
        settings['social_facebook_url'] = (request.form.get('social_facebook_url') or '').strip()
        settings['social_instagram_url'] = (request.form.get('social_instagram_url') or '').strip()
        settings['social_twitter_url'] = (request.form.get('social_twitter_url') or '').strip()
        settings['social_whatsapp_url'] = (request.form.get('social_whatsapp_url') or '').strip()
        settings['social_tiktok_handle'] = (request.form.get('social_tiktok_handle') or '').strip()
        # Analytics / monitoring
        settings['google_tag_id'] = (request.form.get('google_tag_id') or '').strip()
        settings['sentry_dsn'] = (request.form.get('sentry_dsn') or '').strip()
        # Realtime (Socket.IO)
        settings['socketio_enabled'] = (request.form.get('socketio_enabled') or '').lower() in {'1','true','yes','on'}
        settings['socketio_async_mode'] = (request.form.get('socketio_async_mode') or '').strip()
        # Business comms & Checkout toggles
        settings['whatsapp_number'] = (request.form.get('whatsapp_number') or '').strip()
        settings['allow_cod'] = (request.form.get('allow_cod') or '').lower() in {'1','true','yes','on'}
        settings['allow_pickup'] = (request.form.get('allow_pickup') or '').lower() in {'1','true','yes','on'}
        settings['pickup_location'] = (request.form.get('pickup_location') or '').strip()
        # Promotions & delivery rules
        try:
            fdt = request.form.get('free_delivery_threshold')
            settings['free_delivery_threshold'] = float(fdt) if fdt not in (None, '') else None
        except Exception:
            settings['free_delivery_threshold'] = None
        # SMTP
        settings['smtp_host'] = (request.form.get('smtp_host') or '').strip()
        settings['smtp_port'] = request.form.get('smtp_port') or ''
        settings['smtp_username'] = (request.form.get('smtp_username') or '').strip()
        settings['smtp_password'] = (request.form.get('smtp_password') or '').strip()
        settings['smtp_sender'] = (request.form.get('smtp_sender') or '').strip()
        settings['contact_to'] = (request.form.get('contact_to') or '').strip()
        # Payments: Stripe
        settings['stripe_publishable_key'] = (request.form.get('stripe_publishable_key') or '').strip()
        settings['stripe_secret_key'] = (request.form.get('stripe_secret_key') or '').strip()
        settings['stripe_webhook_secret'] = (request.form.get('stripe_webhook_secret') or '').strip()
        # Payments: M-Pesa (Daraja)
        settings['mpesa_consumer_key'] = (request.form.get('mpesa_consumer_key') or '').strip()
        settings['mpesa_consumer_secret'] = (request.form.get('mpesa_consumer_secret') or '').strip()
        settings['mpesa_short_code'] = (request.form.get('mpesa_short_code') or '').strip()
        settings['mpesa_passkey'] = (request.form.get('mpesa_passkey') or '').strip()
        settings['mpesa_callback_url'] = (request.form.get('mpesa_callback_url') or '').strip()
        settings['mpesa_base_url'] = (request.form.get('mpesa_base_url') or '').strip()
        # Lipa na Till (Buy Goods) support
        settings['mpesa_till_number'] = (request.form.get('mpesa_till_number') or '').strip()
        settings['mpesa_transaction_type'] = (request.form.get('mpesa_transaction_type') or '').strip()  # CustomerPayBillOnline or CustomerBuyGoodsOnline
        os.makedirs(current_app.instance_path, exist_ok=True)
        with open(sfile, 'w', encoding='utf-8') as f:
            json.dump(settings, f)
        flash('Admin settings saved', 'success')
        try: cache.clear()
        except Exception: pass
        return redirect(url_for('admin.admin_settings'))
    return render_template('admin/settings.html', settings=settings)


@admin_bp.route('/orders/<int:order_id>/assign', methods=['POST'])
@login_required
@admin_required
def admin_assign_rider(order_id):
    from ...models import Rider, OrderStatusLog
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
    rider_id = request.form.get('rider_id', type=int)
    rider = db.session.get(Rider, rider_id) if rider_id else None
    if not rider:
        flash('Rider not found', 'danger')
        return redirect(url_for('admin.orders'))
    order.rider_id = rider.id
    try:
        db.session.add(OrderStatusLog(order_id=order.id, status=order.status or 'pending', notes=f'Rider assigned: {rider.name}'))
    except Exception:
        pass
    db.session.commit()
    try:
        if order.user_id:
            socketio.emit('order.rider_assigned', {
                'order_id': order.id,
                'rider': {'id': rider.id, 'name': rider.name, 'phone': rider.phone}
            }, namespace='/', room=f'user_{order.user_id}')
    except Exception:
        pass
    flash('Rider assigned', 'success')
    return redirect(url_for('admin.orders'))

@admin_bp.route('/settings/readonly_status', methods=['GET'])
@login_required
@admin_required
def admin_readonly_status():
    inst = current_app.instance_path
    sfile = os.path.join(inst, 'admin_settings.json')
    settings = {}
    if os.path.exists(sfile):
        with open(sfile, 'r', encoding='utf-8') as f:
            try: settings = json.load(f)
            except Exception: settings = {}
    return Response(json.dumps({'read_only': bool(settings.get('read_only'))}), status=200, mimetype='application/json')
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
        # Enforce a max of 10 active banners (prevent overpopulating hero carousel)
        active_count = HomePageBanner.query.filter_by(is_active=True).count()
        if active_count >= 10:
            flash("Cannot add more than 10 active banners. Please deactivate an existing banner first.", "warning")
            return redirect(url_for('admin.banners'))
        # Set default sort_order to append at the end
        try:
            max_sort = db.session.query(db.func.coalesce(db.func.max(HomePageBanner.sort_order), 0)).scalar() or 0
        except Exception:
            max_sort = 0
        new_sort = int(max_sort) + 1
        db.session.add(HomePageBanner(title=title, image_url=image_url, link_url=link_url, is_active=True, sort_order=new_sort))
        db.session.commit()
        try: cache.clear()
        except Exception: pass
        flash("Banner added", "success")
    banners = HomePageBanner.query.order_by(HomePageBanner.created_at.desc()).all()
    active_count = HomePageBanner.query.filter_by(is_active=True).count()
    return render_template("admin/banners.html", banners=banners, active_count=active_count)


@admin_bp.route("/banners/reorder", methods=["POST"])
@login_required
@admin_required
def banners_reorder():
    """Accept JSON array of banner ids in order to update sort_order.
    Example: {"order": [3,1,2]}
    """
    payload = request.get_json(silent=True) or {}
    order = payload.get('order') or []
    if not isinstance(order, (list, tuple)):
        return ("Bad Request", 400)
    try:
        # If the provided numbers are not valid banner IDs, treat them as indexes
        # into the current active banners list (ordered by sort_order).
        # This supports payloads that provide positions (e.g., [2,0,1]) or ids (e.g., [3,1,2]).
        existing = HomePageBanner.query.order_by(HomePageBanner.sort_order.asc(), HomePageBanner.created_at.asc()).all()
        id_set = {b.id for b in existing}
        use_indices = any((not isinstance(x, (int, str)) or (isinstance(x, (int)) and x not in id_set) or (isinstance(x, str) and not x.isdigit()) ) for x in order)
        if use_indices:
            # Interpret as indices into `existing` (0-based)
            resolved = []
            for idx in order:
                try:
                    i = int(idx)
                except Exception:
                    continue
                if 0 <= i < len(existing):
                    resolved.append(existing[i].id)
            order_ids = resolved
        else:
            order_ids = [int(x) for x in order if str(x).isdigit()]
        for idx, bid in enumerate(order_ids):
            b = db.session.get(HomePageBanner, int(bid))
            if not b:
                continue
            b.sort_order = int(idx)
            db.session.add(b)
        db.session.commit()
        try: cache.clear()
        except Exception: pass
        return ("OK", 200)
    except Exception as e:
        db.session.rollback()
        return ("Server Error", 500)

@admin_bp.route("/banners/<int:banner_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_banner(banner_id):
    b = db.session.get(HomePageBanner, banner_id)
    if not b:
        abort(404)
    b.is_active = not b.is_active
    db.session.commit()
    try:
        cache.clear()
    except Exception:
        pass
    flash("Banner updated", "success")
    return redirect(url_for("admin.banners"))

@admin_bp.route("/banners/<int:banner_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_banner(banner_id):
    b = db.session.get(HomePageBanner, banner_id)
    if not b:
        abort(404)
    db.session.delete(b)
    db.session.commit()
    try:
        cache.clear()
    except Exception:
        pass
    flash("Banner deleted", "info")
    return redirect(url_for("admin.banners"))


# ---- Flash Sales admin management ----
def check_flash_sale_overlap(product_id, starts_at, ends_at, exclude_fs_id=None):
    """Check if there's an overlapping flash sale for the product.
    Returns (has_overlap, overlapping_fs) tuple.
    """
    query = FlashSale.query.filter(
        FlashSale.product_id == product_id,
        FlashSale.is_active.is_(True),
        FlashSale.starts_at < ends_at,
        FlashSale.ends_at > starts_at,
    )
    if exclude_fs_id:
        query = query.filter(FlashSale.id != exclude_fs_id)
    overlapping = query.first()
    return (overlapping is not None, overlapping)


@admin_bp.route('/flash-sales', methods=['GET', 'POST'])
@login_required
@admin_required
def flash_sales():
    from datetime import datetime
    products = Product.query.order_by(Product.name.asc()).all()
    if request.method == 'POST':
        try:
            product_id = int(request.form.get('product_id') or 0)
            discount_percent = request.form.get('discount_percent')
            sale_price_in = request.form.get('sale_price')
            starts_at_raw = request.form.get('starts_at')
            ends_at_raw = request.form.get('ends_at')
            if not product_id or not (starts_at_raw and ends_at_raw):
                flash('Product, start and end date are required', 'warning')
                return redirect(url_for('admin.flash_sales'))
            starts_at = datetime.fromisoformat(starts_at_raw)
            ends_at = datetime.fromisoformat(ends_at_raw)
            if starts_at >= ends_at:
                flash('End time must be after start time', 'warning')
                return redirect(url_for('admin.flash_sales'))
            p = db.session.get(Product, product_id)
            if not p:
                flash('Product not found', 'warning')
                return redirect(url_for('admin.flash_sales'))
            # Check for overlapping sales
            has_overlap, overlap_fs = check_flash_sale_overlap(product_id, starts_at, ends_at)
            if has_overlap:
                flash(f'This product already has an active flash sale from {overlap_fs.starts_at} to {overlap_fs.ends_at}. Please adjust the time window or deactivate the existing sale.', 'warning')
                return redirect(url_for('admin.flash_sales'))
            # Determine sale price
            sale_price = None
            if sale_price_in:
                try:
                    sale_price = float(sale_price_in)
                except Exception:
                    sale_price = None
            if sale_price is None and discount_percent:
                try:
                    dp = float(discount_percent)
                    sale_price = float(p.price) * (1.0 - (dp/100.0))
                except Exception:
                    sale_price = None
            # Persist flash sale with original_price for safe reversion
            fs = FlashSale(product_id=product_id, discount_percent=int(discount_percent or 0), original_price=float(p.price), starts_at=starts_at, ends_at=ends_at, quantity_available=request.form.get('quantity_available') or None, is_active=True)
            # Update product prices to reflect sale immediately (store old_price)
            try:
                if p.old_price is None:
                    p.old_price = p.price
                if sale_price is not None:
                    p.price = round(sale_price, 2)
                db.session.add(p)
            except Exception:
                pass
            db.session.add(fs)
            db.session.commit()
            try:
                cache.clear()
            except Exception:
                pass
            flash('Flash sale created', 'success')
            return redirect(url_for('admin.flash_sales'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating flash sale: ' + str(e), 'danger')
            return redirect(url_for('admin.flash_sales'))
    # List existing flash sales (recent first)
    flash_sales = FlashSale.query.order_by(FlashSale.starts_at.desc()).all()
    return render_template('admin/flash_sales.html', products=products, flash_sales=flash_sales)


@admin_bp.route('/flash-sales/<int:fs_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_flash_sale(fs_id):
    from datetime import datetime
    fs = db.session.get(FlashSale, fs_id)
    if not fs:
        abort(404)
    products = Product.query.order_by(Product.name.asc()).all()
    if request.method == 'POST':
        try:
            product_id = int(request.form.get('product_id') or 0)
            discount_percent = request.form.get('discount_percent')
            sale_price_in = request.form.get('sale_price')
            starts_at_raw = request.form.get('starts_at')
            ends_at_raw = request.form.get('ends_at')
            if not product_id or not (starts_at_raw and ends_at_raw):
                flash('Product, start and end date are required', 'warning')
                return redirect(url_for('admin.edit_flash_sale', fs_id=fs_id))
            starts_at = datetime.fromisoformat(starts_at_raw)
            ends_at = datetime.fromisoformat(ends_at_raw)
            if starts_at >= ends_at:
                flash('End time must be after start time', 'warning')
                return redirect(url_for('admin.edit_flash_sale', fs_id=fs_id))
            p = db.session.get(Product, product_id)
            if not p:
                flash('Product not found', 'warning')
                return redirect(url_for('admin.edit_flash_sale', fs_id=fs_id))
            # Check for overlapping sales (excluding current one)
            has_overlap, overlap_fs = check_flash_sale_overlap(product_id, starts_at, ends_at, exclude_fs_id=fs_id)
            if has_overlap:
                flash(f'Another active flash sale exists from {overlap_fs.starts_at} to {overlap_fs.ends_at}. Please adjust the time window or deactivate the other sale.', 'warning')
                return redirect(url_for('admin.edit_flash_sale', fs_id=fs_id))
            # Update flash sale
            fs.product_id = product_id
            fs.discount_percent = int(discount_percent or 0)
            fs.starts_at = starts_at
            fs.ends_at = ends_at
            fs.quantity_available = request.form.get('quantity_available') or None
            # Revert old product price if product changed
            if fs.product_id != product_id and fs.original_price:
                old_p = db.session.get(Product, fs.product_id)
                if old_p and old_p.old_price is not None:
                    old_p.price = old_p.old_price
                    old_p.old_price = None
                    db.session.add(old_p)
            # Apply new sale price to the product
            sale_price = None
            if sale_price_in:
                try:
                    sale_price = float(sale_price_in)
                except Exception:
                    sale_price = None
            if sale_price is None and discount_percent:
                try:
                    dp = float(discount_percent)
                    sale_price = float(p.price) * (1.0 - (dp/100.0))
                except Exception:
                    sale_price = None
            if p.old_price is None:
                p.old_price = p.price
            if sale_price is not None:
                p.price = round(sale_price, 2)
            fs.original_price = float(p.price)
            db.session.add(p)
            db.session.add(fs)
            db.session.commit()
            try:
                cache.clear()
            except Exception:
                pass
            flash('Flash sale updated', 'success')
            return redirect(url_for('admin.flash_sales'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating flash sale: ' + str(e), 'danger')
            return redirect(url_for('admin.edit_flash_sale', fs_id=fs_id))
    return render_template('admin/edit_flash_sale.html', fs=fs, products=products)


@admin_bp.route('/flash-sales/<int:fs_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_flash_sale(fs_id):
    fs = db.session.get(FlashSale, fs_id)
    if not fs:
        abort(404)
    # Restore original price using the stored original_price field
    try:
        p = fs.product
        if p and fs.original_price is not None:
            p.price = float(fs.original_price)
            p.old_price = None
            db.session.add(p)
        elif p and p.old_price is not None:
            # Fallback to old_price if original_price not set
            p.price = p.old_price
            p.old_price = None
            db.session.add(p)
    except Exception:
        pass
    db.session.delete(fs)
    db.session.commit()
    try:
        cache.clear()
    except Exception:
        pass
    flash('Flash sale deleted and product price restored', 'info')
    return redirect(url_for('admin.flash_sales'))


@admin_bp.route("/category-heroes", methods=["GET", "POST"])
@login_required
@admin_required
def category_heroes():
    categories = Category.query.order_by(Category.name.asc()).all()
    if request.method == "POST":
        category_id = request.form.get("category_id", type=int)
        image_url = (request.form.get("image_url") or '').strip()
        sort_order = request.form.get("sort_order", type=int) or 0
        is_active = request.form.get("is_active") == '1'
        starts_at = request.form.get("starts_at") or None
        ends_at = request.form.get("ends_at") or None
        # Optional file upload overrides image_url
        file = request.files.get("image_file")
        if file and file.filename:
            up = upload_image(file, folder="scholagro/category_heroes")
            if up:
                image_url = up
        if not category_id or not image_url:
            flash("Category and Image are required", "warning")
            return redirect(url_for("admin.category_heroes"))
        chi = CategoryHeroImage(category_id=category_id, image_url=image_url, sort_order=sort_order, is_active=is_active)
        # Parse datetimes if provided (YYYY-MM-DD HH:MM optional)
        from datetime import datetime
        for fld, val in (("starts_at", starts_at), ("ends_at", ends_at)):
            if val:
                try:
                    setattr(chi, fld, datetime.fromisoformat(val))
                except Exception:
                    pass
        db.session.add(chi)
        db.session.commit()
        flash("Hero image added", "success")
        return redirect(url_for("admin.category_heroes"))
    items = CategoryHeroImage.query.order_by(CategoryHeroImage.category_id.asc(), CategoryHeroImage.sort_order.asc(), CategoryHeroImage.created_at.desc()).all()
    return render_template("admin/category_hero.html", categories=categories, items=items)


@admin_bp.route("/category-heroes/<int:item_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_category_hero(item_id):
    it = db.session.get(CategoryHeroImage, item_id)
    if not it:
        abort(404)
    it.is_active = not it.is_active
    db.session.commit()
    flash("Hero image updated", "success")
    return redirect(url_for("admin.category_heroes"))


@admin_bp.route("/category-heroes/<int:item_id>/update", methods=["POST"])
@login_required
@admin_required
def update_category_hero(item_id):
    it = db.session.get(CategoryHeroImage, item_id)
    if not it:
        abort(404)
    it.sort_order = request.form.get("sort_order", type=int) or it.sort_order
    it.category_id = request.form.get("category_id", type=int) or it.category_id
    it.is_active = request.form.get("is_active") == '1'
    from datetime import datetime
    starts_at = request.form.get("starts_at") or None
    ends_at = request.form.get("ends_at") or None
    if starts_at:
        try: it.starts_at = datetime.fromisoformat(starts_at)
        except Exception: pass
    else:
        it.starts_at = None
    if ends_at:
        try: it.ends_at = datetime.fromisoformat(ends_at)
        except Exception: pass
    else:
        it.ends_at = None
    # optional replace image
    file = request.files.get("image_file")
    if file and file.filename:
        up = upload_image(file, folder="scholagro/category_heroes")
        if up:
            it.image_url = up
    db.session.commit()
    flash("Hero image saved", "success")
    return redirect(url_for("admin.category_heroes"))


@admin_bp.route("/category-heroes/<int:item_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_category_hero(item_id):
    it = db.session.get(CategoryHeroImage, item_id)
    if not it:
        abort(404)
    db.session.delete(it)
    db.session.commit()
    flash("Hero image deleted", "info")
    return redirect(url_for("admin.category_heroes"))


@admin_bp.route("/reviews/moderation")
@login_required
@admin_required
def reviews_moderation():
    pending = Review.query.filter(Review.is_approved.is_(False)).order_by(Review.created_at.desc()).all()
    return render_template("admin/reviews_moderation.html", reviews=pending)


@admin_bp.route("/reviews/<int:review_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_review(review_id):
    r = db.session.get(Review, review_id)
    if not r:
        abort(404)
    r.is_approved = True
    db.session.commit()
    flash("Review approved", "success")
    return redirect(url_for("admin.reviews_moderation"))


@admin_bp.route("/reviews/<int:review_id>/reject", methods=["POST"])
@login_required
@admin_required
def reject_review(review_id):
    r = db.session.get(Review, review_id)
    if not r:
        abort(404)
    # delete photos first
    try:
        ReviewPhoto.query.filter_by(review_id=review_id).delete()
    except Exception:
        pass
    db.session.delete(r)
    db.session.commit()
    flash("Review rejected and removed", "info")
    return redirect(url_for("admin.reviews_moderation"))
@admin_bp.route("/import", methods=["GET", "POST"])
@login_required
@admin_required
def bulk_import():
    scheduled = False
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("Please upload a CSV file", "warning")
            return redirect(url_for("admin.bulk_import"))
        # Save CSV for background processing
        import pathlib, time
        uploads_dir = pathlib.Path.cwd() / 'instance' / 'uploads' / 'imports'
        uploads_dir.mkdir(parents=True, exist_ok=True)
        ext = pathlib.Path(file.filename).suffix or '.csv'
        filename = f'import_{int(time.time())}' + (ext if ext.startswith('.') else f'.{ext}')
        dest = uploads_dir / filename
        file.save(str(dest))
        # Enqueue background task if available
        scheduled = False
        try:
            from ...tasks import bulk_import_task
            if bulk_import_task:
                bulk_import_task.delay(str(dest))
                scheduled = True
                flash("Import scheduled; check admin reports for progress.", "success")
            else:
                raise Exception('No celery task available')
        except Exception:
            # fallback to synchronous import if tasks aren't available
            import csv, io
            stream = io.StringIO(dest.read_text(encoding='utf-8'))
            reader = csv.DictReader(stream)
            created = 0
            for row in reader:
                name = row.get('name'); slug = row.get('slug') or (name or '').lower().replace(' ','-')
                price = row.get('price'); image_url = row.get('image_url'); stock = int(row.get('stock') or 0)
                cat_name = row.get('category');
                    # Enqueue background task if available
                if cat_name:
                    category = Category.query.filter_by(name=cat_name).first()
                    if not category:
                        category = Category(name=cat_name, slug=(cat_name or '').lower().replace(' ','-'))
                        db.session.add(category)
                        db.session.flush()
                if name and price:
                    if not Product.query.filter_by(slug=slug).first():
                        p = Product(name=name, slug=slug, price=price, image_url=image_url, stock=stock, category_id=category.id if category else None)
                        # fallback to synchronous import if tasks aren't available
                        import csv, io
                        created = 0
                        download_images = (request.form.get('download_images') or '') in {'1', 'true', 'on', 'yes'}
                        # Determine if CSV or JSON
                        ext = dest.suffix.lower()
                        if ext == '.json':
                            items = json.loads(dest.read_text(encoding='utf-8'))
                            for obj in items:
                                name = obj.get('name'); slug = obj.get('slug') or (name or '').lower().replace(' ','-')
                                price_raw = obj.get('price')
                                try:
                                    price = float(price_raw) if price_raw is not None and price_raw != '' else None
                                except Exception:
                                    price = None
                                image_url = obj.get('image_url')
                                try:
                                    stock = int(obj.get('stock') or 0)
                                except Exception:
                                    stock = 0
                                cat_name = obj.get('category') or obj.get('category_name')
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
                                        db.session.flush()
                                        created += 1
                                        # Process images array or string
                                        imgs_field = obj.get('images')
                                        if imgs_field:
                                            if isinstance(imgs_field, str):
                                                sep = '|' if '|' in imgs_field else ',' if ',' in imgs_field else ';'
                                                imgs = [s.strip() for s in imgs_field.split(sep) if s.strip()]
                                            else:
                                                imgs = imgs_field
                                            from ...models import ProductImage
                                            first = True
                                            for img in imgs:
                                                url = img
                                                if download_images and str(url).startswith('http'):
                                                    try:
                                                        import requests, pathlib
                                                        r = requests.get(url, timeout=10)
                                                        if r.status_code == 200:
                                                            # save to static/uploads/scholagro/products
                                                            updir = pathlib.Path.cwd() / 'static' / 'uploads' / 'scholagro' / 'products'
                                                            updir.mkdir(parents=True, exist_ok=True)
                                                            fname = os.path.basename(urlparse(url).path) or f'{slug}-{hash(url)}.jpg'
                                                            destp = updir / fname
                                                            if not destp.exists():
                                                                destp.write_bytes(r.content)
                                                            saved_url = '/static/uploads/scholagro/products/' + fname
                                                            url = saved_url
                                                    except Exception:
                                                        pass
                                                db.session.add(ProductImage(product_id=p.id, image_url=url, is_primary=first))
                                                first = False
                        else:
                            # CSV
                            stream = io.StringIO(dest.read_text(encoding='utf-8'))
                            reader = csv.DictReader(stream)
                            for row in reader:
                                name = row.get('name'); slug = row.get('slug') or (name or '').lower().replace(' ','-')
                                price_raw = row.get('price')
                                try:
                                    price = float(price_raw) if price_raw is not None and price_raw != '' else None
                                except Exception:
                                    price = None
                                image_url = row.get('image_url')
                                try:
                                    stock = int(row.get('stock') or 0)
                                except Exception:
                                    stock = 0
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
                                        db.session.flush()
                                        created += 1
                                        # process images column if provided
                                        imgs_field = row.get('images') or row.get('image_urls')
                                        if imgs_field:
                                            sep = '|' if '|' in imgs_field else ',' if ',' in imgs_field else ';'
                                            imgs = [s.strip() for s in imgs_field.split(sep) if s.strip()]
                                            from ...models import ProductImage
                                            first = True
                                            for img in imgs:
                                                url = img
                                                if download_images and str(url).startswith('http'):
                                                    try:
                                                        import requests, pathlib
                                                        r = requests.get(url, timeout=10)
                                                        if r.status_code == 200:
                                                            updir = pathlib.Path.cwd() / 'static' / 'uploads' / 'scholagro' / 'products'
                                                            updir.mkdir(parents=True, exist_ok=True)
                                                            fname = os.path.basename(urlparse(url).path) or f'{slug}-{hash(url)}.jpg'
                                                            destp = updir / fname
                                                            if not destp.exists():
                                                                destp.write_bytes(r.content)
                                                            saved_url = '/static/uploads/scholagro/products/' + fname
                                                            url = saved_url
                                                    except Exception:
                                                        pass
                                                db.session.add(ProductImage(product_id=p.id, image_url=url, is_primary=first))
                                                first = False
                        db.session.commit()
                        flash(f"Imported {created} products", "success")
                        return redirect(url_for('admin.products'))
    # end POST handling
    if scheduled:
        return redirect(url_for('admin.products'))
    # If we didn't POST (or nothing scheduled) show the import page
    return render_template('admin/import.html')
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
    qparam = (request.args.get('q') or '').strip()
    page = max(1, request.args.get('page', type=int, default=1))
    per_page = request.args.get('per_page', type=int, default=50)
    q = Payment.query.order_by(Payment.created_at.desc())
    status = request.args.get('status')
    if status:
        q = q.filter_by(status=status)
    if qparam:
        like = f"%{qparam}%"
        q = q.join(Order, isouter=True).filter(db.or_(
            Payment.id.cast(db.String).ilike(like),
            Payment.reference.ilike(like),
            Payment.method.ilike(like),
            Payment.status.ilike(like),
            Order.id.cast(db.String).ilike(like)
        ))
    total = q.count()
    items = q.offset((page-1)*per_page).limit(per_page).all()
    return render_template("admin/payments.html", payments=items, status=status, total=total, page=page, per_page=per_page, q=qparam)


@admin_bp.route('/riders/<int:rider_id>/location', methods=['POST'])
@login_required
@admin_required
def update_rider_location(rider_id):
    from ...models import Rider
    data = request.get_json(silent=True) or {}
    lat = data.get('lat')
    lon = data.get('lon')
    if lat is None or lon is None:
        flash('Invalid location', 'danger')
        return redirect(url_for('admin.analytics'))
    r = db.session.get(Rider, rider_id)
    if not r:
        abort(404)
    try:
        r.current_location = json.dumps({'lat': float(lat), 'lon': float(lon)})
        db.session.commit()
        socketio.emit('rider.location', {'rider_id': r.id, 'location': {'lat': float(lat), 'lon': float(lon)}}, namespace='/', room=f'rider_{r.id}')
        flash('Rider location updated', 'success')
    except Exception:
        db.session.rollback()
        flash('Unable to update rider', 'danger')
    return redirect(url_for('admin.analytics'))

@admin_bp.route("/reports/payments.csv")
@login_required
@admin_required
def payments_report_csv():
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["PaymentID","OrderID","Method","Reference","Amount","Status","CreatedAt"])
    qparam = (request.args.get('q') or '').strip()
    status = request.args.get('status')
    q = Payment.query
    if status:
        q = q.filter_by(status=status)
    if qparam:
        like = f"%{qparam}%"
        q = q.join(Order, isouter=True).filter(db.or_(
            Payment.id.cast(db.String).ilike(like),
            Payment.reference.ilike(like),
            Payment.method.ilike(like),
            Payment.status.ilike(like),
            Order.id.cast(db.String).ilike(like)
        ))
    for p in q.order_by(Payment.created_at.desc()).all():
        writer.writerow([p.id, (p.order_id or ''), p.method, (p.reference or ''), p.amount, p.status, p.created_at])
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=payments.csv'})


@admin_bp.route("/products/export")
@login_required
@admin_required
def export_products_csv():
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name","slug","category_name","category_slug","price","list_price","image_url","images","stock","created_at"])
    from ...models import ProductImage
    for p in Product.query.join(Category, isouter=True).order_by(Product.created_at.desc()).all():
        images = ProductImage.query.filter_by(product_id=p.id).order_by(ProductImage.is_primary.desc(), ProductImage.created_at.desc()).all()
        images_str = '|'.join([img.image_url for img in images]) if images else ''
        writer.writerow([
            p.name,
            p.slug,
            (p.category.name if p.category else ''),
            (p.category.slug if p.category else ''),
            (p.price if p.price is not None else ''),
            (p.old_price if getattr(p, 'old_price', None) is not None else ''),
            (p.image_url or ''),
            images_str,
            p.stock,
            p.created_at,
        ])
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=products.csv'})


@admin_bp.route("/products/export.json")
@login_required
@admin_required
def export_products_json():
    products = []
    from ...models import ProductImage
    for p in Product.query.join(Category, isouter=True).order_by(Product.created_at.desc()).all():
        images = ProductImage.query.filter_by(product_id=p.id).order_by(ProductImage.is_primary.desc(), ProductImage.created_at.desc()).all()
        img_list = [i.image_url for i in images]
        products.append({
            'id': p.id,
            'name': p.name,
            'slug': p.slug,
            'category_name': (p.category.name if p.category else ''),
            'category_slug': (p.category.slug if p.category else ''),
            'price': str(p.price) if p.price is not None else None,
            'list_price': str(getattr(p, 'old_price', None)) if getattr(p, 'old_price', None) is not None else None,
            'image_url': p.image_url,
            'images': img_list,
            'stock': p.stock,
            'created_at': p.created_at.isoformat() if p.created_at else None,
        })
    return Response(json.dumps(products, ensure_ascii=False, indent=2), mimetype='application/json', headers={'Content-Disposition': 'attachment; filename=products.json'})


@admin_bp.route('/products/print')
@login_required
@admin_required
def products_print_view():
    from ...models import ProductImage
    items = []
    for p in Product.query.join(Category, isouter=True).order_by(Product.created_at.desc()).all():
        images = ProductImage.query.filter_by(product_id=p.id).order_by(ProductImage.is_primary.desc(), ProductImage.created_at.desc()).all()
        items.append({
            'id': p.id,
            'name': p.name,
            'slug': p.slug,
            'category_name': (p.category.name if p.category else ''),
            'category_slug': (p.category.slug if p.category else ''),
            'price': p.price,
            'image_url': p.image_url,
            'images': [i.image_url for i in images],
        })
    return render_template('admin/products_print.html', products=items)


# --- Reviews management ---
@admin_bp.route("/reviews")
@login_required
@admin_required
def reviews():
    q = (request.args.get('q') or '').strip()
    page = max(1, request.args.get('page', type=int, default=1))
    per_page = request.args.get('per_page', type=int, default=50)
    query = Review.query.join(User, Review.user_id == User.id).join(Product, Review.product_id == Product.id)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(User.email.ilike(like), Product.name.ilike(like), Review.comment.ilike(like)))
    total = query.count()
    items = query.order_by(Review.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()
    return render_template("admin/reviews.html", reviews=items, total=total, page=page, per_page=per_page, q=q)

@admin_bp.route("/reviews/<int:review_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_review(review_id):
    r = db.session.get(Review, review_id)
    if not r:
        abort(404)
    db.session.delete(r)
    db.session.commit()
    flash("Review deleted", "info")
    return redirect(url_for("admin.reviews"))


# --- Users management ---
@admin_bp.route("/users", methods=["GET", "POST"])
@login_required
@admin_required
def users():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password') or '';
        name = request.form.get('name') or ''
        is_admin = True if request.form.get('is_admin') == 'on' else False
        if not email or not password:
            flash("Email and password are required", "warning")
        elif User.query.filter_by(email=email).first():
            flash("User already exists", "warning")
        else:
            u = User(email=email, password_hash=generate_password_hash(password), name=name, is_admin=is_admin)
            db.session.add(u)
            db.session.commit()
            flash("User created", "success")
        return redirect(url_for('admin.users'))
    q = (request.args.get('q') or '').strip()
    page = max(1, request.args.get('page', type=int, default=1))
    per_page = request.args.get('per_page', type=int, default=50)
    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(User.email.ilike(like), User.name.ilike(like)))
    total = query.count()
    items = query.order_by(User.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()
    return render_template("admin/users.html", users=items, total=total, page=page, per_page=per_page, q=q)

@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    if current_user.id == user_id:
        flash("You cannot delete your own account from here", "warning")
        return redirect(url_for('admin.users'))
    u = db.session.get(User, user_id)
    if not u:
        abort(404)
    db.session.delete(u)
    db.session.commit()
    flash("User deleted", "info")
    return redirect(url_for('admin.users'))


# --- Delivery Zones management ---
@admin_bp.route("/delivery-zones", methods=["GET", "POST"])
@login_required
@admin_required
def delivery_zones():
    if request.method == "POST":
        name = (request.form.get("name") or '').strip()
        fee = request.form.get("fee", type=float)
        eta = (request.form.get("eta") or '').strip()

        if not name:
            flash("Zone name is required", "danger")
        elif not fee or fee < 0:
            flash("Valid delivery fee is required", "danger")
        else:
            if DeliveryZone.query.filter_by(name=name).first():
                flash("Zone name already exists", "warning")
            else:
                zone = DeliveryZone(name=name, fee=fee, eta=eta)
                db.session.add(zone)
                db.session.commit()
                try: cache.clear()
                except Exception: pass
                flash("Delivery zone added", "success")
        return redirect(url_for("admin.delivery_zones"))

    zones = DeliveryZone.query.order_by(DeliveryZone.name.asc()).all()
    return render_template("admin/delivery_zones.html", zones=zones)


@admin_bp.route("/delivery-zones/<int:zone_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_delivery_zone(zone_id):
    zone = db.session.get(DeliveryZone, zone_id)
    if not zone:
        abort(404)

    if request.method == "POST":
        name = (request.form.get("name") or '').strip()
        fee = request.form.get("fee", type=float)
        eta = (request.form.get("eta") or '').strip()

        if not name:
            flash("Zone name is required", "danger")
        elif not fee or fee < 0:
            flash("Valid delivery fee is required", "danger")
        else:
            # Check if name conflicts with another zone
            existing = DeliveryZone.query.filter_by(name=name).first()
            if existing and existing.id != zone_id:
                flash("Zone name already exists", "warning")
            else:
                zone.name = name
                zone.fee = fee
                zone.eta = eta
                db.session.commit()
                try: cache.clear()
                except Exception: pass
                flash("Delivery zone updated", "success")
                return redirect(url_for("admin.delivery_zones"))

    return render_template("admin/delivery_zone_edit.html", zone=zone)


@admin_bp.route("/delivery-zones/<int:zone_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_delivery_zone(zone_id):
    zone = db.session.get(DeliveryZone, zone_id)
    if not zone:
        abort(404)

    # Check if zone is being used by any orders
    if Order.query.filter_by(delivery_zone_id=zone_id).first():
        flash("Cannot delete zone that has associated orders", "danger")
        return redirect(url_for("admin.delivery_zones"))

    db.session.delete(zone)
    db.session.commit()
    try: cache.clear()
    except Exception: pass
    flash("Delivery zone deleted", "info")
    return redirect(url_for("admin.delivery_zones"))
