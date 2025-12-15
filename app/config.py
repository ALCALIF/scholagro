import os
from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///scholagro.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECURITY_PASSWORD_SALT = os.getenv("SECURITY_PASSWORD_SALT", "change-this-salt")

    MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "")
    MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "")
    MPESA_SHORT_CODE = os.getenv("MPESA_SHORT_CODE", "")
    MPESA_PASSKEY = os.getenv("MPESA_PASSKEY", "")
    MPESA_CALLBACK_URL = os.getenv("MPESA_CALLBACK_URL", "")
    MPESA_BASE_URL = os.getenv("MPESA_BASE_URL", "https://sandbox.safaricom.co.ke")
    MPESA_TILL_NUMBER = os.getenv("MPESA_TILL_NUMBER", "123456")  # placeholder; override in Admin Settings
    MPESA_TRANSACTION_TYPE = os.getenv("MPESA_TRANSACTION_TYPE", "CustomerBuyGoodsOnline")  # default to Till

    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_SENDER = os.getenv("SMTP_SENDER", "no-reply@scholagro.com")
    # Default contact recipient
    CONTACT_TO = os.getenv("CONTACT_TO", "scholagro@gmail.com")
    # Web3Forms
    WEB3FORMS_ACCESS_KEY = os.getenv("WEB3FORMS_ACCESS_KEY")

    # Monitoring
    SENTRY_DSN = os.getenv("SENTRY_DSN")
    GOOGLE_TAG_ID = os.getenv("GOOGLE_TAG_ID")

    # Caching
    CACHE_TYPE = os.getenv("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT = int(os.getenv("CACHE_DEFAULT_TIMEOUT", "300"))
    # Redis / Celery
    REDIS_URL = os.getenv('REDIS_URL', os.getenv('CACHE_REDIS_URL') or os.getenv('REDIS_URL'))
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', REDIS_URL)
    # Stripe
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    # Session cookie security
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = os.getenv('SESSION_COOKIE_HTTPONLY', 'true').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    REMEMBER_COOKIE_SECURE = os.getenv('REMEMBER_COOKIE_SECURE', 'false').lower() == 'true'
    # Socket.IO
    SOCKETIO_ENABLED = os.getenv('SOCKETIO_ENABLED', 'true').lower() == 'true'
    SOCKETIO_ASYNC_MODE = os.getenv('SOCKETIO_ASYNC_MODE')  # eventlet, gevent, threading, asyncio


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False


def get_config():
    env = os.getenv("FLASK_ENV", "development").lower()
    if env == "production":
        return ProductionConfig
    return DevelopmentConfig
