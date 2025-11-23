from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from ...extensions import db
from ...models import User
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from ...utils.email import send_email_html
import time

_forgot_attempts = {}

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("shop.home"))
        flash("Invalid credentials", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        if User.query.filter_by(email=email).first():
            flash("Email already registered", "warning")
            return render_template("auth/signup.html")
        user = User(name=name, email=email, password_hash=generate_password_hash(password, method='pbkdf2:sha256'))
        db.session.add(user)
        db.session.commit()
        flash("Account created, please login", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/signup.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("shop.home"))


def _get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


@auth_bp.route('/forgot', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        # Simple rate limit: 3 attempts per 15 minutes per IP/email
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        key = f"{ip}:{email}".lower()
        now = time.time()
        window = 15*60
        rec = _forgot_attempts.get(key, [])
        # prune old
        rec = [t for t in rec if now - t < window]
        if len(rec) >= 3:
            flash('Too many requests. Please try again later.', 'warning')
            return redirect(url_for('auth.login'))
        rec.append(now)
        _forgot_attempts[key] = rec
        user = User.query.filter_by(email=email).first()
        if user:
            s = _get_serializer()
            token = s.dumps(user.email, salt=current_app.config['SECURITY_PASSWORD_SALT'])
            link = url_for('auth.reset_password', token=token, _external=True)
            html = render_template('emails/reset_password.html', link=link, user=user)
            send_email_html(to=user.email, subject='Reset your password', html=html)
        flash('If that email exists, a reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/forgot.html')


@auth_bp.route('/reset/<token>', methods=['GET', 'POST'])
def reset_password(token):
    s = _get_serializer()
    email = None
    try:
        email = s.loads(token, salt=current_app.config['SECURITY_PASSWORD_SALT'], max_age=3600)
    except (BadSignature, SignatureExpired):
        flash('Invalid or expired reset link', 'danger')
        return redirect(url_for('auth.forgot_password'))
    user = User.query.filter_by(email=email).first_or_404()
    if request.method == 'POST':
        password = request.form.get('password')
        if not password or len(password) < 6:
            flash('Password must be at least 6 characters', 'danger')
        else:
            user.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
            db.session.commit()
            flash('Password updated. Please login.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/reset.html')
