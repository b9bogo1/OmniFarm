import logging
from datetime import datetime, timezone, timedelta

import gridfs
from bson import ObjectId
from flask import render_template, redirect, url_for, flash, request, abort, jsonify, Response
from flask_login import current_user, login_required
from flask_babel import gettext as _

from app.extensions import limiter, csrf
from app.db import get_col
from app.models.marketplace import (
    Product, Order, OrderItem, Payment, CarouselSlide,
    ProductCategory, OrderStatus, PaymentMethod, PaymentStatus,
    generate_order_number,
)
from app.auth.decorators import admin_required
from app.email import send_order_confirmation, send_order_status_update
from . import marketplace_bp
from .cart import Cart
from .forms import ProductForm, CheckoutForm, UpdateOrderStatusForm, CarouselSlideForm
from .upload import save_product_image, delete_product_image, save_carousel_image, delete_carousel_image
from .gateways import (
    initiate_orange_money, initiate_mtn_mobile_money,
    verify_orange_webhook, check_mtn_payment_status,
)

logger = logging.getLogger(__name__)


# ── GridFS image serving ─────────────────────────────────────────────────────

@marketplace_bp.route('/images/<file_id>')
def serve_image(file_id):
    from app.extensions import mongo
    try:
        fs = gridfs.GridFS(mongo.db)
        grid_out = fs.get(ObjectId(file_id))
        return Response(
            grid_out.read(),
            mimetype=grid_out.content_type or 'image/jpeg',
            headers={'Cache-Control': 'public, max-age=86400'},
        )
    except Exception:
        abort(404)


# ── Public product catalog ───────────────────────────────────────────────────

@marketplace_bp.route('/')
def index():
    category_filter = request.args.get('cat')
    page = request.args.get('page', 1, type=int)

    cat_enum = None
    if category_filter:
        try:
            cat_enum = ProductCategory(category_filter)
        except ValueError:
            pass

    pagination = Product.paginate_available(page, per_page=20, category=cat_enum)
    slides     = CarouselSlide.find_active()

    return render_template(
        'marketplace/index.html',
        products=pagination.items,
        pagination=pagination,
        categories=ProductCategory,
        active_cat=category_filter,
        slides=slides,
        title=_('Marché'),
    )


@marketplace_bp.route('/product/<product_id>')
def product_detail(product_id):
    product = Product.get_by_id(product_id) or abort(404)
    return render_template('marketplace/product_detail.html', product=product, title=product.name)


# ── Cart ─────────────────────────────────────────────────────────────────────

@marketplace_bp.route('/cart')
def cart_view():
    cart  = Cart()
    items = cart.get_items()
    return render_template('marketplace/cart.html', items=items,
                           total=cart.get_total(), title=_('Mon panier'))


@marketplace_bp.route('/cart/add', methods=['POST'])
@limiter.limit('60 per minute')
def cart_add():
    product_id = request.form.get('product_id', type=str)
    quantity   = request.form.get('quantity', 1.0, type=float)
    if not product_id or quantity <= 0:
        flash(_('Requête invalide.'), 'danger')
        return redirect(request.referrer or url_for('marketplace.index'))

    cart = Cart()
    if cart.add(product_id, quantity):
        flash(_('Produit ajouté au panier.'), 'success')
    else:
        flash(_('Produit indisponible.'), 'warning')
    return redirect(request.referrer or url_for('marketplace.index'))


@marketplace_bp.route('/cart/remove/<product_id>', methods=['POST'])
def cart_remove(product_id):
    Cart().remove(product_id)
    flash(_('Article retiré du panier.'), 'success')
    return redirect(url_for('marketplace.cart_view'))


@marketplace_bp.route('/cart/update', methods=['POST'])
def cart_update():
    cart = Cart()
    for key, val in request.form.items():
        if key.startswith('qty_'):
            try:
                pid = key.split('_', 1)[1]
                qty = float(val)
                cart.update(pid, qty)
            except (ValueError, IndexError):
                pass
    flash(_('Panier mis à jour.'), 'success')
    return redirect(url_for('marketplace.cart_view'))


