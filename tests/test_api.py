"""Tests for REST API v1: auth tokens, products, orders."""
import pytest


class TestAPIStatus:
    def test_status_ok(self, client, make_user):
        make_user()
        resp = client.get('/api/v1/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'ok'
        assert data['version'] == 'v1'

    def test_openapi_json_served(self, client, make_user):
        make_user()
        resp = client.get('/api/v1/openapi.json')
        assert resp.status_code == 200
        spec = resp.get_json()
        assert spec['openapi'].startswith('3.')
        assert 'paths' in spec

    def test_docs_page_served(self, client, make_user):
        make_user()
        resp = client.get('/api/v1/docs')
        assert resp.status_code == 200
        assert b'swagger' in resp.data.lower()


class TestAPIAuth:
    def test_token_valid_credentials(self, client, make_user):
        make_user(username='apiuser', email='api@t.td', password='Api1234!')
        resp = client.post('/api/v1/auth/token', json={
            'username': 'apiuser',
            'password': 'Api1234!',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'access_token' in data
        assert 'refresh_token' in data
        assert data['token_type'] == 'Bearer'
        assert data['user']['username'] == 'apiuser'

    def test_token_wrong_password(self, client, make_user):
        make_user(username='apiuser2', email='api2@t.td', password='Api1234!')
        resp = client.post('/api/v1/auth/token', json={
            'username': 'apiuser2',
            'password': 'wrongpassword',
        })
        assert resp.status_code == 401

    def test_token_missing_fields(self, client, make_user):
        make_user()
        resp = client.post('/api/v1/auth/token', json={})
        assert resp.status_code == 400

    def test_refresh_token(self, client, make_user):
        make_user(username='refreshuser', email='ref@t.td', password='Ref12345!')
        r = client.post('/api/v1/auth/token', json={
            'username': 'refreshuser', 'password': 'Ref12345!'
        })
        refresh_token = r.get_json()['refresh_token']
        resp = client.post('/api/v1/auth/refresh',
                           headers={'Authorization': f'Bearer {refresh_token}'})
        assert resp.status_code == 200
        assert 'access_token' in resp.get_json()


class TestAPIProducts:
    def test_list_products_empty(self, client, make_user):
        make_user()
        resp = client.get('/api/v1/products')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['products'] == []
        assert data['total'] == 0

    def test_list_products_returns_items(self, client, make_user, make_product, app):
        make_user()
        with app.app_context():
            make_product(name='Tilapia API', category='fish', price=4000, stock=50)
        resp = client.get('/api/v1/products')
        data = resp.get_json()
        assert data['total'] == 1
        assert data['products'][0]['name'] == 'Tilapia API'

    def test_list_products_category_filter(self, client, make_user, make_product, app):
        make_user()
        with app.app_context():
            make_product(name='Poulet', category='poultry', price=3000, stock=20)
            make_product(name='Poisson', category='fish', price=5000, stock=30)
        resp = client.get('/api/v1/products?category=fish')
        data = resp.get_json()
        assert data['total'] == 1
        assert data['products'][0]['name'] == 'Poisson'

    def test_list_products_price_filter(self, client, make_user, make_product, app):
        make_user()
        with app.app_context():
            make_product(name='Cheap', category='other', price=500, stock=10)
            make_product(name='Expensive', category='other', price=50000, stock=10)
        resp = client.get('/api/v1/products?min_price=1000&max_price=100000')
        data = resp.get_json()
        names = [p['name'] for p in data['products']]
        assert 'Expensive' in names
        assert 'Cheap' not in names

    def test_list_products_search(self, client, make_user, make_product, app):
        make_user()
        with app.app_context():
            make_product(name='Lapin Gris', category='rabbit', price=8000, stock=5)
        resp = client.get('/api/v1/products?q=Lapin')
        data = resp.get_json()
        assert any(p['name'] == 'Lapin Gris' for p in data['products'])

    def test_product_detail(self, client, make_user, make_product, app):
        make_user()
        with app.app_context():
            p = make_product(name='DetailFish', category='fish', price=3500, stock=10)
            pid = p.id
        resp = client.get(f'/api/v1/products/{pid}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['product']['name'] == 'DetailFish'

    def test_product_detail_not_found(self, client, make_user):
        make_user()
        resp = client.get('/api/v1/products/000000000000000000000000')
        assert resp.status_code == 404

    def test_invalid_category_returns_400(self, client, make_user):
        make_user()
        resp = client.get('/api/v1/products?category=invalid_cat')
        assert resp.status_code == 400


class TestAPIOrders:
    def test_list_orders_requires_auth(self, client, make_user):
        make_user()
        resp = client.get('/api/v1/orders')
        assert resp.status_code == 401

    def test_list_orders_empty_for_new_user(self, client, auth_headers, make_user):
        make_user()
        resp = client.get('/api/v1/orders', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['orders'] == []

    def test_create_order_cod(self, client, auth_headers, make_product, make_user, app):
        make_user()
        with app.app_context():
            p = make_product(name='Poisson CO', category='fish', price=3000, stock=20)
            pid = p.id
        resp = client.post('/api/v1/orders', json={
            'customer_name':  'Test Client',
            'customer_phone': '0600000002',
            'payment_method': 'cash_on_delivery',
            'items': [{'product_id': pid, 'quantity': 3}],
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert 'order' in data
        assert data['order']['customer_name'] == 'Test Client'
        assert data['order']['total_xaf'] == pytest.approx(9000.0)

        with app.app_context():
            from app.models.marketplace import Product
            updated = Product.get_by_id(pid)
            assert updated.stock_quantity == pytest.approx(17.0)

    def test_create_order_insufficient_stock(self, client, auth_headers, make_product, make_user, app):
        make_user()
        with app.app_context():
            p = make_product(name='LowStk', category='fish', price=2000, stock=2)
            pid = p.id
        resp = client.post('/api/v1/orders', json={
            'customer_name':  'Someone',
            'customer_phone': '0600000003',
            'payment_method': 'cash_on_delivery',
            'items': [{'product_id': pid, 'quantity': 10}],
        }, headers=auth_headers)
        assert resp.status_code == 409

    def test_create_order_missing_required_fields(self, client, auth_headers, make_user):
        make_user()
        resp = client.post('/api/v1/orders', json={}, headers=auth_headers)
        assert resp.status_code == 400

    def test_order_detail_accessible_by_owner(self, client, auth_headers, make_product, make_user, app):
        make_user()
        with app.app_context():
            p = make_product(name='ODetail', category='fish', price=1000, stock=10)
            pid = p.id
        client.post('/api/v1/orders', json={
            'customer_name': 'Owner', 'customer_phone': '0600000004',
            'payment_method': 'cash_on_delivery',
            'items': [{'product_id': pid, 'quantity': 1}],
        }, headers=auth_headers)

        orders_resp = client.get('/api/v1/orders', headers=auth_headers)
        order_number = orders_resp.get_json()['orders'][0]['order_number']

        resp = client.get(f'/api/v1/orders/{order_number}', headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['order']['order_number'] == order_number
        assert 'items' in data['order']
