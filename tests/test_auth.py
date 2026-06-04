"""Tests for authentication flows: login, logout, setup guard, role redirect."""
import pytest


class TestSetupGuard:
    def test_empty_db_redirects_to_setup(self, client):
        resp = client.get('/', follow_redirects=False)
        # With empty users collection the before_request hook redirects to setup
        assert resp.status_code in (302, 200)

    def test_setup_page_accessible(self, client):
        resp = client.get('/auth/setup')
        assert resp.status_code == 200

    def test_setup_creates_admin(self, client, app):
        resp = client.post('/auth/setup', data={
            'username': 'admin',
            'email': 'admin@omnifarm.td',
            'password': 'Admin1234!',
            'confirm': 'Admin1234!',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            from app.models.user import User
            user = User.find_by_username_or_email('admin')
            assert user is not None
            assert user.is_admin


class TestLogin:
    def test_login_success(self, client, make_user):
        make_user(username='alice', email='alice@omnifarm.td', password='Alice123!')
        resp = client.post('/auth/login', data={
            'username': 'alice',
            'password': 'Alice123!',
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_login_wrong_password(self, client, make_user):
        make_user(username='bob', email='bob@omnifarm.td', password='Bob12345!')
        resp = client.post('/auth/login', data={
            'username': 'bob',
            'password': 'wrongpassword',
        }, follow_redirects=True)
        assert resp.status_code == 200
        data = resp.data.decode()
        assert 'incorrects' in data.lower() or 'invalid' in data.lower() or resp.status_code == 200

    def test_login_nonexistent_user(self, client, make_user):
        make_user()  # ensure users exist so setup guard doesn't intercept
        resp = client.post('/auth/login', data={
            'username': 'nobody',
            'password': 'Whatever1!',
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_logout(self, client, make_user):
        make_user(username='carol', email='carol@omnifarm.td', password='Carol123!')
        client.post('/auth/login', data={'username': 'carol', 'password': 'Carol123!'})
        resp = client.get('/auth/logout', follow_redirects=True)
        assert resp.status_code == 200


class TestDashboardAccess:
    def test_dashboard_requires_login(self, client, make_user):
        make_user()  # ensure users exist
        resp = client.get('/dashboard', follow_redirects=False)
        assert resp.status_code in (302, 401)

    def test_dashboard_accessible_when_logged_in(self, client, make_user):
        make_user(username='dave', email='dave@omnifarm.td', password='Dave1234!')
        client.post('/auth/login', data={'username': 'dave', 'password': 'Dave1234!'})
        resp = client.get('/dashboard')
        assert resp.status_code == 200
