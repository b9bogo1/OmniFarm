import enum
from datetime import datetime, timezone
from app.db import get_col, oid, Pagination


class ProductCategory(enum.Enum):
    FISH    = 'fish'
    POULTRY = 'poultry'
    RABBIT  = 'rabbit'
    EGGS    = 'eggs'
    OTHER   = 'other'


class OrderStatus(enum.Enum):
    PENDING         = 'pending'
    PAYMENT_PENDING = 'payment_pending'
    PAID            = 'paid'
    PROCESSING      = 'processing'
    SHIPPED         = 'shipped'
    DELIVERED       = 'delivered'
    CANCELLED       = 'cancelled'


class PaymentMethod(enum.Enum):
    ORANGE_MONEY      = 'orange_money'
    MTN_MOBILE_MONEY  = 'mtn_mobile_money'
    CASH_ON_DELIVERY  = 'cash_on_delivery'


class PaymentStatus(enum.Enum):
    PENDING  = 'pending'
    SUCCESS  = 'success'
    FAILED   = 'failed'
    REFUNDED = 'refunded'


# ── Product ───────────────────────────────────────────────────────────────────

class Product:
    def __init__(self, doc=None, **kw):
        doc = {**(doc or {}), **kw}
        object.__setattr__(self, '_id', doc.get('_id'))
        self.name           = doc.get('name', '')
        self.description    = doc.get('description')
        _c = doc.get('category', ProductCategory.OTHER.value)
        self.category = ProductCategory(_c) if isinstance(_c, str) else _c
        self.price_xaf      = float(doc.get('price_xaf', 0))
        self.unit           = doc.get('unit', 'kg')
        self.stock_quantity = float(doc.get('stock_quantity', 0.0))
        self.is_available   = doc.get('is_available', True)
        self.image_filename = doc.get('image_filename')
        self.created_at     = doc.get('created_at', datetime.now(timezone.utc))
        self.created_by_id  = doc.get('created_by_id')

    @property
    def id(self):
        return str(self._id) if self._id else None

    @property
    def price_float(self) -> float:
        return float(self.price_xaf) if self.price_xaf else 0.0

    def category_label(self) -> str:
        from flask_babel import gettext as _
        labels = {
            ProductCategory.FISH:    _('Poisson'),
            ProductCategory.POULTRY: _('Volaille'),
            ProductCategory.RABBIT:  _('Lapin'),
            ProductCategory.EGGS:    _('Œufs'),
            ProductCategory.OTHER:   _('Autre'),
        }
        return labels.get(self.category, self.category.value)

    def category_icon(self) -> str:
        icons = {
            ProductCategory.FISH:    '🐟',
            ProductCategory.POULTRY: '🐔',
            ProductCategory.RABBIT:  '🐇',
            ProductCategory.EGGS:    '🥚',
            ProductCategory.OTHER:   '🌿',
        }
        return icons.get(self.category, '📦')

    def save(self) -> 'Product':
        col = get_col('products')
        doc = self._to_doc()
        if self._id:
            col.replace_one({'_id': self._id}, doc)
        else:
            result = col.insert_one(doc)
            object.__setattr__(self, '_id', result.inserted_id)
        return self

    def delete(self) -> None:
        if self._id:
            get_col('products').delete_one({'_id': self._id})

    def _to_doc(self) -> dict:
        return {
            'name':           self.name,
            'description':    self.description,
            'category':       self.category.value,
            'price_xaf':      float(self.price_xaf),
            'unit':           self.unit,
            'stock_quantity': float(self.stock_quantity),
            'is_available':   self.is_available,
            'image_filename': self.image_filename,
            'created_at':     self.created_at,
            'created_by_id':  self.created_by_id,
        }

    @classmethod
    def get_by_id(cls, id_str) -> 'Product | None':
        doc = get_col('products').find_one({'_id': oid(id_str)})
        return cls(doc) if doc else None

    @classmethod
    def paginate_available(cls, page: int, per_page: int = 20,
                           category=None, q: str = '') -> Pagination:
        filt: dict = {'is_available': True}
        if category:
            filt['category'] = category.value if hasattr(category, 'value') else category
        if q:
            filt['$or'] = [
                {'name': {'$regex': q, '$options': 'i'}},
                {'description': {'$regex': q, '$options': 'i'}},
            ]
        col = get_col('products')
        total = col.count_documents(filt)
        docs = list(col.find(filt).sort('created_at', -1)
                    .skip((page - 1) * per_page).limit(per_page))
        return Pagination([cls(d) for d in docs], total, page, per_page)

    @classmethod
    def paginate_all(cls, page: int, per_page: int = 20) -> Pagination:
        col = get_col('products')
        total = col.count_documents({})
        docs = list(col.find().sort('created_at', -1)
                    .skip((page - 1) * per_page).limit(per_page))
        return Pagination([cls(d) for d in docs], total, page, per_page)

    @classmethod
    def count_all(cls) -> int:
        return get_col('products').count_documents({})

    @classmethod
    def count_available(cls) -> int:
        return get_col('products').count_documents({'is_available': True})

    @classmethod
    def count_low_stock(cls) -> int:
        return get_col('products').count_documents({
            'stock_quantity': {'$gt': 0, '$lte': 5},
        })

    @classmethod
    def find_by_ids(cls, id_list: list) -> list['Product']:
        oids = [oid(i) for i in id_list if oid(i)]
        docs = list(get_col('products').find({'_id': {'$in': oids}}))
        return [cls(d) for d in docs]

    def __repr__(self) -> str:
        return f'<Product {self.name!r}>'


