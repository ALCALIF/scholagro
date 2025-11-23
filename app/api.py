from flask import Blueprint, jsonify, request
from .models import Product, Category, Order, User
from .extensions import db

api_bp = Blueprint('api', __name__, url_prefix='/api')

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
    user = User.query.get_or_404(user_id)
    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'phone': user.phone
    })
