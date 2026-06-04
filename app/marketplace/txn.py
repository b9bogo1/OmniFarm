"""
Transactional checkout for OmniFarm Hub.

Atomically:
  1. Verifies and decrements stock_quantity for each ordered item.
  2. Inserts the Order document.

Uses a MongoDB multi-document transaction when running on a replica set.
Falls back to non-transactional operations on single-node / test environments
where sessions or transactions are not supported.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pymongo.errors import OperationFailure, ConfigurationError

if TYPE_CHECKING:
    from app.models.marketplace import Order, Product

logger = logging.getLogger(__name__)


class InsufficientStockError(Exception):
    def __init__(self, product_name: str, available: float, requested: float):
        self.product_name = product_name
        self.available = available
        self.requested = requested
        super().__init__(
            f"Stock insuffisant pour « {product_name} » "
            f"(disponible : {available}, demandé : {requested})"
        )


def _stock_check_and_insert(session, mongo_db, order: "Order", items: list) -> None:
    """Core logic: decrement stock and insert order, optionally inside a session."""
    from app.db import oid
    for product, qty in items:
        result = mongo_db["products"].update_one(
            {
                "_id": oid(product.id),
                "stock_quantity": {"$gte": qty},
                "is_available": True,
            },
            {"$inc": {"stock_quantity": -qty}},
            **({"session": session} if session is not None else {}),
        )
        if result.matched_count == 0:
            current = mongo_db["products"].find_one(
                {"_id": oid(product.id)},
                {"stock_quantity": 1},
                **({"session": session} if session is not None else {}),
            )
            available = float(current["stock_quantity"]) if current else 0.0
            raise InsufficientStockError(product.name, available, qty)

    doc = order._to_doc()
    result = mongo_db["orders"].insert_one(
        doc,
        **({"session": session} if session is not None else {}),
    )
    object.__setattr__(order, "_id", result.inserted_id)


def _is_transaction_unsupported(exc: Exception) -> bool:
    """Return True if the error means the server doesn't support transactions."""
    msg = str(exc).lower()
    keywords = (
        "transaction", "not supported", "notimplemented",
        "replicaset", "replica set", "no replicationinfo",
        "errcode: 20", "command not found",
    )
    return isinstance(exc, (NotImplementedError, ConfigurationError)) or any(
        k in msg for k in keywords
    )


def checkout_transact(order: "Order", items: list[tuple["Product", float]]) -> "Order":
    """Atomically decrement stock for each item and insert the order.

    On a replica set this runs inside a multi-document transaction.
    On single-node / test environments the same logic runs without a session
    (best-effort; still raises InsufficientStockError on stock violations).

    Args:
        order:  A fully-populated Order instance (not yet saved).
        items:  List of (Product, qty) pairs matching order.items.

    Returns:
        The same Order instance, now with _id set.

    Raises:
        InsufficientStockError: if any product has less stock than requested.
    """
    from app.extensions import mongo

    try:
        with mongo.cx.start_session() as session:
            try:
                with session.start_transaction():
                    _stock_check_and_insert(session, mongo.db, order, items)
            except (OperationFailure, NotImplementedError, Exception) as exc:
                if _is_transaction_unsupported(exc):
                    logger.debug(
                        "[TXN] Transactions not available (%s), running without session.",
                        type(exc).__name__,
                    )
                    _stock_check_and_insert(None, mongo.db, order, items)
                else:
                    raise
    except (AttributeError, NotImplementedError, ConfigurationError) as exc:
        # start_session itself not available (e.g. mongomock)
        logger.debug(
            "[TXN] Sessions not available (%s), running without session.",
            type(exc).__name__,
        )
        _stock_check_and_insert(None, mongo.db, order, items)

    logger.info("[TXN] Order %s committed (items=%d)", order.order_number, len(items))
    return order
