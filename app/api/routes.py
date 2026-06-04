"""
OmniFarm Hub — REST API v1
Base URL: /api/v1
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import jsonify, request, render_template
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    get_jwt_identity, jwt_required,
)

from app.extensions import limiter
from app.models.user import User
from app.models.marketplace import (
    Product, Order, OrderItem, Payment,
    ProductCategory, OrderStatus, PaymentMethod, PaymentStatus,
    generate_order_number,
)
from app.marketplace.gateways import initiate_orange_money, initiate_mtn_mobile_money
from app.marketplace.txn import checkout_transact, InsufficientStockError
from app.email import send_order_confirmation
from . import api_bp

logger = logging.getLogger(__name__)


def _ok(data: dict, status: int = 200):
    return jsonify(data), status


def _err(message: str, status: int = 400):
    return jsonify({'error': message}), status


def _product_dict(p: Product) -> dict:
    return {
        'id':             p.id,
        'name':           p.name,
        'description':    p.description,
        'category':       p.category.value,
        'category_label': p.category_label(),
        'category_icon':  p.category_icon(),
        'price_xaf':      float(p.price_xaf),
        'unit':           p.unit,
        'stock_quantity': p.stock_quantity,
        'is_available':   p.is_available,
        'image_url':      f'/marketplace/images/{p.image_id}' if p.image_id else None,
        'created_at':     p.created_at.isoformat() if p.created_at else None,
    }


def _order_dict(o: Order, include_items: bool = False) -> dict:
    d = {
        'order_number':     o.order_number,
        'status':           o.status.value,
        'status_label':     o.status_label(),
        'payment_method':   o.payment_method.value if o.payment_method else None,
        'total_xaf':        float(o.total_xaf),
        'customer_name':    o.customer_name,
        'customer_phone':   o.customer_phone,
        'customer_address': o.customer_address,
        'notes':            o.notes,
        'created_at':       o.created_at.isoformat() if o.created_at else None,
    }
    if include_items:
        d['items'] = [
            {
                'product_name':   i.product_name,
                'product_unit':   i.product_unit,
                'unit_price_xaf': float(i.unit_price_xaf),
                'quantity':       i.quantity,
                'subtotal_xaf':   float(i.subtotal_xaf),
            }
            for i in o.items
        ]
        if o.payment:
            d['payment'] = {
                'method':    o.payment.method.value,
                'status':    o.payment.status.value,
                'reference': o.payment.gateway_reference,
            }
    return d


@api_bp.route('/openapi.json')
def openapi_json():
    from .openapi_spec import get_spec
    return jsonify(get_spec())


@api_bp.route('/docs')
def docs():
    return render_template('api/docs.html')


@api_bp.route('/status')
def status():
    return _ok({'status': 'ok', 'version': 'v1',
                'timestamp': datetime.now(timezone.utc).isoformat()})


@api_bp.route('/auth/token', methods=['POST'])
@limiter.limit('10 per minute')
def auth_token():
    data       = request.get_json(silent=True) or {}
    identifier = str(data.get('username', '')).strip()
    password   = str(data.get('password', ''))

    if not identifier or not password:
        return _err('username and password are required.', 400)

    user = User.find_by_username_or_email(identifier)
    if not user or not user.is_active or not user.check_password(password):
        logger.warning('[API] Failed login attempt for identifier=%r', identifier)
        return _err('Invalid credentials or account disabled.', 401)

    user.touch_last_login()

    access  = create_access_token(identity=str(user.id))
    refresh = create_refresh_token(identity=str(user.id))

    logger.info('[API] Token issued: user_id=%s role=%s', user.id, user.role.value)
    return _ok({
        'access_token':  access,
        'refresh_token': refresh,
        'token_type':    'Bearer',
        'user': {
            'id':       user.id,
            'username': user.username,
            'email':    user.email,
            'role':     user.role.value,
        },
    })


@api_bp.route('/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def auth_refresh():
    user_id    = get_jwt_identity()
    new_access = create_access_token(identity=user_id)
    return _ok({'access_token': new_access, 'token_type': 'Bearer'})


@api_bp.route('/products')
def products_list():
    q         = request.args.get('q', '').strip()
    category  = request.args.get('category', '').strip()
    page      = max(1, request.args.get('page', 1, type=int))
    per_page  = min(100, max(1, request.args.get('per_page', 20, type=int)))
    min_price = request.args.get('min_price', None, type=float)
    max_price = request.args.get('max_price', None, type=float)

    cat_enum = None
    if category:
        try:
            cat_enum = ProductCategory(category)
        except ValueError:
            return _err(f'Unknown category: {category}. Valid: {[c.value for c in ProductCategory]}', 400)

    pagination = Product.paginate_available(
        page, per_page, category=cat_enum, q=q,
        min_price=min_price, max_price=max_price,
    )
    return _ok({
        'products': [_product_dict(p) for p in pagination.items],
        'total':    pagination.total,
        'page':     page,
        'per_page': per_page,
        'pages':    pagination.pages,
    })


@api_bp.route('/products/<product_id>')
def product_detail(product_id: str):
    p = Product.get_by_id(product_id)
    if not p:
        return _err('Product not found.', 404)
    return _ok({'product': _product_dict(p)})


@api_bp.route('/orders')
@jwt_required()
def orders_list():
    user_id = get_jwt_identity()
    pag     = Order.paginate_by_customer(user_id, page=1, per_page=100)
    return _ok({'orders': [_order_dict(o) for o in pag.items]})


@api_bp.route('/orders/<order_number>')
@jwt_required()
def order_detail(order_number: str):
    user_id = get_jwt_identity()
    order   = Order.get_by_order_number(order_number)
    if not order:
        return _err('Order not found.', 404)

    user = User.get_by_id(user_id)
    if order.customer_id != user_id and not (user and user.is_admin):
        return _err('Access denied.', 403)

    return _ok({'order': _order_dict(order, include_items=True)})


@api_bp.route('/orders', methods=['POST'])
@jwt_required()
@limiter.limit('10 per minute')
def orders_create():
    user_id   = get_jwt_identity()
    data      = request.get_json(silent=True) or {}

    name      = str(data.get('customer_name', '')).strip()
    phone     = str(data.get('customer_phone', '')).strip()
    address   = str(data.get('customer_address', '')).strip() or None
    notes     = str(data.get('notes', '')).strip() or None
    items_raw = data.get('items', [])

    if not name or not phone:
        return _err('customer_name and customer_phone are required.', 400)
    if not isinstance(items_raw, list) or not items_raw:
        return _err('items must be a non-empty list.', 400)

    try:
        method = PaymentMethod(data.get('payment_method', 'cash_on_delivery'))
    except ValueError:
        return _err(f'Invalid payment_method. Valid: {[m.value for m in PaymentMethod]}', 400)

    resolved_items = []
    total = 0.0
    for entry in items_raw:
        pid = entry.get('product_id')
        qty = entry.get('quantity', 1.0)
        if not pid or not isinstance(qty, (int, float)) or qty <= 0:
            return _err('Each item needs product_id (str) and quantity (positive number).', 400)
        product = Product.get_by_id(str(pid))
        if not product or not product.is_available:
            return _err(f'Product {pid} is not available.', 400)
        subtotal = float(product.price_xaf) * float(qty)
        total += subtotal
        resolved_items.append((product, float(qty), subtotal))

    pay_phone = str(data.get('mobile_money_phone', '') or phone).strip()

    order = Order(
        order_number=generate_order_number(),
        customer_id=user_id,
        customer_name=name,
        customer_phone=phone,
        customer_address=address,
        status=OrderStatus.PENDING.value,
        payment_method=method.value,
        total_xaf=total,
        notes=notes,
    )
    order.items = [
        OrderItem(
            product_id=product.id,
            product_name=product.name,
            product_unit=product.unit,
            unit_price_xaf=product.price_xaf,
            quantity=qty,
            subtotal_xaf=subtotal,
        )
        for product, qty, subtotal in resolved_items
    ]

    payment = Payment(
        method=method.value,
        phone_number=pay_phone,
        amount_xaf=total,
        status=PaymentStatus.PENDING.value,
    )

    payment_url = None

    if method == PaymentMethod.ORANGE_MONEY:
        order.status = OrderStatus.PAYMENT_PENDING
        resp = initiate_orange_money(order.order_number, int(total), pay_phone,
                                     description=f'OmniFarm {order.order_number}')
        payment.gateway_reference = resp.reference
        payment.gateway_response  = resp.raw_response
        if resp.success:
            payment_url = resp.payment_url

    elif method == PaymentMethod.MTN_MOBILE_MONEY:
        order.status = OrderStatus.PAYMENT_PENDING
        resp = initiate_mtn_mobile_money(order.order_number, int(total), pay_phone,
                                         description=f'OmniFarm {order.order_number}')
        payment.gateway_reference = resp.reference
        payment.gateway_response  = resp.raw_response

    else:
        order.status = OrderStatus.PROCESSING

    order.payment = payment

    try:
        checkout_transact(order, [(product, qty) for product, qty, _ in resolved_items])
    except InsufficientStockError as exc:
        return _err(
            f'Stock insuffisant pour « {exc.product_name} » '
            f'(disponible : {exc.available}, demandé : {exc.requested}).',
            409,
        )

    send_order_confirmation(order)

    logger.info('[API] Order created: %s user=%s method=%s total=%s',
                order.order_number, user_id, method.value, total)

    result = {'order': _order_dict(order, include_items=True)}
    if payment_url:
        result['payment_url'] = payment_url
    return _ok(result, 201)
