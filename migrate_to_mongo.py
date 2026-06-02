#!/usr/bin/env python
"""
OmniFarm Hub — MariaDB → MongoDB Migration Script
==================================================
Reads every table from the existing MariaDB (10.100.200.20 / omnifarm_db)
and inserts all rows into the new MongoDB replica set.

Run ONCE before switching the app to MongoDB:
    python migrate_to_mongo.py

Safe to re-run: collections are dropped and re-created each time,
so you can run it multiple times during the cut-over window.

Requirements (in addition to project venv):
    pip install pymysql pymongo python-dotenv
"""
import sys
import logging
from datetime import datetime, timezone, date as date_type

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('migrate')

# ── Load .env ─────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()
import os

# ── MariaDB connection ────────────────────────────────────────────────────────
MYSQL_HOST = '10.100.200.20'
MYSQL_PORT = 3306
MYSQL_USER = 'admin'
MYSQL_PASS = 'piidou'
MYSQL_DB   = 'omnifarm_db'

# ── MongoDB connection ────────────────────────────────────────────────────────
MONGO_USER   = os.environ.get('MONGO_USER', 'b9bogo1')
MONGO_PASS   = os.environ.get('MONGO_PASS', 'piidou')
MONGO_RS     = os.environ.get('MONGO_RS_NAME', 'sr0')
MONGO_DB     = os.environ.get('MONGO_DB', 'omnifarm_db')
# Connect directly to the primary (mongo-2 = 10.9.4.12) so we don't need
# hostname DNS resolution for mongo-1/mongo-2/mongo-3.
# directConnection=True skips RS topology discovery entirely.
MONGO_URI    = (
    f"mongodb://{MONGO_USER}:{MONGO_PASS}@"
    f"10.9.4.12:27017"
    f"/{MONGO_DB}"
    f"?authSource=admin"
    f"&directConnection=true"
    f"&connectTimeoutMS=10000&serverSelectionTimeoutMS=10000"
)