# ── Checkout ─────────────────────────────────────────────────────────────────

@marketplace_bp.route('/checkout', methods=['GET', 'POST'])
@limiter.limit('15 per minute')
def checkout():
    cart = Cart()
    if cart.is_empty():
        flash(_('Votre panier est vide.'), 'warning')
        return redirect(url_for('marketplace.index'))

    form = CheckoutForm()
    if request.method == 'GET' and current_user.is_authenticated:
        form.customer_name.data = current_user.username

    if form.validate_on_submit():
        items = cart.get_items()
        if not items:
            flash(_('Votre panier est vide ou les produits ne sont plus disponibles.'), 'danger')
            return redirect(url_for('marketplace.index'))

        total  = cart.get_total()
        method = PaymentMethod(form.payment_method.data)

        order = Order(
            order_number=generate_order_number(),
            customer_id=current_user.id if current_user.is_authenticated else None,
            customer_name=form.customer_name.data.strip(),
            customer_phone=form.customer_phone.data.strip(),
            customer_address=form.customer_address.data or None,
            status=OrderStatus.PENDING.value,
            payment_method=method.value,
            total_xaf=total,
            notes=form.notes.data or None,
        )
        order.items = [
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                product_unit=product.unit,
                unit_price_xaf=product.price_xaf,
                quantity=qty,
                subtotal_xaf=product.price_float * qty,
            )
            for product, qty in items
        ]

        phone_for_payment = form.mobile_money_phone.data or form.customer_phone.data
        payment = Payment(
            method=method.value,
            phone_number=phone_for_payment,
            amount_xaf=total,
            status=PaymentStatus.PENDING.value,
        )

        orange_redirect_url = None

        if method == PaymentMethod.ORANGE_MONEY:
            order.status = OrderStatus.PAYMENT_PENDING
            resp = initiate_orange_money(
                order.order_number, int(total), phone_for_payment,
                description=_('Commande OmniFarm %(num)s', num=order.order_number),
            )
            payment.gateway_reference = resp.reference
            payment.gateway_response  = resp.raw_response
            if resp.success and resp.payment_url:
                orange_redirect_url = resp.payment_url
            elif not resp.success:
                flash(_('Orange Money : %(msg)s', msg=resp.message), 'warning')

        elif method == PaymentMethod.MTN_MOBILE_MONEY:
            order.status = OrderStatus.PAYMENT_PENDING
            resp = initiate_mtn_mobile_money(
                order.order_number, int(total), phone_for_payment,
                description=_('Commande OmniFarm %(num)s', num=order.order_number),
            )
            payment.gateway_reference = resp.reference
            payment.gateway_response  = resp.raw_response
            if not resp.success:
                flash(_('MTN MoMo : %(msg)s', msg=resp.message), 'warning')

        else:
            order.status = OrderStatus.PROCESSING

        order.payment = payment
        order.save()
        cart.clear()
        send_order_confirmation(order)

        if orange_redirect_url:
            return redirect(orange_redirect_url)

        flash(_('Commande %(num)s confirmée avec succès !', num=order.order_number), 'success')
        return redirect(url_for('marketplace.order_confirmation', order_number=order.order_number))

    return render_template(
        'marketplace/checkout.html',
        form=form,
        cart_items=cart.get_items(),
        total=cart.get_total(),
        title=_('Finaliser la commande'),
    )


@marketplace_bp.route('/order/<order_number>')
def order_confirmation(order_number):
    order = Order.get_by_order_number(order_number) or abort(404)
    return render_template('marketplace/order_confirmation.html',
                           order=order, title=_('Confirmation de commande'))


