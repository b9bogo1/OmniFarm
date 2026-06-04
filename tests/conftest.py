"""
Pytest fixtures for OmniFarm Hub.

Strategy: create the Flask app normally, then surgically replace mongo.db and
mongo.cx with mongomock equivalents BEFORE the first request is made.
PyMongo 4.x with connect=False defers the actual connection, so swapping out
the client before any query is safe.
"""
import mongomock
import pytest


# ── Test application config ───────────────────────────────────────────────────

class TestConfig:
    TESTING = True
    SECRET_KEY = 'test-secret-key-omnifarm'
    WTF_CSRF_ENABLED = False
    MONGO_URI = 'mongodb://localhost:27017/omnifarm_test'
    JWT_SECRET_KEY = 'test-jwt-secret'
    BABEL_DEFAULT_LOCALE = 'fr'
    LANGUAGES = ['fr', 'en']
    MAIL_SUPPRESS_SEND = True
    MAIL_SERVER = 'localhost'
    RATELIMIT_ENABLED = False
    LOG_FILE = 'logs/test.log'
    LOG_LEVEL = 'WARNING'
    SENTRY_DSN = ''


# ── Session-scoped app + mongo swap ──────────────────────────────────────────

@pytest.fixture(scope='session')
def _mock_mongo_client():
    """Single mongomock client reused across the whole test session."""
    return mongomock.MongoClient()


@pytest.fixture(scope='session')
def app(_mock_mongo_client):
    """Flask app with the real MongoClient swapped out for mongomock."""
    from app import create_app
    application = create_app(TestConfig)

    # Swap mongo.cx and mongo.db so every get_col() call hits the mock.
    from app.extensions import mongo
    mongo.cx = _mock_mongo_client
    mongo.db = _mock_mongo_client['omnifarm_test']

    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


# ── Per-test DB cleanup ───────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_db(app, _mock_mongo_client):
    """Drop every collection before each test."""
    db = _mock_mongo_client['omnifarm_test']
    for name in db.list_collection_names():
        db.drop_collection(name)
    yield


# ── Factory helpers ───────────────────────────────────────────────────────────

@pytest.fixture()
def make_user(app):
    def _factory(username='testuser', email='test@omnifarm.td',
                 password='Test1234!', role='admin'):
        with app.app_context():
            from app.models.user import User, UserRole
            u = User(username=username, email=email,
                     role=UserRole(role), is_active=True)
            u.set_password(password)
            u.save()
            return u
    return _factory


@pytest.fixture()
def make_product(app):
    def _factory(name='Tilapia', category='fish', price=5000, stock=100):
        with app.app_context():
            from app.models.marketplace import Product, ProductCategory
            p = Product(name=name, category=ProductCategory(category),
                        price_xaf=price, unit='kg',
                        stock_quantity=stock, is_available=True)
            p.save()
            return p
    return _factory


@pytest.fixture()
def auth_headers(client, make_user):
    make_user(username='apiuser', email='api@omnifarm.td',
              password='Api1234!', role='client')
    resp = client.post('/api/v1/auth/token',
                       json={'username': 'apiuser', 'password': 'Api1234!'})
    token = resp.get_json()['access_token']
    return {'Authorization': f'Bearer {token}'}
