"""
Session-based cart — no DB table required.
Cart state: session['omnifarm_cart'] = {str(product_id): quantity}
Product IDs are now MongoDB ObjectId strings.
"""
from flask import session
from app.models.marketplace import Product

_KEY = 'omnifarm_cart'


class Cart:
    def __init__(self):
        if _KEY not in session:
            session[_KEY] = {}

    @property
    def _data(self) -> dict:
        return session.setdefault(_KEY, {})

    def add(self, product_id: str, quantity: float) -> bool:
        product = Product.get_by_id(product_id)
        if not product or not product.is_available:
            return False
        key = str(product_id)
        self._data[key] = self._data.get(key, 0.0) + quantity
        session.modified = True
        return True

    def update(self, product_id: str, quantity: float) -> None:
        key = str(product_id)
        if quantity <= 0:
            self._data.pop(key, None)
        else:
            self._data[key] = quantity
        session.modified = True

    def remove(self, product_id: str) -> None:
        self._data.pop(str(product_id), None)
        session.modified = True

    def clear(self) -> None:
        session[_KEY] = {}
        session.modified = True

    def get_items(self) -> list[tuple[Product, float]]:
        data = self._data
        if not data:
            return []
        id_list = list(data.keys())
        products_map = {p.id: p for p in Product.find_by_ids(id_list)}
        items = []
        stale = []
        for pid_str, qty in data.items():
            product = products_map.get(pid_str)
            if product and product.is_available:
                items.append((product, qty))
            else:
                stale.append(pid_str)
        for k in stale:
            data.pop(k, None)
        if stale:
            session.modified = True
        return items

    def get_total(self) -> float:
        return sum(p.price_float * qty for p, qty in self.get_items())

    def get_count(self) -> int:
        return int(sum(self._data.values()))

    def is_empty(self) -> bool:
        return not self._data


def get_cart_count() -> int:
    return int(sum(session.get(_KEY, {}).values()))