@marketplace_bp.route('/my-orders')
@login_required
def my_orders():
    page          = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')

    _pending_vals = [OrderStatus.PENDING.value, OrderStatus.PAYMENT_PENDING.value,
                     OrderStatus.PROCESSING.value]
    _paid_vals    = [OrderStatus.PAID.value, OrderStatus.DELIVERED.value]

    raw_counts    = Order.count_by_customer_and_statuses(current_user.id)
    all_count     = sum(raw_counts.values())
    pending_count = sum(raw_counts.get(s, 0) for s in _pending_vals)
    done_count    = sum(raw_counts.get(s, 0) for s in _paid_vals)
    cancelled_count = raw_counts.get(OrderStatus.CANCELLED.value, 0)

    sf = None if status_filter == 'all' else status_filter
    pagination = Order.paginate_by_customer(current_user.id, page, per_page=10, status_filter=sf)

    return render_template(
        'marketplace/my_orders.html',
        orders=pagination.items,
        pagination=pagination,
        status_filter=status_filter,
        all_count=all_count,
        pending_count=pending_count,
        done_count=done_count,
        cancelled_count=cancelled_count,
        title=_('Mes commandes'),
    )


# ── Admin: Product management ────────────────────────────────────────────────

@marketplace_bp.route('/admin/products')
@admin_required
def admin_products():
    page         = request.args.get('page', 1, type=int)
    total_count  = Product.count_all()
    active_count = Product.count_available()
    low_stock    = Product.count_low_stock()
    pagination   = Product.paginate_all(page, per_page=20)
    return render_template(
        'marketplace/admin/products.html',
        products=pagination.items,
        pagination=pagination,
        total_count=total_count,
        active_count=active_count,
        inactive_count=total_count - active_count,
        low_stock_count=low_stock,
        title=_('Gestion des produits'),
    )


@marketplace_bp.route('/admin/product/new', methods=['GET', 'POST'])
@admin_required
def admin_create_product():
    form = ProductForm()
    if form.validate_on_submit():
        image_id = None
        if form.image.data and form.image.data.filename:
            try:
                image_id = save_product_image(form.image.data)
            except ValueError as exc:
                flash(str(exc), 'danger')
                return render_template('marketplace/admin/product_form.html',
                                       form=form, title=_('Nouveau produit'), is_edit=False)
        product = Product(
            name=form.name.data.strip(),
            description=form.description.data or None,
            category=form.category.data,
            price_xaf=form.price_xaf.data,
            unit=form.unit.data.strip(),
            stock_quantity=form.stock_quantity.data or 0.0,
            is_available=form.is_available.data,
            image_id=image_id,
            created_by_id=current_user.id,
        )
        product.save()
        flash(_('Produit « %(name)s » créé.', name=product.name), 'success')
        return redirect(url_for('marketplace.admin_products'))
    return render_template('marketplace/admin/product_form.html',
                           form=form, title=_('Nouveau produit'), is_edit=False)


