import os
from flask import Flask
from .extensions import db, migrate, login_manager, csrf
from .config import get_config
from .blueprints.auth.routes import auth_bp
from .blueprints.shop.routes import shop_bp
from .blueprints.cart.routes import cart_bp
from .blueprints.orders.routes import orders_bp
from .blueprints.admin.routes import admin_bp
from .blueprints.payments.routes import payments_bp
from .blueprints.wishlist.routes import wishlist_bp
from .blueprints.account.routes import account_bp


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(get_config())
    
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
    from .extensions import cache
    cache.init_app(app)

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
        return {"cart_count": int(cart_count), "site_name": "ScholaGro"}

    @app.shell_context_processor
    def shell_ctx():
        from . import models
        return {"db": db, **{m.__name__: getattr(models, m.__name__) for m in models.__all__}}

    @app.context_processor
    def inject_csrf():
        from flask_wtf.csrf import generate_csrf
        from .utils.media import cl_transform
        from datetime import datetime, timedelta
        return {"csrf_token": generate_csrf, "cl_transform": cl_transform, "datetime": datetime, "timedelta": timedelta}

    @app.errorhandler(404)
    def not_found(e):
        from datetime import datetime, timedelta
        from flask_wtf.csrf import generate_csrf
        from flask_login import current_user
        from .utils.media import cl_transform
        from .models import CartItem
        cart_count = 0
        if getattr(current_user, 'is_authenticated', False):
            try:
                cart_count = db.session.query(db.func.coalesce(db.func.sum(CartItem.quantity), 0)).filter_by(user_id=current_user.id).scalar() or 0
            except Exception:
                cart_count = 0
        return app.jinja_env.get_template('404.html').render(
            datetime=datetime, timedelta=timedelta, csrf_token=generate_csrf, cl_transform=cl_transform,
            current_user=current_user, cart_count=int(cart_count), site_name="ScholaGro"
        ), 404

    @app.errorhandler(500)
    def server_error(e):
        from datetime import datetime, timedelta
        from flask_wtf.csrf import generate_csrf
        from flask_login import current_user
        from .utils.media import cl_transform
        from .models import CartItem
        cart_count = 0
        if getattr(current_user, 'is_authenticated', False):
            try:
                cart_count = db.session.query(db.func.coalesce(db.func.sum(CartItem.quantity), 0)).filter_by(user_id=current_user.id).scalar() or 0
            except Exception:
                cart_count = 0
        return app.jinja_env.get_template('500.html').render(
            datetime=datetime, timedelta=timedelta, csrf_token=generate_csrf, cl_transform=cl_transform,
            current_user=current_user, cart_count=int(cart_count), site_name="ScholaGro"
        ), 500

    @app.after_request
    def set_security_headers(resp):
        resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
        resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        resp.headers.setdefault('Permissions-Policy', 'geolocation=(self), camera=()')
        # Basic CSP allowing our own assets and common CDNs used in templates
        csp = "default-src 'self'; img-src 'self' https: data:; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; font-src 'self' https://fonts.gstatic.com; frame-src https://www.openstreetmap.org;"
        resp.headers.setdefault('Content-Security-Policy', csp)
        return resp

    return app
