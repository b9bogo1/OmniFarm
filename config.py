import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # --- Security ---
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-fallback-secret-CHANGE-IN-PROD')
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour

    # --- MongoDB Replica Set ---
    # All credentials come from .env — never hardcode here
    _MONGO_USER = os.environ.get('MONGO_USER', '')
    _MONGO_PASS = os.environ.get('MONGO_PASS', '')
    _MONGO_RS   = os.environ.get('MONGO_RS_NAME', 'rs0')
    _MONGO_DB   = os.environ.get('MONGO_DB', 'omnifarm_db')
    _MONGO_AUTH = f"{_MONGO_USER}:{_MONGO_PASS}@" if _MONGO_USER else ''

    # Seed list uses the exact hostnames the RS members report to each other
    # (mongo-1 / mongo-2 / mongo-3).  These must resolve on every machine
    # that runs the app — add them to /etc/hosts or the Windows hosts file:
    #   10.9.4.11   mongo-1
    #   10.9.4.12   mongo-2
    #   10.9.4.13   mongo-3
    #
    # PyMongo behaviour:
    #   1. Connects to any seed in the list.
    #   2. Runs "hello" / isMaster to discover the full RS topology.
    #   3. Routes writes to the elected primary, reads to the nearest node.
    #   4. Monitors topology every heartbeatFrequencyMS and auto-fails over.
    MONGO_URI = (
        f"mongodb://{_MONGO_AUTH}"
        f"mongo-1:27017,mongo-2:27017,mongo-3:27017"
        f"/{_MONGO_DB}"
        f"?replicaSet={_MONGO_RS}"
        f"&authSource=admin"
        f"&readPreference=primaryPreferred"
        f"&w=majority"
        f"&journal=true"
        f"&connectTimeoutMS=5000"
        f"&serverSelectionTimeoutMS=10000"
        f"&heartbeatFrequencyMS=10000"
        f"&retryWrites=true"
        f"&retryReads=true"
    )
    # Lightweight URI used by run.py bootstrap (no majority wait for schema ops)
    MONGO_URI_BOOTSTRAP = (
        f"mongodb://{_MONGO_AUTH}"
        f"mongo-1:27017,mongo-2:27017,mongo-3:27017"
        f"/{_MONGO_DB}"
        f"?replicaSet={_MONGO_RS}"
        f"&authSource=admin"
        f"&w=1"
        f"&connectTimeoutMS=5000"
        f"&serverSelectionTimeoutMS=10000"
        f"&retryWrites=true"
    )
    MONGO_DB = _MONGO_DB

    # --- Internationalization ---
    BABEL_DEFAULT_LOCALE = 'fr'
    BABEL_DEFAULT_TIMEZONE = 'Africa/Douala'
    LANGUAGES = ['fr', 'en']

    # --- Logging ---
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/omnifarm.log')

    # --- Payment Gateways ---
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')
    ORANGE_MONEY_CLIENT_ID     = os.environ.get('ORANGE_MONEY_CLIENT_ID', '')
    ORANGE_MONEY_CLIENT_SECRET = os.environ.get('ORANGE_MONEY_CLIENT_SECRET', '')
    ORANGE_MONEY_MERCHANT_KEY  = os.environ.get('ORANGE_MONEY_MERCHANT_KEY', '')
    MTN_MOMO_SUBSCRIPTION_KEY  = os.environ.get('MTN_MOMO_SUBSCRIPTION_KEY', '')
    MTN_MOMO_API_USER          = os.environ.get('MTN_MOMO_API_USER', '')
    MTN_MOMO_API_KEY           = os.environ.get('MTN_MOMO_API_KEY', '')
    MTN_MOMO_TARGET_ENV        = os.environ.get('MTN_MOMO_TARGET_ENV', 'mtncameroon')

    # --- Product image uploads ---
    UPLOAD_FOLDER = os.path.join(
        os.path.dirname(__file__), 'app', 'static', 'uploads', 'products'
    )
    ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
    PRODUCT_IMAGE_SIZE = (400, 400)
    PRODUCT_IMAGE_MAX_BYTES = 5 * 1024 * 1024

    # --- Carousel image uploads ---
    CAROUSEL_UPLOAD_FOLDER = os.path.join(
        os.path.dirname(__file__), 'app', 'static', 'uploads', 'carousel'
    )
    CAROUSEL_IMAGE_SIZE = (1400, 700)
    CAROUSEL_IMAGE_MAX_BYTES = 8 * 1024 * 1024

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024

    # --- Email (Flask-Mail) ---
    MAIL_SERVER          = os.environ.get('MAIL_SERVER', '[PLACEHOLDER_MAIL_SERVER]')
    MAIL_PORT            = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS         = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL         = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME        = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD        = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER  = os.environ.get('MAIL_DEFAULT_SENDER', 'OmniFarm <noreply@[PLACEHOLDER_DOMAIN]>')
    MAIL_SUPPRESS_SEND   = os.environ.get('MAIL_SUPPRESS_SEND', 'false').lower() == 'true'

    # --- Error Tracking (Sentry) ---
    SENTRY_DSN = os.environ.get('SENTRY_DSN', '')

    # --- Rate Limiting (Flask-Limiter) ---
    RATELIMIT_STORAGE_URI    = os.environ.get('REDIS_URL', 'memory://')
    RATELIMIT_DEFAULT        = '500 per day;100 per hour'
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_SWALLOW_ERRORS = True

    # --- REST API (JWT) ---
    JWT_SECRET_KEY           = os.environ.get('JWT_SECRET_KEY', '[PLACEHOLDER_JWT_SECRET_KEY]')
    JWT_ACCESS_TOKEN_EXPIRES  = 3600
    JWT_REFRESH_TOKEN_EXPIRES = 30 * 24 * 3600

    # --- IoT / Background Scheduler ---
    SCHEDULER_API_ENABLED = False
    MODBUS_POLL_INTERVAL_SECONDS = 30
    IOT_POLL_INTERVAL_MINUTES = 5


class DevelopmentConfig(Config):
    FLASK_DEBUG = True


class ProductionConfig(Config):
    FLASK_DEBUG = False
    WTF_CSRF_TIME_LIMIT = 1800


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': Config,
}