@marketplace_bp.route('/admin/product/<product_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    product = Product.get_by_id(product_id) or abort(404)
    form    = ProductForm(obj=product)
    if form.validate_on_submit():
        if form.image.data and form.image.data.filename:
            try:
                product.image_id = save_product_image(
                    form.image.data, old_file_id=product.image_id
                )
            except ValueError as exc:
                flash(str(exc), 'danger')
                form.category.data = product.category.value
                return render_template('marketplace/admin/product_form.html',
                                       form=form, product=product,
                                       title=_('Modifier le produit'), is_edit=True)
        elif form.remove_image.data and product.image_id:
            delete_product_image(product.image_id)
            product.image_id = None

        product.name           = form.name.data.strip()
        product.description    = form.description.data or None
        product.category       = ProductCategory(form.category.data)
        product.price_xaf      = form.price_xaf.data
        product.unit           = form.unit.data.strip()
        product.stock_quantity = form.stock_quantity.data or 0.0
        product.is_available   = form.is_available.data
        product.save()
        flash(_('Produit « %(name)s » mis à jour.', name=product.name), 'success')
        return redirect(url_for('marketplace.admin_products'))
    form.category.data = product.category.value
    return render_template('marketplace/admin/product_form.html',
                           form=form, product=product, title=_('Modifier le produit'), is_edit=True)


@marketplace_bp.route('/admin/product/<product_id>/delete', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    product = Product.get_by_id(product_id) or abort(404)
    name    = product.name
    delete_product_image(product.image_id)
    product.delete()
    flash(_('Produit « %(name)s » supprimé.', name=name), 'success')
    return redirect(url_for('marketplace.admin_products'))


# ── Admin: Order management ──────────────────────────────────────────────────

@marketplace_bp.route('/admin/orders')
@admin_required
def admin_orders():
    page          = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')

    _pending_vals = [OrderStatus.PENDING.value, OrderStatus.PAYMENT_PENDING.value,
                     OrderStatus.PROCESSING.value]
    _paid_vals    = [OrderStatus.PAID.value, OrderStatus.DELIVERED.value]

    raw_counts     = Order.count_by_statuses()
    total_count    = sum(raw_counts.values())
    pending_count  = sum(raw_counts.get(s, 0) for s in _pending_vals)
    paid_count     = sum(raw_counts.get(s, 0) for s in _paid_vals)
    cancelled_count = raw_counts.get(OrderStatus.CANCELLED.value, 0)

    # Revenue from paid orders
    paid_docs = list(get_col('orders').aggregate([
        {'$match': {'status': {'$in': _paid_vals}}},
        {'$group': {'_id': None, 'total': {'$sum': '$total_xaf'}}},
    ]))
    total_revenue = float(paid_docs[0]['total']) if paid_docs else 0.0

    sf         = None if status_filter == 'all' else status_filter
    pagination = Order.paginate_all(page, per_page=20, status_filter=sf)

    return render_template(
        'marketplace/admin/orders.html',
        orders=pagination.items,
        pagination=pagination,
        status_filter=status_filter,
        total_count=total_count,
        pending_count=pending_count,
        paid_count=paid_count,
        cancelled_count=cancelled_count,
        total_revenue=total_revenue,
        OrderStatus=OrderStatus,
        title=_('Gestion des commandes'),
    )


@marketplace_bp.route('/admin/order/<order_id>/status', methods=['POST'])
@admin_required
def admin_update_order_status(order_id):
    order      = Order.get_by_id(order_id) or abort(404)
    new_status = request.form.get('status')
    try:
        order.status = OrderStatus(new_status)
        order.save()
        send_order_status_update(order)
        flash(_('Statut de la commande %(num)s mis à jour.', num=order.order_number), 'success')
    except ValueError:
        flash(_('Statut invalide.'), 'danger')
    return redirect(url_for('marketplace.admin_orders'))


# ── Admin: Carousel management ──────────────────────────────────────────────

@marketplace_bp.route('/admin/carousel')
@admin_required
def admin_carousel():
    slides = list(get_col('carousel_slides').find().sort([('sort_order', 1), ('created_at', 1)]))
    from app.models.marketplace import CarouselSlide as CS
    return render_template('marketplace/admin/carousel.html',
                           slides=[CS(d) for d in slides], title=_('Gestion du carousel'))


@marketplace_bp.route('/admin/carousel/new', methods=['GET', 'POST'])
@admin_required
def admin_create_slide():
    form = CarouselSlideForm()
    if form.validate_on_submit():
        image_id = None
        if form.image.data and form.image.data.filename:
            try:
                image_id = save_carousel_image(form.image.data)
            except ValueError as exc:
                flash(str(exc), 'danger')
                return render_template('marketplace/admin/carousel_form.html',
                                       form=form, title=_('Nouveau slide'))
        slide = CarouselSlide(
            title=form.title.data.strip(),
            subtitle=form.subtitle.data or None,
            cta_text=form.cta_text.data or None,
            cta_url=form.cta_url.data or '#products',
            is_active=form.is_active.data,
            sort_order=form.sort_order.data or 0,
            image_id=image_id,
            created_by_id=current_user.id,
        )
        slide.save()
        flash(_('Slide « %(t)s » créé.', t=slide.title), 'success')
        return redirect(url_for('marketplace.admin_carousel'))
    return render_template('marketplace/admin/carousel_form.html',
                           form=form, title=_('Nouveau slide'))


@marketplace_bp.route('/admin/carousel/<slide_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_slide(slide_id):
    slide = CarouselSlide.get_by_id(slide_id) or abort(404)
    form  = CarouselSlideForm(obj=slide)
    if form.validate_on_submit():
        if form.image.data and form.image.data.filename:
            try:
                slide.image_id = save_carousel_image(
                    form.image.data, old_file_id=slide.image_id
                )
            except ValueError as exc:
                flash(str(exc), 'danger')
                return render_template('marketplace/admin/carousel_form.html',
                                       form=form, slide=slide, title=_('Modifier le slide'))
        elif form.remove_image.data and slide.image_id:
            delete_carousel_image(slide.image_id)
            slide.image_id = None

        slide.title      = form.title.data.strip()
        slide.subtitle   = form.subtitle.data or None
        slide.cta_text   = form.cta_text.data or None
        slide.cta_url    = form.cta_url.data or '#products'
        slide.is_active  = form.is_active.data
        slide.sort_order = form.sort_order.data or 0
        slide.save()
        flash(_('Slide « %(t)s » mis à jour.', t=slide.title), 'success')
        return redirect(url_for('marketplace.admin_carousel'))
    return render_template('marketplace/admin/carousel_form.html',
                           form=form, slide=slide, title=_('Modifier le slide'))


@marketplace_bp.route('/admin/carousel/<slide_id>/delete', methods=['POST'])
@admin_required
def admin_delete_slide(slide_id):
    slide = CarouselSlide.get_by_id(slide_id) or abort(404)
    title = slide.title
    delete_carousel_image(slide.image_id)
    slide.delete()
    flash(_('Slide « %(t)s » supprimé.', t=title), 'success')
    return redirect(url_for('marketplace.admin_carousel'))


@marketplace_bp.route('/admin/carousel/<slide_id>/toggle', methods=['POST'])
@admin_required
def admin_toggle_slide(slide_id):
    slide = CarouselSlide.get_by_id(slide_id) or abort(404)
    slide.is_active = not slide.is_active
    slide.save()
    status_msg = _('activé') if slide.is_active else _('désactivé')
    flash(_('Slide « %(t)s » %(s)s.', t=slide.title, s=status_msg), 'success')
    return redirect(url_for('marketplace.admin_carousel'))


# ── Payment status polling ────────────────────────────────────────────────────

@marketplace_bp.route('/payment/status/<order_number>')
def payment_status(order_number):
    order = Order.get_by_order_number(order_number) or abort(404)
    pmt   = order.payment

    result = {
        'order_status':   order.status.value,
        'payment_status': pmt.status.value if pmt else 'none',
        'paid':           order.status == OrderStatus.PAID,
    }

    if (pmt
            and pmt.method == PaymentMethod.MTN_MOBILE_MONEY
            and pmt.status == PaymentStatus.PENDING
            and pmt.gateway_reference):
        poll       = check_mtn_payment_status(pmt.gateway_reference)
        mtn_status = poll.get('status', 'PENDING')

        if mtn_status == 'SUCCESSFUL':
            pmt.status       = PaymentStatus.SUCCESS
            pmt.completed_at = datetime.now(timezone.utc)
            order.status     = OrderStatus.PAID
            order.save()
            send_order_status_update(order)
            logger.info('[MTN] Payment confirmed via poll: order=%s ref=%s',
                        order_number, pmt.gateway_reference)

        elif mtn_status == 'FAILED':
            pmt.status             = PaymentStatus.FAILED
            pmt.gateway_response   = {**(pmt.gateway_response or {}), 'poll_result': poll}
            order.save()
            logger.warning('[MTN] Payment failed via poll: order=%s reason=%s',
                           order_number, poll.get('reason'))

        result['order_status']   = order.status.value
        result['payment_status'] = pmt.status.value
        result['paid']           = order.status == OrderStatus.PAID
        result['mtn_status']     = mtn_status

    return jsonify(result)


# ── Webhooks ─────────────────────────────────────────────────────────────────

@marketplace_bp.route('/webhook/orange', methods=['POST'])
@csrf.exempt
def webhook_orange():
    data = request.get_json(silent=True) or request.form.to_dict()
    logger.info('[WEBHOOK:ORANGE] Received: %s', data)

    notif_token = data.get('notif_token', '')
    pay_token   = data.get('pay_token', '')
    order_id    = data.get('order_id', '') or data.get('reference', '')

    if not order_id:
        return jsonify({'error': 'missing order_id'}), 400

    order = Order.get_by_order_number(order_id)
    if not order or not order.payment:
        return jsonify({'error': 'order not found'}), 404

    stored_pay_token = order.payment.gateway_reference or ''
    if not verify_orange_webhook(notif_token, stored_pay_token or pay_token):
        return jsonify({'error': 'invalid token'}), 403

    status_code = str(data.get('status', '')).upper()
    if status_code in ('', '00', 'SUCCESSFUL', 'SUCCESS'):
        order.payment.status       = PaymentStatus.SUCCESS
        order.payment.completed_at = datetime.now(timezone.utc)
        order.payment.gateway_response = {**(order.payment.gateway_response or {}), 'webhook': data}
        order.status = OrderStatus.PAID
        order.save()
        send_order_status_update(order)
        logger.info('[WEBHOOK:ORANGE] Order %s marked PAID', order_id)
    else:
        order.payment.status = PaymentStatus.FAILED
        order.payment.gateway_response = {**(order.payment.gateway_response or {}), 'webhook': data}
        order.save()
        logger.warning('[WEBHOOK:ORANGE] Order %s payment failed, status=%s', order_id, status_code)

    return jsonify({'received': True}), 200


@marketplace_bp.route('/webhook/mtn', methods=['POST'])
@csrf.exempt
def webhook_mtn():
    data = request.get_json(silent=True) or {}
    logger.info('[WEBHOOK:MTN] Received: %s', data)

    reference_id = data.get('referenceId', '') or data.get('externalId', '')
    mtn_status   = str(data.get('status', '')).upper()

    if not reference_id:
        return jsonify({'error': 'missing referenceId'}), 400

    order = Order.get_by_payment_reference(reference_id)
    if not order:
        return jsonify({'error': 'payment not found'}), 404

    order.payment.gateway_response = {**(order.payment.gateway_response or {}), 'webhook': data}

    if mtn_status == 'SUCCESSFUL':
        order.payment.status       = PaymentStatus.SUCCESS
        order.payment.completed_at = datetime.now(timezone.utc)
        order.status               = OrderStatus.PAID
        order.save()
        send_order_status_update(order)
        logger.info('[WEBHOOK:MTN] Order %s marked PAID via webhook', order.order_number)
    elif mtn_status == 'FAILED':
        order.payment.status = PaymentStatus.FAILED
        order.save()
        logger.warning('[WEBHOOK:MTN] Order %s payment failed via webhook', order.order_number)
    else:
        order.save()

    return jsonify({'received': True}), 200


# ── Product search (AJAX) ─────────────────────────────────────────────────────

@marketplace_bp.route('/search')
def search():
    q   = request.args.get('q', '').strip()
    cat = request.args.get('cat', '').strip()

    cat_enum = None
    if cat:
        try:
            cat_enum = ProductCategory(cat)
        except ValueError:
            pass

    pagination = Product.paginate_available(page=1, per_page=60, category=cat_enum, q=q)

    def _serialize(p):
        return {
            'id':             p.id,
            'name':           p.name,
            'description':    p.description or '',
            'category':       p.category.value,
            'category_label': p.category_label(),
            'category_icon':  p.category_icon(),
            'price_xaf':      float(p.price_xaf),
            'unit':           p.unit,
            'stock_quantity': p.stock_quantity,
            'image_url':      url_for('marketplace.serve_image', file_id=str(p.image_id))
                              if p.image_id else None,
            'add_cart_url':   url_for('marketplace.cart_add'),
            'detail_url':     url_for('marketplace.product_detail', product_id=p.id),
        }

    return jsonify({'products': [_serialize(p) for p in pagination.items]})


# ── Admin: Analytics ─────────────────────────────────────────────────────────

@marketplace_bp.route('/admin/analytics')
@admin_required
def admin_analytics():
    cutoff_30d   = datetime.now(timezone.utc) - timedelta(days=30)
    paid_statuses = [OrderStatus.PAID.value, OrderStatus.PROCESSING.value,
                     OrderStatus.SHIPPED.value, OrderStatus.DELIVERED.value]

    # Revenue per day — last 30 days
    rev_pipeline = [
        {'$match': {'created_at': {'$gte': cutoff_30d}, 'status': {'$in': paid_statuses}}},
        {'$group': {
            '_id':     {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at'}},
            'revenue': {'$sum': '$total_xaf'},
        }},
        {'$sort': {'_id': 1}},
    ]
    rev_rows       = list(get_col('orders').aggregate(rev_pipeline))
    revenue_labels = [r['_id'] for r in rev_rows]
    revenue_data   = [float(r['revenue']) for r in rev_rows]

    # Orders by status
    status_rows   = list(get_col('orders').aggregate([{'$group': {'_id': '$status', 'n': {'$sum': 1}}}]))
    status_labels = [r['_id'] for r in status_rows]
    status_data   = [r['n'] for r in status_rows]

    # Top 5 products by revenue
    top_pipeline = [
        {'$unwind': '$items'},
        {'$group': {
            '_id':       '$items.product_name',
            'total_rev': {'$sum': '$items.subtotal_xaf'},
            'total_qty': {'$sum': '$items.quantity'},
        }},
        {'$sort': {'total_rev': -1}},
        {'$limit': 5},
    ]
    top_raw = list(get_col('orders').aggregate(top_pipeline))
    from types import SimpleNamespace
    top_products = [
        SimpleNamespace(
            product_name=r['_id'],
            total_rev=float(r['total_rev']),
            total_qty=float(r['total_qty']),
        )
        for r in top_raw
    ]

    # Payment method distribution
    pay_rows   = list(get_col('orders').aggregate([
        {'$group': {'_id': '$payment_method', 'n': {'$sum': 1}}}
    ]))
    pay_labels = [r['_id'] for r in pay_rows]
    pay_data   = [r['n'] for r in pay_rows]

    # KPI cards
    _pending_kpi = [OrderStatus.PENDING.value, OrderStatus.PAYMENT_PENDING.value]
    kpi_pipeline = [
        {'$facet': {
            'total_orders': [{'$count': 'n'}],
            'total_revenue': [
                {'$match': {'status': {'$in': paid_statuses}}},
                {'$group': {'_id': None, 's': {'$sum': '$total_xaf'}}},
            ],
            'pending_orders': [
                {'$match': {'status': {'$in': _pending_kpi}}},
                {'$count': 'n'},
            ],
            'avg_order': [
                {'$group': {'_id': None, 'avg': {'$avg': '$total_xaf'}}},
            ],
        }}
    ]
    kpi_raw     = list(get_col('orders').aggregate(kpi_pipeline))[0]
    total_orders  = kpi_raw['total_orders'][0]['n'] if kpi_raw['total_orders'] else 0
    total_revenue = float(kpi_raw['total_revenue'][0]['s']) if kpi_raw['total_revenue'] else 0.0
    pending_orders = kpi_raw['pending_orders'][0]['n'] if kpi_raw['pending_orders'] else 0
    avg_order     = float(kpi_raw['avg_order'][0]['avg']) if kpi_raw['avg_order'] else 0.0

    return render_template(
        'marketplace/admin/analytics.html',
        revenue_labels=revenue_labels,
        revenue_data=revenue_data,
        status_labels=status_labels,
        status_data=status_data,
        top_products=top_products,
        pay_labels=pay_labels,
        pay_data=pay_data,
        total_revenue=total_revenue,
        total_orders=int(total_orders),
        pending_orders=int(pending_orders),
        avg_order=avg_order,
        title=_('Analytiques'),
    )
