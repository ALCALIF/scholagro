import os
from flask import Flask, request, render_template
from .extensions import db, migrate, login_manager, csrf, cache, socketio
from .tasks import init_celery
from .config import get_config
from .blueprints.auth.routes import auth_bp
from .blueprints.shop.routes import shop_bp
from .blueprints.cart.routes import cart_bp
from .blueprints.orders.routes import orders_bp
from .blueprints.admin.routes import admin_bp
from .blueprints.payments.routes import payments_bp
from .blueprints.wishlist.routes import wishlist_bp
from .api import api_bp
from .blueprints.account.routes import account_bp


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(get_config())
    # Load admin instance settings to override config (if present)
    try:
        import json
        os.makedirs(app.instance_path, exist_ok=True)
        sfile = os.path.join(app.instance_path, 'admin_settings.json')
        if os.path.exists(sfile):
            with open(sfile, 'r', encoding='utf-8') as f:
                data = json.load(f) or {}
                if isinstance(data, dict):
                    # Flatten known keys onto app.config
                    for k, v in data.items():
                        key = str(k).upper()
                        app.config[key] = v
    except Exception:
        pass
    # Ensure default WhatsApp number if not configured and compute wa.me-friendly digits
    try:
        app.config.setdefault('WHATSAPP_NUMBER', '0757391071')
        def _wa_digits(n: str) -> str:
            if not n:
                return ''
            s = ''.join(ch for ch in str(n) if ch.isdigit() or ch == '+')
            s = s.replace('+', '')
            if s.startswith('0'):
                # assume KE local and convert to 254
                s = '254' + s[1:]
            elif s.startswith('7') and len(s) == 9:
                s = '254' + s
            # if already starts with country code, keep as is
            return s
        app.config['WHATSAPP_NUMBER_WA'] = _wa_digits(app.config.get('WHATSAPP_NUMBER'))
    except Exception:
        pass
    
    # Add dict filter to Jinja2 environment
    @app.template_filter('dict')
    def dict_filter(value=None, **kwargs):
        if value is not None:
            if kwargs:
                result = dict(value)
                result.update(kwargs)
                return result
            return dict(value)
        return kwargs

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    cache.init_app(app)
    try:
        # If Redis/broker configured, initialize celery tasks
        init_celery(app)
    except Exception:
        pass
    # SocketIO (optional) - initialize based on config
    try:
        enabled = app.config.get('SOCKETIO_ENABLED', True)
        if enabled:
            mode = app.config.get('SOCKETIO_ASYNC_MODE')
            if mode:
                socketio.init_app(app, async_mode=mode)
            else:
                socketio.init_app(app)
        # if disabled, skip init
    except Exception:
        pass
    # Rate limiter
    try:
        from .extensions import limiter
        limiter.init_app(app)
    except Exception:
        pass
    try:
        # import socket event handlers to register them
        from . import socket_events  # noqa: F401
    except Exception:
        pass

    # Sentry monitoring (optional)
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        dsn = app.config.get("SENTRY_DSN")
        if dsn:
            sentry_sdk.init(dsn=dsn, integrations=[FlaskIntegration()])
    except Exception:
        pass

    app.register_blueprint(auth_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(wishlist_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(api_bp)

    @app.context_processor
    def nav_context():
        from flask_login import current_user
        from .models import CartItem
        cart_count = 0
        if getattr(current_user, 'is_authenticated', False):
            try:
                cart_count = db.session.query(db.func.coalesce(db.func.sum(CartItem.quantity), 0)).filter_by(user_id=current_user.id).scalar() or 0
            except Exception:
                cart_count = 0
        # Pull dynamic site settings with sensible fallbacks
        site_name = app.config.get('SITE_NAME') or "ScholaGro"
        # Normalize Instagram: accept full URL or handle
        ig_raw = app.config.get('SOCIAL_INSTAGRAM_URL')
        ig_url = None
        try:
            if ig_raw:
                s = str(ig_raw).strip()
                if 'instagram.com' in s:
                    ig_url = s
                else:
                    handle = s.lstrip('@')
                    ig_url = f"https://instagram.com/{handle}"
        except Exception:
            ig_url = None
        if not ig_url:
            ig_url = 'https://instagram.com/scholah_meeme'

        wa_digits = app.config.get('WHATSAPP_NUMBER_WA') or '254757391071'
        socials = {
            'facebook_url': app.config.get('SOCIAL_FACEBOOK_URL') or 'https://facebook.com',
            'instagram_url': ig_url,
            'twitter_url': app.config.get('SOCIAL_TWITTER_URL') or 'https://twitter.com',
            'whatsapp_url': app.config.get('SOCIAL_WHATSAPP_URL') or f'https://wa.me/{wa_digits}',
            'tiktok_handle': app.config.get('SOCIAL_TIKTOK_HANDLE') or 'scholah_meeme',
        }
        return {"cart_count": int(cart_count), "site_name": site_name, "socials": socials, "config": app.config}

    @app.shell_context_processor
    def shell_ctx():
        from . import models
        return {"db": db, **{m.__name__: getattr(models, m.__name__) for m in models.__all__}}

    @app.context_processor
    def inject_csrf():
        from flask_wtf.csrf import generate_csrf
        from .utils.media import cl_transform
        from datetime import datetime, timedelta
        # Load announcement messages for the top marquee
        promo_messages = [
            'Fresh groceries delivered to your doorstep—fast and affordable!',
            'Order today and enjoy same-day delivery across KU, Ruiru & Nairobi!',
            'Get the best prices on fruits, veggies, and household essentials!',
            'ScholaGro—We deliver exactly what you ordered, fresh and clean!',
            'Save more this season with our daily offers and discounts!'
        ]
        try:
            import json
            inst = app.instance_path if hasattr(app, 'instance_path') else os.path.join(os.getcwd(), 'instance')
            os.makedirs(inst, exist_ok=True)
            p = os.path.join(inst, 'announcements.json')
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list) and data:
                        promo_messages = [str(x) for x in data if str(x).strip()]
        except Exception:
            pass
        return {"csrf_token": generate_csrf, "cl_transform": cl_transform, "datetime": datetime, "timedelta": timedelta, "promo_messages": promo_messages}

    @app.context_processor
    def feature_flags():
        cfg = app.config
        stripe_enabled = bool(cfg.get('STRIPE_SECRET_KEY') and cfg.get('STRIPE_PUBLISHABLE_KEY'))
        mpesa_enabled = bool(
            cfg.get('MPESA_CONSUMER_KEY') and cfg.get('MPESA_CONSUMER_SECRET') and
            cfg.get('MPESA_SHORT_CODE') and cfg.get('MPESA_PASSKEY') and cfg.get('MPESA_CALLBACK_URL')
        )
        return {"stripe_enabled": stripe_enabled, "mpesa_enabled": mpesa_enabled}

    @app.errorhandler(404)
    def not_found(e):
        # Use render_template so all context processors (including socials, config, etc.) are applied
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        # Use render_template so all context processors (including socials, config, etc.) are applied
        return render_template('500.html'), 500

    @app.after_request
    def set_security_headers(resp):
        resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
        resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        resp.headers.setdefault('Permissions-Policy', 'geolocation=(self), camera=()')
        # CSP allowing our own assets, CDNs, Safaricom sandbox, and ngrok for callbacks/testing
        csp = (
            "default-src 'self'; "
            "img-src 'self' https: data:; "
            "script-src 'self' https://cdn.jsdelivr.net https://cdn.socket.io; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "frame-src https://www.openstreetmap.org; "
            "connect-src 'self' https://cdn.jsdelivr.net https://sandbox.safaricom.co.ke https://*.ngrok.io https://*.ngrok-free.app wss://*.ngrok.io wss://*.ngrok-free.app;"
        )
        resp.headers.setdefault('Content-Security-Policy', csp)
        return resp

    # On first request, log DB URL and table list to aid diagnosis of missing tables
    @app.before_request
    def _log_db_state_once():
        # Log DB state once per process to aid debugging but avoid noise on every request
        if app.config.get('_db_state_logged'):  # whether we've already logged
            return
        try:
            from sqlalchemy import inspect
            engine = db.session.get_bind()
            insp = inspect(engine)
            tables = insp.get_table_names()
            app.logger.info('DB URL: %s', app.config.get('SQLALCHEMY_DATABASE_URI'))
            app.logger.info('DB tables present: %s', tables)
            if 'products' not in tables:
                app.logger.error("DB is missing 'products' table. Run migrations: 'flask db upgrade' or init with 'python -m scripts.init_db'.")
        except Exception:
            app.logger.exception('Could not inspect DB state')
        finally:
            app.config['_db_state_logged'] = True

    @app.route('/robots.txt')
    def robots_txt():
        content = """User-agent: *
Disallow:
Sitemap: /sitemap.xml
"""
        return app.response_class(content, mimetype='text/plain')

    @app.route('/sitemap.xml')
    def sitemap_xml():
        base = request.url_root.rstrip('/')
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{base}/</loc></url>
  <url><loc>{base}/shop</loc></url>
  <url><loc>{base}/orders</loc></url>
  <url><loc>{base}/pages/privacy</loc></url>
  <url><loc>{base}/pages/terms</loc></url>
</urlset>
"""
        return app.response_class(xml, mimetype='application/xml')

    return app