def to_dt(v):
    """Convert date/datetime → UTC datetime for MongoDB storage."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, date_type):
        return datetime(v.year, v.month, v.day, tzinfo=timezone.utc)
    return v


def connect_mysql():
    import pymysql
    log.info('Connecting to MariaDB %s/%s …', MYSQL_HOST, MYSQL_DB)
    conn = pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASS,
        db=MYSQL_DB, charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
    )
    log.info('MariaDB connected.')
    return conn


def connect_mongo():
    from pymongo import MongoClient
    log.info('Connecting to MongoDB replica set %s …', MONGO_RS)
    client = MongoClient(MONGO_URI)
    # Ping to validate
    client.admin.command('ping')
    db = client[MONGO_DB]
    log.info('MongoDB connected → database: %s', MONGO_DB)
    return db


# ── ID mapping: old integer PK → new str(ObjectId) ───────────────────────────
# We generate a deterministic mapping per table so cross-table FK references
# stay consistent.  The strategy: insert each doc and record its inserted _id.

def migrate_users(cur, mdb):
    cur.execute("SELECT * FROM users")
    rows = cur.fetchall()
    log.info('Migrating %d users …', len(rows))
    mdb.users.drop()
    id_map = {}    # old int id → new ObjectId str
    for row in rows:
        doc = {
            'username':      row['username'],
            'email':         row['email'],
            'password_hash': row['password_hash'],
            'role':          row['role'],
            'is_active':     bool(row['is_active']),
            'language':      row['language'] or 'fr',
            'theme':         row['theme'] or 'light',
            'created_at':    to_dt(row['created_at']),
            'last_login':    to_dt(row['last_login']),
        }
        result = mdb.users.insert_one(doc)
        id_map[row['id']] = str(result.inserted_id)
    log.info('  → %d users inserted.', len(id_map))
    return id_map


def migrate_ponds(cur, mdb):
    cur.execute("SELECT * FROM ponds")
    rows = cur.fetchall()
    log.info('Migrating %d ponds …', len(rows))
    mdb.ponds.drop()
    id_map = {}
    for row in rows:
        doc = {
            'name':              row['name'],
            'species':           row['species'],
            'capacity_m3':       row['capacity_m3'],
            'status':            row['status'],
            'installation_date': to_dt(row['installation_date']),
            'notes':             row['notes'],
            'created_at':        to_dt(row['created_at']),
        }
        result = mdb.ponds.insert_one(doc)
        id_map[row['id']] = str(result.inserted_id)
    log.info('  → %d ponds inserted.', len(id_map))
    return id_map


def migrate_aquaculture_records(cur, mdb, pond_map, user_map):
    cur.execute("SELECT * FROM aquaculture_records")
    rows = cur.fetchall()
    log.info('Migrating %d aquaculture records …', len(rows))
    mdb.aquaculture_records.drop()
    if not rows:
        return
    docs = []
    for row in rows:
        docs.append({
            'pond_id':              pond_map.get(row['pond_id']),
            'recorded_by_id':       user_map.get(row['recorded_by_id']),
            'record_date':          to_dt(row['record_date']),
            'current_count':        row['current_count'],
            'avg_weight_g':         float(row['avg_weight_g']) if row['avg_weight_g'] is not None else None,
            'feed_quantity_kg':     float(row['feed_quantity_kg']) if row['feed_quantity_kg'] is not None else None,
            'feed_type':            row['feed_type'],
            'mortality_count':      row['mortality_count'] or 0,
            'mortality_cause':      row['mortality_cause'],
            'water_temp_c':         float(row['water_temp_c']) if row['water_temp_c'] is not None else None,
            'ph':                   float(row['ph']) if row['ph'] is not None else None,
            'dissolved_oxygen_mgl': float(row['dissolved_oxygen_mgl']) if row['dissolved_oxygen_mgl'] is not None else None,
            'turbidity_ntu':        float(row['turbidity_ntu']) if row['turbidity_ntu'] is not None else None,
            'notes':                row['notes'],
            'created_at':           to_dt(row['created_at']),
        })
    mdb.aquaculture_records.insert_many(docs)
    log.info('  → %d aquaculture records inserted.', len(docs))


def migrate_flocks(cur, mdb):
    cur.execute("SELECT * FROM flocks")
    rows = cur.fetchall()
    log.info('Migrating %d flocks …', len(rows))
    mdb.flocks.drop()
    id_map = {}
    for row in rows:
        doc = {
            'name':           row['name'],
            'species':        row['species'],
            'breed':          row['breed'],
            'placement_date': to_dt(row['placement_date']),
            'initial_count':  row['initial_count'],
            'house_number':   row['house_number'],
            'status':         row['status'],
            'notes':          row['notes'],
            'created_at':     to_dt(row['created_at']),
        }
        result = mdb.flocks.insert_one(doc)
        id_map[row['id']] = str(result.inserted_id)
    log.info('  → %d flocks inserted.', len(id_map))
    return id_map


def migrate_poultry_records(cur, mdb, flock_map, user_map):
    cur.execute("SELECT * FROM poultry_records")
    rows = cur.fetchall()
    log.info('Migrating %d poultry records …', len(rows))
    mdb.poultry_records.drop()
    if not rows:
        return
    docs = []
    for row in rows:
        docs.append({
            'flock_id':         flock_map.get(row['flock_id']),
            'recorded_by_id':   user_map.get(row['recorded_by_id']),
            'record_date':      to_dt(row['record_date']),
            'feed_quantity_kg': float(row['feed_quantity_kg']) if row['feed_quantity_kg'] is not None else None,
            'feed_type':        row['feed_type'],
            'water_consumed_l': float(row['water_consumed_l']) if row['water_consumed_l'] is not None else None,
            'eggs_collected':   row['eggs_collected'] or 0,
            'avg_weight_g':     float(row['avg_weight_g']) if row['avg_weight_g'] is not None else None,
            'mortality_count':  row['mortality_count'] or 0,
            'mortality_cause':  row['mortality_cause'],
            'ambient_temp_c':   float(row['ambient_temp_c']) if row['ambient_temp_c'] is not None else None,
            'humidity_pct':     float(row['humidity_pct']) if row['humidity_pct'] is not None else None,
            'notes':            row['notes'],
            'created_at':       to_dt(row['created_at']),
        })
    mdb.poultry_records.insert_many(docs)
    log.info('  → %d poultry records inserted.', len(docs))


def migrate_rabbit_batches(cur, mdb):
    cur.execute("SELECT * FROM rabbit_batches")
    rows = cur.fetchall()
    log.info('Migrating %d rabbit batches …', len(rows))
    mdb.rabbit_batches.drop()
    id_map = {}
    for row in rows:
        doc = {
            'name':             row['name'],
            'breed':            row['breed'],
            'acquisition_date': to_dt(row['acquisition_date']),
            'initial_count':    row['initial_count'],
            'female_count':     row['female_count'] or 0,
            'male_count':       row['male_count'] or 0,
            'status':           row['status'],
            'notes':            row['notes'],
            'created_at':       to_dt(row['created_at']),
        }
        result = mdb.rabbit_batches.insert_one(doc)
        id_map[row['id']] = str(result.inserted_id)
    log.info('  → %d rabbit batches inserted.', len(id_map))
    return id_map


def migrate_cuniculture_records(cur, mdb, batch_map, user_map):
    cur.execute("SELECT * FROM cuniculture_records")
    rows = cur.fetchall()
    log.info('Migrating %d cuniculture records …', len(rows))
    mdb.cuniculture_records.drop()
    if not rows:
        return
    docs = []
    for row in rows:
        docs.append({
            'batch_id':         batch_map.get(row['batch_id']),
            'recorded_by_id':   user_map.get(row['recorded_by_id']),
            'record_date':      to_dt(row['record_date']),
            'feed_quantity_kg': float(row['feed_quantity_kg']) if row['feed_quantity_kg'] is not None else None,
            'feed_type':        row['feed_type'],
            'litters_born':     row['litters_born'] or 0,
            'kits_born':        row['kits_born'] or 0,
            'kits_survived':    row['kits_survived'] or 0,
            'avg_weight_g':     float(row['avg_weight_g']) if row['avg_weight_g'] is not None else None,
            'mortality_count':  row['mortality_count'] or 0,
            'mortality_cause':  row['mortality_cause'],
            'ambient_temp_c':   float(row['ambient_temp_c']) if row['ambient_temp_c'] is not None else None,
            'notes':            row['notes'],
            'created_at':       to_dt(row['created_at']),
        })
    mdb.cuniculture_records.insert_many(docs)
    log.info('  → %d cuniculture records inserted.', len(docs))


def migrate_products(cur, mdb, user_map):
    cur.execute("SELECT * FROM products")
    rows = cur.fetchall()
    log.info('Migrating %d products …', len(rows))
    mdb.products.drop()
    id_map = {}
    for row in rows:
        doc = {
            'name':           row['name'],
            'description':    row['description'],
            'category':       row['category'],
            'price_xaf':      float(row['price_xaf']),
            'unit':           row['unit'],
            'stock_quantity': float(row['stock_quantity']) if row['stock_quantity'] is not None else 0.0,
            'is_available':   bool(row['is_available']),
            'image_filename': row['image_filename'],
            'created_at':     to_dt(row['created_at']),
            'created_by_id':  user_map.get(row['created_by_id']),
        }
        result = mdb.products.insert_one(doc)
        id_map[row['id']] = str(result.inserted_id)
    log.info('  → %d products inserted.', len(id_map))
    return id_map


def migrate_orders(cur, mdb, user_map, product_map):
    cur.execute("SELECT * FROM orders")
    orders = cur.fetchall()
    log.info('Migrating %d orders …', len(orders))
    mdb.orders.drop()

    cur.execute("SELECT * FROM order_items")
    items_by_order = {}
    for item in cur.fetchall():
        items_by_order.setdefault(item['order_id'], []).append(item)

    cur.execute("SELECT * FROM payments")
    payments_by_order = {}
    for pay in cur.fetchall():
        payments_by_order[pay['order_id']] = pay

    id_map = {}
    for order in orders:
        items_docs = []
        for it in items_by_order.get(order['id'], []):
            items_docs.append({
                'product_id':     product_map.get(it['product_id']),
                'product_name':   it['product_name'],
                'product_unit':   it['product_unit'],
                'unit_price_xaf': float(it['unit_price_xaf']),
                'quantity':       float(it['quantity']),
                'subtotal_xaf':   float(it['subtotal_xaf']),
            })

        pay_doc = None
        pay = payments_by_order.get(order['id'])
        if pay:
            pay_doc = {
                'method':            pay['method'],
                'phone_number':      pay['phone_number'],
                'amount_xaf':        float(pay['amount_xaf']),
                'status':            pay['status'],
                'gateway_reference': pay['gateway_reference'],
                'gateway_response':  pay['gateway_response'],
                'initiated_at':      to_dt(pay['initiated_at']),
                'completed_at':      to_dt(pay['completed_at']),
            }

        doc = {
            'order_number':     order['order_number'],
            'customer_id':      user_map.get(order['customer_id']),
            'customer_name':    order['customer_name'],
            'customer_phone':   order['customer_phone'],
            'customer_address': order['customer_address'],
            'status':           order['status'],
            'payment_method':   order['payment_method'],
            'total_xaf':        float(order['total_xaf']),
            'notes':            order['notes'],
            'created_at':       to_dt(order['created_at']),
            'items':            items_docs,
            'payment':          pay_doc,
        }
        result = mdb.orders.insert_one(doc)
        id_map[order['id']] = str(result.inserted_id)

    log.info('  → %d orders inserted (with embedded items + payments).', len(id_map))
    return id_map


def migrate_carousel_slides(cur, mdb, user_map):
    cur.execute("SELECT * FROM carousel_slides")
    rows = cur.fetchall()
    log.info('Migrating %d carousel slides …', len(rows))
    mdb.carousel_slides.drop()
    if not rows:
        return
    docs = [
        {
            'title':          row['title'],
            'subtitle':       row['subtitle'],
            'image_filename': row['image_filename'],
            'cta_text':       row['cta_text'],
            'cta_url':        row['cta_url'] or '#products',
            'is_active':      bool(row['is_active']),
            'sort_order':     row['sort_order'] or 0,
            'created_at':     to_dt(row['created_at']),
            'created_by_id':  user_map.get(row['created_by_id']),
        }
        for row in rows
    ]
    mdb.carousel_slides.insert_many(docs)
    log.info('  → %d carousel slides inserted.', len(docs))


def migrate_finance_entries(cur, mdb, user_map):
    cur.execute("SELECT * FROM finance_entries")
    rows = cur.fetchall()
    log.info('Migrating %d finance entries …', len(rows))
    mdb.finance_entries.drop()
    if not rows:
        return
    docs = [
        {
            'entry_type':       row['entry_type'],
            'category':         row['category'],
            'description':      row['description'],
            'amount_xaf':       float(row['amount_xaf']),
            'entry_date':       to_dt(row['entry_date']),
            'production_scope': row['production_scope'],
            'payment_method':   row['payment_method'],
            'reference_number': row['reference_number'],
            'recorded_by_id':   user_map.get(row['recorded_by_id']),
            'notes':            row['notes'],
            'created_at':       to_dt(row['created_at']),
        }
        for row in rows
    ]
    mdb.finance_entries.insert_many(docs)
    log.info('  → %d finance entries inserted.', len(docs))


def migrate_health_events(cur, mdb, user_map):
    cur.execute("SELECT * FROM health_events")
    rows = cur.fetchall()
    log.info('Migrating %d health events …', len(rows))
    mdb.health_events.drop()
    if not rows:
        return
    docs = [
        {
            'production_unit': row['production_unit'],
            'unit_ref_id':     row['unit_ref_id'],
            'unit_name':       row['unit_name'],
            'event_type':      row['event_type'],
            'event_date':      to_dt(row['event_date']),
            'product_used':    row['product_used'],
            'dose':            row['dose'],
            'administered_by': row['administered_by'],
            'next_due_date':   to_dt(row['next_due_date']),
            'cost_xaf':        float(row['cost_xaf']) if row['cost_xaf'] is not None else None,
            'notes':           row['notes'],
            'recorded_by_id':  user_map.get(row['recorded_by_id']),
            'created_at':      to_dt(row['created_at']),
        }
        for row in rows
    ]
    mdb.health_events.insert_many(docs)
    log.info('  → %d health events inserted.', len(docs))


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    try:
        mysql_conn = connect_mysql()
        mdb        = connect_mongo()
    except Exception as exc:
        log.critical('Connection failed: %s', exc)
        sys.exit(1)

    try:
        cur = mysql_conn.cursor()

        log.info(DIVIDER := '=' * 60)
        log.info('OmniFarm Hub — MariaDB → MongoDB Migration')
        log.info(DIVIDER)

        user_map    = migrate_users(cur, mdb)
        pond_map    = migrate_ponds(cur, mdb)
        migrate_aquaculture_records(cur, mdb, pond_map, user_map)
        flock_map   = migrate_flocks(cur, mdb)
        migrate_poultry_records(cur, mdb, flock_map, user_map)
        batch_map   = migrate_rabbit_batches(cur, mdb)
        migrate_cuniculture_records(cur, mdb, batch_map, user_map)
        product_map = migrate_products(cur, mdb, user_map)
        migrate_orders(cur, mdb, user_map, product_map)
        migrate_carousel_slides(cur, mdb, user_map)
        migrate_finance_entries(cur, mdb, user_map)
        migrate_health_events(cur, mdb, user_map)

        log.info(DIVIDER)
        log.info('Migration complete!  All data is now in MongoDB.')
        log.info('Next steps:')
        log.info('  1. Verify data in MongoDB Compass or mongosh')
        log.info('  2. Start the app:  python run.py')
        log.info('  3. Log in and verify everything works')

    except Exception as exc:
        log.critical('Migration failed: %s', exc, exc_info=True)
        sys.exit(1)
    finally:
        mysql_conn.close()


if __name__ == '__main__':
    run()
