from flask import Blueprint, jsonify, request, abort
from .models import Product, Category, Order, User
from .extensions import db

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/health', methods=['GET'])
def health():
    from .extensions import db, cache
    data = {'ok': True}
    try:
        db.session.execute('SELECT 1')
        data['db'] = True
    except Exception:
        data['db'] = False
    try:
        # ping cache if available
        c = cache.get if cache else None
        if c:
            cache.set('_hc', '1', timeout=5)
            cache.get('_hc')
            data['cache'] = True
        else:
            data['cache'] = None
    except Exception:
        data['cache'] = False
    try:
        # check Celery broker if configured
        from .celery_app import make_celery
        app = None
        try:
            from flask import current_app
            app = current_app._get_current_object()
        except Exception:
            app = None
        if app:
            celery = make_celery(app)
            data['celery_broker'] = celery.conf.broker_url is not None
        else:
            data['celery_broker'] = None
    except Exception:
        data['celery_broker'] = False
    return jsonify(data), 200


@api_bp.route('/products', methods=['GET'])
def get_products():
    products = Product.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'price': p.price,
        'stock': p.stock,
        'image_url': p.image_url,
        'category': p.category.name if p.category else None,
        'slug': p.slug
    } for p in products])

@api_bp.route('/categories', methods=['GET'])
def get_categories():
    categories = Category.query.all()
    return jsonify([{'id': c.id, 'name': c.name, 'slug': c.slug} for c in categories])

@api_bp.route('/orders/<int:user_id>', methods=['GET'])
def get_orders(user_id):
    orders = Order.query.filter_by(user_id=user_id).all()
    return jsonify([{
        'id': o.id,
        'status': o.status,
        'total_amount': o.total_amount,
        'created_at': o.created_at.isoformat()
    } for o in orders])

@api_bp.route('/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'phone': user.phone
    })