# ── Payment sub-document ──────────────────────────────────────────────────────

class Payment:
    """Embedded in Order — not stored in its own collection."""

    def __init__(self, doc=None, **kw):
        doc = {**(doc or {}), **kw}
        _m = doc.get('method', PaymentMethod.CASH_ON_DELIVERY.value)
        self.method = PaymentMethod(_m) if isinstance(_m, str) else _m
        self.phone_number = doc.get('phone_number')
        self.amount_xaf   = float(doc.get('amount_xaf', 0))
        _ps = doc.get('status', PaymentStatus.PENDING.value)
        self.status = PaymentStatus(_ps) if isinstance(_ps, str) else _ps
        self.gateway_reference = doc.get('gateway_reference')
        self.gateway_response  = doc.get('gateway_response')
        self.initiated_at      = doc.get('initiated_at', datetime.now(timezone.utc))
        self.completed_at      = doc.get('completed_at')

    def to_subdoc(self) -> dict:
        return {
            'method':             self.method.value,
            'phone_number':       self.phone_number,
            'amount_xaf':         float(self.amount_xaf),
            'status':             self.status.value,
            'gateway_reference':  self.gateway_reference,
            'gateway_response':   self.gateway_response,
            'initiated_at':       self.initiated_at,
            'completed_at':       self.completed_at,
        }

    def __repr__(self) -> str:
        return f'<Payment method={self.method.value} status={self.status.value}>'


# ── OrderItem sub-document ────────────────────────────────────────────────────

class OrderItem:
    """Embedded in Order."""

    def __init__(self, doc=None, **kw):
        doc = {**(doc or {}), **kw}
        self.product_id      = doc.get('product_id')
        self.product_name    = doc.get('product_name', '')
        self.product_unit    = doc.get('product_unit', '')
        self.unit_price_xaf  = float(doc.get('unit_price_xaf', 0))
        self.quantity        = float(doc.get('quantity', 0))
        self.subtotal_xaf    = float(doc.get('subtotal_xaf', 0))

    @property
    def subtotal_float(self) -> float:
        return self.subtotal_xaf

    def to_subdoc(self) -> dict:
        return {
            'product_id':     self.product_id,
            'product_name':   self.product_name,
            'product_unit':   self.product_unit,
            'unit_price_xaf': self.unit_price_xaf,
            'quantity':       self.quantity,
            'subtotal_xaf':   self.subtotal_xaf,
        }

    def __repr__(self) -> str:
        return f'<OrderItem {self.product_name!r} ×{self.quantity}>'


# ── Order ─────────────────────────────────────────────────────────────────────

