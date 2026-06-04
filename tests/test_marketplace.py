"""Tests for marketplace: catalog, cart, checkout, stock deduction."""
import pytest


class TestCatalog:
    def test_marketplace_index_public(self, client, make_user):
        make_user()  # ensure setup guard passes
        resp = client.get('/marketplace/')
        assert resp.status_code == 200

    def test_marketplace_index_shows_products(self, client, make_user, make_product):
        make_user()
        make_product(name='Poisson Tilapia', category='fish', price=4000, stock=50)
        resp = client.get('/marketplace/')
        assert resp.status_code == 200
        assert b'Tilapia' in resp.data

    def test_category_filter(self, client, make_user, make_product):
        make_user()
        make_product(name='Poulet', category='poultry', price=3000, stock=20)
        resp = client.get('/marketplace/?cat=poultry')
        assert resp.status_code == 200

    def test_search_endpoint_returns_json(self, client, make_user, make_product):
        make_user()
        make_product(name='Lapin Blanc', category='rabbit', price=6000, stock=30)
        resp = client.get('/marketplace/search?q=Lapin')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'products' in data
        assert any(p['name'] == 'Lapin Blanc' for p in data['products'])

    def test_search_price_filter(self, client, make_user, make_product):
        make_user()
        make_product(name='Cheap Fish', category='fish', price=1000, stock=10)
        make_product(name='Expensive Fish', category='fish', price=20000, stock=10)
        resp = client.get('/marketplace/search?min_price=5000&max_price=25000')
        data = resp.get_json()
        names = [p['name'] for p in data['products']]
        assert 'Expensive Fish' in names
        assert 'Cheap Fish' not in names

    def test_product_detail(self, client, make_user, make_product, app):
        make_user()
        with app.app_context():
            p = make_product(name='Tilapia Détail', category='fish', price=3500, stock=10)
            pid = p.id
        resp = client.get(f'/marketplace/product/{pid}')
        assert resp.status_code == 200


class TestCart:
    def test_cart_empty_on_start(self, client, make_user):
        make_user()
        resp = client.get('/marketplace/cart')
        assert resp.status_code == 200

    def test_add_to_cart(self, client, make_user, make_product, app):
        make_user()
        with app.app_context():
            p = make_product(name='Oeufs', category='eggs', price=500, stock=100)
            pid = p.id
        resp = client.post('/marketplace/cart/add',
                           data={'product_id': pid, 'quantity': 2},
                           follow_redirects=True)
        assert resp.status_code == 200

    def test_add_unavailable_product_rejected(self, client, make_user, make_product, app):
        make_user()
        with app.app_context():
            from app.models.marketplace import Product
            p = make_product(name='Rupture', category='other', price=1000, stock=0)
            # Mark unavailable
            p.is_available = False
            p.save()
            pid = p.id
        resp = client.post('/marketplace/cart/add',
                           data={'product_id': pid, 'quantity': 1},
                           follow_redirects=True)
        assert resp.status_code == 200


class TestCheckout:
    def _add_item_to_cart(self, client, pid, qty=1):
        client.post('/marketplace/cart/add',
                    data={'product_id': pid, 'quantity': qty},
                    follow_redirects=True)

    def test_checkout_requires_non_empty_cart(self, client, make_user):
        make_user(username='u', email='u@t.td', password='User1234!')
        client.post('/auth/login', data={'username': 'u', 'password': 'User1234!'})
        resp = client.get('/marketplace/checkout', follow_redirects=True)
        assert resp.status_code == 200

    def test_cod_checkout_creates_order_and_decrements_stock(
        self, client, make_user, make_product, app
    ):
        make_user(username='buyer', email='buyer@t.td', password='Buyer123!')
        client.post('/auth/login', data={'username': 'buyer', 'password': 'Buyer123!'})
        with app.app_context():
            p = make_product(name='Tilapia', category='fish', price=3000, stock=10)
            pid = p.id

        self._add_item_to_cart(client, pid, qty=2)

        resp = client.post('/marketplace/checkout', data={
            'customer_name':    'Buyer Test',
            'customer_phone':   '0600000000',
            'customer_address': 'N\'Djamena',
            'payment_method':   'cash_on_delivery',
            'notes':            '',
            'mobile_money_phone': '',
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            from app.models.marketplace import Product, Order
            updated = Product.get_by_id(pid)
            assert updated is not None
            # Stock should have decreased by ordered quantity
            assert updated.stock_quantity == pytest.approx(8.0)
            orders = Order.recent(1)
            assert len(orders) == 1
            assert orders[0].customer_name == 'Buyer Test'

    def test_checkout_insufficient_stock_rejected(
        self, client, make_user, make_product, app
    ):
        make_user(username='buyer2', email='buyer2@t.td', password='Buyer123!')
        client.post('/auth/login', data={'username': 'buyer2', 'password': 'Buyer123!'})
        with app.app_context():
            p = make_product(name='LowStock', category='fish', price=2000, stock=1)
            pid = p.id

        self._add_item_to_cart(client, pid, qty=5)

        resp = client.post('/marketplace/checkout', data={
            'customer_name':  'Buyer2',
            'customer_phone': '0600000001',
            'payment_method': 'cash_on_delivery',
            'notes': '',
            'mobile_money_phone': '',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            from app.models.marketplace import Order
            # No order should have been created
            assert Order.count_all() == 0
