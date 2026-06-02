"""
OmniFarm Hub — Main Entry Point
Bootstraps MongoDB indexes then starts the Flask dev server.
"""
import os
import sys
import logging

from app import create_app

app = create_app()

DIVIDER = '=' * 62


def _ensure_indexes() -> None:
    """Create MongoDB indexes for all collections (idempotent).
    Uses a dedicated client with w=1 so index creation doesn't block
    waiting for majority acknowledgment from secondaries.
    """
    from pymongo import ASCENDING, MongoClient
    from config import Config

    client = MongoClient(Config.MONGO_URI_BOOTSTRAP)
    db = client[Config.MONGO_DB]

    # users
    db.users.create_index('username', unique=True)
    db.users.create_index('email', unique=True)

    # ponds
    db.ponds.create_index('status')
    db.ponds.create_index('created_at')

    # aquaculture_records
    db.aquaculture_records.create_index('pond_id')
    db.aquaculture_records.create_index([('pond_id', ASCENDING), ('record_date', ASCENDING)])

    # flocks
    db.flocks.create_index('status')
    db.flocks.create_index('created_at')

    # poultry_records
    db.poultry_records.create_index('flock_id')
    db.poultry_records.create_index([('flock_id', ASCENDING), ('record_date', ASCENDING)])

    # rabbit_batches
    db.rabbit_batches.create_index('status')
    db.rabbit_batches.create_index('created_at')

    # cuniculture_records
    db.cuniculture_records.create_index('batch_id')
    db.cuniculture_records.create_index([('batch_id', ASCENDING), ('record_date', ASCENDING)])

    # products
    db.products.create_index('is_available')
    db.products.create_index('category')
    db.products.create_index('created_at')

    # orders
    db.orders.create_index('order_number', unique=True)
    db.orders.create_index('customer_id')
    db.orders.create_index('status')
    db.orders.create_index('created_at')
    db.orders.create_index('payment.gateway_reference')

    # carousel_slides
    db.carousel_slides.create_index([('sort_order', ASCENDING), ('created_at', ASCENDING)])

    # finance_entries
    db.finance_entries.create_index('entry_date')
    db.finance_entries.create_index('entry_type')
    db.finance_entries.create_index('production_scope')

    # health_events
    db.health_events.create_index('event_date')
    db.health_events.create_index('next_due_date')
    db.health_events.create_index('production_unit')
    db.health_events.create_index('event_type')

    client.close()
    app.logger.info('[ BOOTSTRAP ] MongoDB indexes verified / created.')


def _bootstrap() -> None:
    with app.app_context():
        try:
            app.logger.info('[ BOOTSTRAP ] Starting Zero-Touch Initialization...')
            _ensure_indexes()

            from app.db import get_col
            if get_col('users').count_documents({}) == 0:
                app.logger.warning(
                    '[ BOOTSTRAP ] No users found — open http://0.0.0.0:5000/setup '
                    'in your browser to create the first administrator account.'
                )

        except Exception as exc:
            app.logger.critical(
                f'[ BOOTSTRAP ] Initialization failed: {exc}', exc_info=True
            )
            sys.exit(1)


if __name__ == '__main__':
    _bootstrap()

    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1')

    app.logger.info(
        f'[ SERVER ] Starting OmniFarm Hub on http://0.0.0.0:5000 '
        f'(debug={debug_mode})'
    )

    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=debug_mode,
    )