class Order:
    def __init__(self, doc=None, **kw):
        doc = {**(doc or {}), **kw}
        object.__setattr__(self, '_id', doc.get('_id'))
        self.order_number    = doc.get('order_number', '')
        self.customer_id     = doc.get('customer_id')
        self.customer_name   = doc.get('customer_name', '')
        self.customer_phone  = doc.get('customer_phone', '')
        self.customer_address = doc.get('customer_address')
        _s = doc.get('status', OrderStatus.PENDING.value)
        self.status = OrderStatus(_s) if isinstance(_s, str) else _s
        _pm = doc.get('payment_method')
        self.payment_method = PaymentMethod(_pm) if isinstance(_pm, str) and _pm else _pm
        self.total_xaf       = float(doc.get('total_xaf', 0))
        self.notes           = doc.get('notes')
        self.created_at      = doc.get('created_at', datetime.now(timezone.utc))
        # Embedded sub-documents
        raw_items = doc.get('items', [])
        self.items = [OrderItem(i) for i in raw_items]
        raw_pay = doc.get('payment')
        self.payment = Payment(raw_pay) if raw_pay else None

    @property
    def id(self):
        return str(self._id) if self._id else None

    @property
    def total_float(self) -> float:
        return float(self.total_xaf)

    def status_label(self) -> str:
        from flask_babel import gettext as _
        labels = {
            OrderStatus.PENDING:         _('En attente'),
            OrderStatus.PAYMENT_PENDING: _('Paiement en cours'),
            OrderStatus.PAID:            _('Payée'),
            OrderStatus.PROCESSING:      _('En traitement'),
            OrderStatus.SHIPPED:         _('Expédiée'),
            OrderStatus.DELIVERED:       _('Livrée'),
            OrderStatus.CANCELLED:       _('Annulée'),
        }
        return labels.get(self.status, self.status.value)

    def save(self) -> 'Order':
        col = get_col('orders')
        doc = self._to_doc()
        if self._id:
            col.replace_one({'_id': self._id}, doc)
        else:
            result = col.insert_one(doc)
            object.__setattr__(self, '_id', result.inserted_id)
        return self

    def delete(self) -> None:
        if self._id:
            get_col('orders').delete_one({'_id': self._id})

    def _to_doc(self) -> dict:
        return {
            'order_number':    self.order_number,
            'customer_id':     self.customer_id,
            'customer_name':   self.customer_name,
            'customer_phone':  self.customer_phone,
            'customer_address': self.customer_address,
            'status':          self.status.value,
            'payment_method':  self.payment_method.value if self.payment_method else None,
            'total_xaf':       float(self.total_xaf),
            'notes':           self.notes,
            'created_at':      self.created_at,
            'items':           [i.to_subdoc() for i in self.items],
            'payment':         self.payment.to_subdoc() if self.payment else None,
        }

    @classmethod
    def get_by_id(cls, id_str) -> 'Order | None':
        doc = get_col('orders').find_one({'_id': oid(id_str)})
        return cls(doc) if doc else None

    @classmethod
    def get_by_order_number(cls, number: str) -> 'Order | None':
        doc = get_col('orders').find_one({'order_number': number})
        return cls(doc) if doc else None

    @classmethod
    def get_by_payment_reference(cls, ref: str) -> 'Order | None':
        doc = get_col('orders').find_one({'payment.gateway_reference': ref})
        return cls(doc) if doc else None

    @classmethod
    def paginate_all(cls, page: int, per_page: int = 20,
                     status_filter=None) -> Pagination:
        filt = _build_status_filter(status_filter)
        col = get_col('orders')
        total = col.count_documents(filt)
        docs = list(col.find(filt).sort('created_at', -1)
                    .skip((page - 1) * per_page).limit(per_page))
        return Pagination([cls(d) for d in docs], total, page, per_page)

    @classmethod
    def paginate_by_customer(cls, customer_id: str, page: int,
                             per_page: int = 10, status_filter=None) -> Pagination:
        filt = {'customer_id': customer_id}
        filt.update(_build_status_filter(status_filter))
        col = get_col('orders')
        total = col.count_documents(filt)
        docs = list(col.find(filt).sort('created_at', -1)
                    .skip((page - 1) * per_page).limit(per_page))
        return Pagination([cls(d) for d in docs], total, page, per_page)

    @classmethod
    def count_by_customer_and_statuses(cls, customer_id: str) -> dict:
        pipeline = [
            {'$match': {'customer_id': customer_id}},
            {'$group': {'_id': '$status', 'n': {'$sum': 1}}},
        ]
        return {row['_id']: row['n']
                for row in get_col('orders').aggregate(pipeline)}

    @classmethod
    def count_by_statuses(cls) -> dict:
        pipeline = [{'$group': {'_id': '$status', 'n': {'$sum': 1}}}]
        return {row['_id']: row['n']
                for row in get_col('orders').aggregate(pipeline)}

    @classmethod
    def recent(cls, limit: int = 5) -> list['Order']:
        docs = list(get_col('orders').find().sort('created_at', -1).limit(limit))
        return [cls(d) for d in docs]

    @classmethod
    def count_all(cls) -> int:
        return get_col('orders').count_documents({})

    def __repr__(self) -> str:
        return f'<Order {self.order_number}>'


def _build_status_filter(status_filter) -> dict:
    _pending_s = [OrderStatus.PENDING.value, OrderStatus.PAYMENT_PENDING.value,
                  OrderStatus.PROCESSING.value]
    _paid_s    = [OrderStatus.PAID.value, OrderStatus.DELIVERED.value]
    if status_filter == 'pending':
        return {'status': {'$in': _pending_s}}
    if status_filter == 'paid' or status_filter == 'done':
        return {'status': {'$in': _paid_s}}
    if status_filter == 'cancelled':
        return {'status': OrderStatus.CANCELLED.value}
    return {}


# ── Carousel Slide ────────────────────────────────────────────────────────────

class CarouselSlide:
    def __init__(self, doc=None, **kw):
        doc = {**(doc or {}), **kw}
        object.__setattr__(self, '_id', doc.get('_id'))
        self.title          = doc.get('title', '')
        self.subtitle       = doc.get('subtitle')
        self.image_filename = doc.get('image_filename')
        self.cta_text       = doc.get('cta_text')
        self.cta_url        = doc.get('cta_url', '#products')
        self.is_active      = doc.get('is_active', True)
        self.sort_order     = doc.get('sort_order', 0)
        self.created_at     = doc.get('created_at', datetime.now(timezone.utc))
        self.created_by_id  = doc.get('created_by_id')

    @property
    def id(self):
        return str(self._id) if self._id else None

    def save(self) -> 'CarouselSlide':
        col = get_col('carousel_slides')
        doc = self._to_doc()
        if self._id:
            col.replace_one({'_id': self._id}, doc)
        else:
            result = col.insert_one(doc)
            object.__setattr__(self, '_id', result.inserted_id)
        return self

    def delete(self) -> None:
        if self._id:
            get_col('carousel_slides').delete_one({'_id': self._id})

    def _to_doc(self) -> dict:
        return {
            'title':          self.title,
            'subtitle':       self.subtitle,
            'image_filename': self.image_filename,
            'cta_text':       self.cta_text,
            'cta_url':        self.cta_url,
            'is_active':      self.is_active,
            'sort_order':     self.sort_order,
            'created_at':     self.created_at,
            'created_by_id':  self.created_by_id,
        }

    @classmethod
    def get_by_id(cls, id_str) -> 'CarouselSlide | None':
        doc = get_col('carousel_slides').find_one({'_id': oid(id_str)})
        return cls(doc) if doc else None

    @classmethod
    def find_active(cls) -> list['CarouselSlide']:
        docs = list(get_col('carousel_slides')
                    .find({'is_active': True})
                    .sort([('sort_order', 1), ('created_at', 1)]))
        return [cls(d) for d in docs]

    @classmethod
    def find_all(cls) -> list['CarouselSlide']:
        docs = list(get_col('carousel_slides')
                    .find()
                    .sort([('sort_order', 1), ('created_at', 1)]))
        return [cls(d) for d in docs]

    def __repr__(self) -> str:
        return f'<CarouselSlide {self.title!r}>'


# ── Order number generator ────────────────────────────────────────────────────

def generate_order_number() -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"OMF-{year}-"
    last = get_col('orders').find_one(
        {'order_number': {'$regex': f'^{prefix}'}},
        sort=[('_id', -1)],
    )
    if last:
        try:
            seq = int(last['order_number'].split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:06d}"
