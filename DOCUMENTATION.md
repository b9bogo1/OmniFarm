# OmniFarm Hub — Developer Documentation

> **Version:** 1.0 · **Stack:** Flask 3 · MongoDB · APScheduler · JWT · Tailwind CSS  
> **Language:** Python 3.11+ · **Database:** MongoDB replica set (rs0)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Technology Stack](#2-technology-stack)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Directory Structure](#4-directory-structure)
5. [Configuration & Environment Variables](#5-configuration--environment-variables)
6. [Database Design](#6-database-design)
7. [Authentication & Authorization](#7-authentication--authorization)
8. [Blueprint Reference](#8-blueprint-reference)
   - [Main](#81-main-blueprint)
   - [Auth](#82-auth-blueprint)
   - [Aquaculture](#83-aquaculture-blueprint)
   - [Poultry](#84-poultry-blueprint)
   - [Cuniculture](#85-cuniculture-blueprint)
   - [Finance](#86-finance-blueprint)
   - [Health](#87-health-blueprint)
   - [Reports](#88-reports-blueprint)
   - [IoT](#89-iot-blueprint)
   - [Marketplace](#810-marketplace-blueprint)
   - [API v1](#811-api-v1-blueprint)
9. [Marketplace & Order Flow](#9-marketplace--order-flow)
10. [Payment Gateway Integration](#10-payment-gateway-integration)
11. [IoT & Background Scheduler](#11-iot--background-scheduler)
12. [Email System](#12-email-system)
13. [REST API Reference](#13-rest-api-reference)
14. [Frontend Design System](#14-frontend-design-system)
15. [Security Model](#15-security-model)
16. [Development Setup](#16-development-setup)
17. [Testing](#17-testing)
18. [Deployment](#18-deployment)

---

## 1. Project Overview

OmniFarm Hub is a **multi-module agricultural management platform** for a farm operation in N'Djamena, Chad. It combines:

- **Farm management** — real-time tracking for three livestock production lines (aquaculture, poultry, rabbit farming)
- **E-commerce marketplace** — direct-to-consumer product sales with Mobile Money payment support
- **Financial ledger** — revenue/expense tracking and reporting per production unit
- **Animal health calendar** — vaccination, treatment, and inspection scheduling
- **IoT telemetry** — background sensor polling via ModBus TCP / EtherNet/IP with live SSE dashboard
- **REST API** — JWT-authenticated API for mobile clients and third-party integrations

The application is **bilingual** (French/English), supports **dark/light mode**, and is designed to work from small phones to desktop workstations.

---

## 2. Technology Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                    │
│  Tailwind CSS (Play CDN)  ·  Ubuntu Font  ·  Chart.js  ·  SSE      │
│  Premium Design System (premium.css)  ·  Jinja2 Templates          │
├─────────────────────────────────────────────────────────────────────┤
│                         BACKEND                                     │
│  Flask 3.0           — Web framework                                │
│  Flask-Login         — Session authentication                       │
│  Flask-JWT-Extended  — Stateless API tokens (HS256)                 │
│  Flask-WTF           — Forms + CSRF protection                      │
│  Flask-Babel         — i18n/l10n (fr / en, UTC+1)                  │
│  Flask-Limiter       — Rate limiting (Redis or in-memory)           │
│  Flask-Mail          — Transactional email (SMTP TLS/SSL)           │
│  Flask-Assets        — CSS/JS bundling (production)                 │
│  APScheduler         — Background IoT polling tasks                 │
│  PyModbus            — ModBus TCP sensor communication              │
├─────────────────────────────────────────────────────────────────────┤
│                         DATA LAYER                                  │
│  MongoDB replica set (rs0, 3 nodes)                                 │
│  Flask-PyMongo       — MongoDB driver wrapper                       │
│  GridFS              — Binary image storage                         │
├─────────────────────────────────────────────────────────────────────┤
│                         INFRASTRUCTURE                              │
│  Redis               — Rate-limit counters                          │
│  Sentry              — Error tracking (production)                  │
│  python-dotenv       — Environment configuration                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. High-Level Architecture

```
                         ┌──────────────────────────┐
                         │       Browser / App       │
                         └────────────┬─────────────┘
                                      │ HTTPS
                         ┌────────────▼─────────────┐
                         │      Flask Application    │
                         │    (WSGI / Gunicorn)      │
                         └──┬─────────┬─────────┬───┘
                            │         │         │
              ┌─────────────▼──┐  ┌───▼──────┐  ┌▼────────────────┐
              │  Web Blueprints│  │ API v1   │  │ Background      │
              │  (11 modules)  │  │ (JWT)    │  │ Scheduler       │
              └────────┬───────┘  └───┬──────┘  │ (APScheduler)  │
                       │              │          └────────┬────────┘
                       │              │                   │ ModBus TCP
                       │              │          ┌────────▼────────┐
              ┌─────────▼──────────────▼──┐      │   IoT Sensors   │
              │       MongoDB rs0          │      │  (aqua/climate) │
              │  ┌────────┐ ┌────────┐    │      └─────────────────┘
              │  │ mongo-1│ │ mongo-2│    │
              │  │PRIMARY │ │SECONDARY    │
              │  └────────┘ └────────┘    │
              │       ┌────────┐          │
              │       │ mongo-3│          │
              │       │SECONDARY         │
              │       └────────┘          │
              │  GridFS: Images           │
              └───────────────────────────┘
                            │
              ┌─────────────▼─────────────┐
              │         Redis              │
              │   (Rate-limit counters)    │
              └────────────────────────────┘
```

### Request Lifecycle

```
HTTP Request
    │
    ▼
Flask app.before_request()
    │  ├─ Redirect to /setup  (no users exist)
    │  ├─ Inject: now, cart_count, pending_orders
    │  └─ Inject: user_theme, get_locale()
    │
    ▼
Flask-Limiter  (rate check)
    │
    ▼
Blueprint route handler
    │  ├─ @login_required / @admin_required
    │  ├─ WTForms validation (CSRF + fields)
    │  ├─ MongoDB query via get_col()
    │  └─ Model hydration / persistence
    │
    ▼
Jinja2 template render  ──or──  JSON response (API)
    │
    ▼
HTTP Response
```

---

## 4. Directory Structure

```
OmniFarm/
├── app/
│   ├── __init__.py              # App factory (create_app)
│   ├── extensions.py            # Shared extension instances
│   │
│   ├── models/                  # MongoDB document models
│   │   ├── __init__.py
│   │   ├── user.py              # User, UserRole
│   │   ├── aquaculture.py       # Pond, AquacultureRecord
│   │   ├── poultry.py           # Flock, PoultryRecord
│   │   ├── cuniculture.py       # RabbitBatch, CunicultureRecord
│   │   ├── finance.py           # FinanceEntry
│   │   ├── health.py            # HealthEvent
│   │   └── marketplace.py       # Product, Order, OrderItem,
│   │                            #   Payment, CarouselSlide
│   │
│   ├── auth/                    # Authentication blueprint
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── forms.py
│   │
│   ├── main/                    # Dashboard & admin monitor
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── templates/main/
│   │       ├── dashboard.html
│   │       └── admin_monitor.html
│   │
│   ├── aquaculture/             # Fish pond management
│   ├── poultry/                 # Chicken flock management
│   ├── cuniculture/             # Rabbit batch management
│   ├── finance/                 # Financial ledger
│   ├── health/                  # Animal health events
│   ├── reports/                 # CSV exports & summaries
│   │
│   ├── iot/                     # IoT telemetry module
│   │   ├── __init__.py
│   │   ├── routes.py            # /iot/ dashboard + SSE stream
│   │   ├── scheduler.py         # APScheduler setup
│   │   └── readers.py           # ModBus polling functions
│   │
│   ├── marketplace/             # E-commerce module
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── forms.py
│   │   └── txn.py               # Atomic stock+order transaction
│   │
│   ├── api/                     # REST API v1 (JWT)
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── openapi_spec.py      # OpenAPI 3.0.3 schema
│   │
│   ├── email.py                 # Transactional email helpers
│   │
│   ├── static/
│   │   ├── css/
│   │   │   ├── premium.css      # Design system (900+ lines)
│   │   │   └── fonts.css        # Ubuntu font-face declarations
│   │   └── js/
│   │       ├── tailwind.js      # Tailwind Play CDN
│   │       └── chart.umd.min.js # Chart.js
│   │
│   └── templates/
│       ├── base.html            # Authenticated layout (sidebar)
│       ├── base_shop.html       # Public shop layout (topnav)
│       ├── macros.html          # Reusable Jinja2 macros
│       ├── errors/              # 403, 404, 413, 429, 500
│       └── email/               # Email HTML templates
│
├── tests/
│   ├── conftest.py              # Fixtures (mongomock, test client)
│   ├── test_auth.py
│   ├── test_api.py
│   └── test_marketplace.py
│
├── pytest.ini
├── requirements.txt
├── .env                         # (gitignored) Environment variables
└── DOCUMENTATION.md             # This file
```

---

## 5. Configuration & Environment Variables

All configuration is loaded from a `.env` file via `python-dotenv`. Copy `.env.example` and fill in your values.

### Complete `.env` Reference

```ini
# ── Core ────────────────────────────────────────────────────────────
SECRET_KEY=change-me-to-a-long-random-string
FLASK_ENV=development          # development | production
BASE_URL=http://localhost:5000  # Used in email links

# ── MongoDB ─────────────────────────────────────────────────────────
MONGO_URI=mongodb://admin:password@mongo-1:27017,mongo-2:27017,mongo-3:27017/omnifarm_db?replicaSet=rs0&authSource=admin&readPreference=primaryPreferred&w=majority&journal=true

# Single-node dev alternative:
# MONGO_URI=mongodb://localhost:27017/omnifarm_db

# ── Redis (rate limiting) ────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
# Leave empty → in-memory fallback (dev only)

# ── JWT ─────────────────────────────────────────────────────────────
JWT_SECRET_KEY=another-long-random-string
JWT_ACCESS_TOKEN_EXPIRES=3600       # seconds (1 hour)
JWT_REFRESH_TOKEN_EXPIRES=2592000   # seconds (30 days)

# ── Email (Flask-Mail) ───────────────────────────────────────────────
MAIL_SERVER=smtp.example.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=noreply@omnifarm.com
MAIL_PASSWORD=smtp-password
MAIL_DEFAULT_SENDER=OmniFarm <noreply@omnifarm.com>

# ── Payment Gateways ────────────────────────────────────────────────
ORANGE_MONEY_CLIENT_ID=
ORANGE_MONEY_CLIENT_SECRET=
ORANGE_MONEY_MERCHANT_KEY=

MTN_MOMO_SUBSCRIPTION_KEY=
MTN_MOMO_API_USER=
MTN_MOMO_API_KEY=
MTN_MOMO_TARGET_ENV=mtncameroon

# ── IoT ─────────────────────────────────────────────────────────────
MODBUS_AQUA_HOST=192.168.1.100    # Aquaculture ModBus device IP
MODBUS_CLIMATE_HOST=192.168.1.101 # Climate sensor device IP
IOT_POLL_INTERVAL_MINUTES=5

# ── Sentry (production error tracking) ──────────────────────────────
SENTRY_DSN=https://xxx@sentry.io/project_id

# ── Feature flags ───────────────────────────────────────────────────
USE_ASSETS_BUNDLE=false   # true → Flask-Assets bundled CSS/JS
WTF_CSRF_TIME_LIMIT=3600  # CSRF token expiry seconds
```

### Configuration Priority

```
Environment variable
    └─▶ .env file
            └─▶ config.py defaults
```

---

## 6. Database Design

### Collections Overview

```
omnifarm_db
├── users
├── ponds                   ◄── Aquaculture
├── aquaculture_records     ◄──
├── flocks                  ◄── Poultry
├── poultry_records         ◄──
├── rabbit_batches          ◄── Cuniculture
├── cuniculture_records     ◄──
├── finance_entries         ◄── Finance
├── health_events           ◄── Health
├── products                ◄── Marketplace
├── orders                  ◄──
├── carousel_slides         ◄──
└── fs.files / fs.chunks    ◄── GridFS (images)
```

### Entity Relationship Diagram

```
┌──────────────┐        ┌──────────────────────┐
│    users     │        │       orders          │
├──────────────┤        ├──────────────────────┤
│ _id (ObjId)  │◄───────│ customer_id (string) │
│ username     │        │ order_number          │
│ email        │        │ customer_name         │
│ password_hash│        │ customer_phone        │
│ role         │        │ customer_address      │
│ is_active    │        │ status (enum)         │
│ language     │        │ total_xaf             │
│ theme        │        │ payment_method        │
│ created_at   │        │ notes                 │
│ last_login   │        │ created_at            │
└──────────────┘        │ ┌─────────────────┐  │
                        │ │   items[]        │  │
                        │ ├─────────────────┤  │
                        │ │ product_id       │  │
                        │ │ product_name     │  │
                        │ │ unit_price_xaf   │  │
                        │ │ quantity         │  │
                        │ │ subtotal_xaf     │  │
                        │ └─────────────────┘  │
                        │ ┌─────────────────┐  │
                        │ │   payment{}      │  │
                        │ ├─────────────────┤  │
                        │ │ method           │  │
                        │ │ phone_number     │  │
                        │ │ amount_xaf       │  │
                        │ │ status           │  │
                        │ │ gateway_ref      │  │
                        │ └─────────────────┘  │
                        └──────────────────────┘

┌──────────────┐        ┌──────────────────────┐
│   products   │        │   carousel_slides     │
├──────────────┤        ├──────────────────────┤
│ _id (ObjId)  │        │ _id (ObjId)          │
│ name         │        │ title                 │
│ description  │        │ subtitle              │
│ category     │        │ image_id → GridFS     │
│ price_xaf    │        │ cta_text              │
│ unit         │        │ cta_url               │
│ stock_qty    │        │ is_active             │
│ is_available │        │ sort_order            │
│ image_id     │──► GridFS
│ created_at   │
└──────────────┘

┌──────────────┐        ┌──────────────────────┐
│    ponds     │        │  aquaculture_records  │
├──────────────┤        ├──────────────────────┤
│ _id (ObjId)  │◄───────│ pond_id (string)      │
│ name         │        │ record_date           │
│ species      │        │ current_count         │
│ capacity_m3  │        │ avg_weight_g          │
│ status (enum)│        │ feed_quantity_kg      │
│ install_date │        │ feed_type             │
│ notes        │        │ mortality_count       │
│ created_at   │        │ water_temp_c  ◄── IoT │
└──────────────┘        │ ph            ◄── IoT │
                        │ dissolved_o2  ◄── IoT │
                        │ turbidity_ntu ◄── IoT │
                        │ created_at            │
                        └──────────────────────┘

┌──────────────┐        ┌──────────────────────┐
│   flocks     │        │   poultry_records     │
├──────────────┤        ├──────────────────────┤
│ _id (ObjId)  │◄───────│ flock_id (string)     │
│ name         │        │ record_date           │
│ species      │        │ feed_quantity_kg      │
│ breed        │        │ water_consumed_l      │
│ placement_dt │        │ eggs_collected        │
│ initial_count│        │ avg_weight_g          │
│ house_number │        │ mortality_count       │
│ status (enum)│        │ ambient_temp_c ◄─ IoT │
│ created_at   │        │ humidity_pct   ◄─ IoT │
└──────────────┘        └──────────────────────┘

┌──────────────┐        ┌──────────────────────┐
│rabbit_batches│        │ cuniculture_records   │
├──────────────┤        ├──────────────────────┤
│ _id (ObjId)  │◄───────│ batch_id (string)     │
│ name         │        │ record_date           │
│ breed        │        │ litters_born          │
│ acquis_date  │        │ kits_born             │
│ initial_count│        │ kits_survived         │
│ female_count │        │ avg_weight_g          │
│ male_count   │        │ mortality_count       │
│ status (enum)│        │ ambient_temp_c ◄─ IoT │
│ created_at   │        │ created_at            │
└──────────────┘        └──────────────────────┘

┌──────────────────────┐   ┌──────────────────────┐
│   finance_entries    │   │    health_events      │
├──────────────────────┤   ├──────────────────────┤
│ entry_type (enum)    │   │ production_unit (enum)│
│ category (enum)      │   │ unit_ref_id (string)  │
│ description          │   │ unit_name             │
│ amount_xaf           │   │ event_type (enum)     │
│ entry_date           │   │ event_date            │
│ production_scope     │   │ product_used          │
│ payment_method       │   │ dose                  │
│ reference_number     │   │ administered_by       │
│ recorded_by_id       │   │ next_due_date         │
│ created_at           │   │ cost_xaf              │
└──────────────────────┘   └──────────────────────┘
```

### MongoDB Data Access Pattern

Every model follows the same convention:

```python
# ── Retrieve ──────────────────────────────────────────────────────
pond = Pond.get_by_id("64abc...")          # returns None if not found
ponds = Pond.find_all(filter={"status": "active"})
page = Pond.paginate(page=1, per_page=20)  # returns Pagination object

# ── Persist ───────────────────────────────────────────────────────
pond = Pond(name="Bassin A", species="Tilapia", capacity_m3=12.5)
pond.save()           # insert_one → sets pond._id

pond.status = "maintenance"
pond.save()           # replace_one (upsert=True)

# ── Delete ────────────────────────────────────────────────────────
pond.delete()         # delete_one, then cascade records

# ── Raw collection access ──────────────────────────────────────────
col = get_col("ponds")            # returns mongo.db["ponds"]
result = col.aggregate([...])     # native PyMongo aggregation
```

### Enum Values Reference

| Model | Field | Values |
|-------|-------|--------|
| User | role | `admin` `technician` `client` |
| Pond | status | `active` `inactive` `maintenance` `harvested` |
| Flock | status | `active` `sold` `culled` |
| RabbitBatch | status | `active` `sold` `deceased` |
| Order | status | `pending` `payment_pending` `paid` `processing` `shipped` `delivered` `cancelled` |
| Order | payment_method | `orange_money` `mtn_mobile_money` `cash_on_delivery` |
| Payment | status | `pending` `success` `failed` `refunded` |
| Product | category | `fish` `poultry` `rabbit` `eggs` `other` |
| FinanceEntry | entry_type | `EXPENSE` `REVENUE` |
| FinanceEntry | production_scope | `AQUACULTURE` `POULTRY` `CUNICULTURE` `GENERAL` |
| FinanceEntry | category | `FEED` `MEDICATION` `EQUIPMENT` `LABOR` `UTILITIES` `TRANSPORT` `MAINTENANCE` `PRODUCT_SALE` `DIRECT_SALE` `SUBSIDY` `OTHER` |
| HealthEvent | event_type | `VACCINATION` `TREATMENT` `DEWORMING` `INSPECTION` `SURGERY` |
| HealthEvent | production_unit | `AQUACULTURE` `POULTRY` `CUNICULTURE` |

---

## 7. Authentication & Authorization

### Role Hierarchy

```
┌─────────────────────────────────────────────────────┐
│  ADMIN                                              │
│  • All routes                                       │
│  • User management (create / edit / delete)         │
│  • Admin marketplace (products, orders, carousel)   │
│  • Admin monitor (logs, DB stats)                   │
│  • All production + finance + health modules        │
├─────────────────────────────────────────────────────┤
│  TECHNICIAN                                         │
│  • All production modules (aqua / poultry / cunicu) │
│  • Finance, Health, Reports, IoT dashboard          │
│  • Marketplace (browse + order) — not admin actions │
├─────────────────────────────────────────────────────┤
│  CLIENT                                             │
│  • Marketplace (browse + cart + checkout)           │
│  • My orders                                        │
│  • Dashboard (simplified view)                      │
└─────────────────────────────────────────────────────┘
```

### Authentication Flow

```
                        ┌──────────────────────┐
                        │  /setup (first-run)   │
                        │  Creates admin user   │
                        └─────────┬────────────┘
                                  │ (redirects after)
                        ┌─────────▼────────────┐
                        │  POST /auth/login     │
                        │  username + password  │
                        └─────────┬────────────┘
                                  │
              ┌───────────────────▼──────────────────┐
              │         Flask-Login validates         │
              │  bcrypt.check_password_hash()         │
              └───────────┬──────────────────────────┘
                          │
          ┌───────────────┴──────────────────┐
          │ success                          │ failure
          ▼                                  ▼
  login_user(user)                  flash("Identifiants invalides")
  update last_login                 redirect to /login
  redirect to next or /
```

### Route Decorators

```python
from flask_login import login_required

# Require any authenticated user
@login_required

# Require admin role
@admin_required          # custom decorator in auth/routes.py

# Require admin OR technician role
@technician_required     # custom decorator in auth/routes.py
```

Implementation:

```python
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated
```

### JWT Authentication (API)

```
POST /api/v1/auth/token
Body: { "username": "...", "password": "..." }

Response:
{
  "access_token":  "eyJ...",   # expires in 1 hour
  "refresh_token": "eyJ..."    # expires in 30 days
}

Subsequent requests:
Authorization: Bearer eyJ...

Token refresh:
POST /api/v1/auth/refresh
Authorization: Bearer <refresh_token>
→ { "access_token": "eyJ..." }
```

---

## 8. Blueprint Reference

### Application Factory

```python
# app/__init__.py
def create_app(config=None):
    app = Flask(__name__)
    # 1. Load config from environment
    # 2. Initialize extensions (mongo, login, babel, limiter…)
    # 3. Register blueprints
    # 4. Register error handlers
    # 5. Set up before_request (first-run guard, context injection)
    # 6. Start IoT scheduler (non-testing, non-reloader-child mode)
    return app
```

```python
# app/extensions.py — shared singletons
mongo   = PyMongo()
login   = LoginManager()
bcrypt  = Bcrypt()
babel   = Babel()
limiter = Limiter(...)
mail    = Mail()
jwt     = JWTManager()
assets  = Environment()
```

---

### 8.1 Main Blueprint

**Prefix:** `/`  **Template folder:** `app/main/templates/`

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/` | — | Redirect to dashboard or marketplace |
| GET | `/dashboard` | `login_required` | Main dashboard with charts |
| GET | `/admin/monitor` | `admin_required` | Logs, MongoDB stats, scheduler info |

**Dashboard context variables:**

```
pond_count         — active ponds
flock_count        — active flocks
batch_count        — active rabbit batches
order_count        — total orders
pending_orders     — orders with status=pending
recent_orders      — last 10 orders (admin/tech only)
total_revenue_all  — sum of all REVENUE entries
total_expense_all  — sum of all EXPENSE entries
net_balance_all    — revenue − expense
chart_labels       — ["Jan", "Feb", ...] last 6 months
chart_revenues     — monthly revenue array
chart_expenses     — monthly expense array
order_status_labels/data — donut chart data
species_labels/data      — production donut data
activity_feed      — recent 8 finance/order/health events
user_count         — total users (admin only)
iot_running        — scheduler running boolean
iot_jobs           — count of scheduled jobs
```

---

### 8.2 Auth Blueprint

**Prefix:** `/auth`

| Method | URL | Auth | Rate Limit | Description |
|--------|-----|------|-----------|-------------|
| GET/POST | `/login` | — | 10/min | Login form |
| GET/POST | `/register` | — | 5/min | Self-registration (CLIENT role) |
| GET | `/logout` | `login_required` | — | Logout + redirect |
| GET/POST | `/setup` | — | — | First-run admin setup |
| GET | `/admin/users` | `admin_required` | — | List all users |
| GET/POST | `/admin/users/new` | `admin_required` | — | Create user |
| GET/POST | `/admin/users/<id>/edit` | `admin_required` | — | Edit user |
| POST | `/admin/users/<id>/delete` | `admin_required` | — | Delete user |
| GET | `/set-language/<code>` | — | — | Switch locale (fr/en) |
| GET | `/set-theme/<theme>` | — | — | Switch theme (light/dark) |

**Forms:**

```python
LoginForm       — username, password, remember_me
RegisterForm    — username, email, password, confirm
SetupForm       — username, email, password, confirm
UserAdminForm   — username, email, password (optional), role, is_active
```

---

### 8.3 Aquaculture Blueprint

**Prefix:** `/aquaculture`  **Auth:** `technician_required` on all routes

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/` | List ponds + aggregate stats |
| GET/POST | `/pond/new` | Create pond |
| GET | `/pond/<id>` | Pond detail + records list |
| GET/POST | `/pond/<id>/edit` | Edit pond |
| POST | `/pond/<id>/delete` | Delete pond (cascades records) |
| GET/POST | `/pond/<id>/record/new` | Add aquaculture record |
| GET/POST | `/pond/<id>/record/<rid>/edit` | Edit record |
| POST | `/pond/<id>/record/<rid>/delete` | Delete record |

**Pond list aggregation** (runs per pond on load):

```python
{
  record_count:    count of aquaculture_records for this pond
  total_mortality: sum of mortality_count
  latest_record:   most recent record by record_date
}
```

---

### 8.4 Poultry Blueprint

**Prefix:** `/poultry`  **Auth:** `technician_required`

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/` | List flocks + aggregate stats |
| GET/POST | `/flock/new` | Create flock |
| GET | `/flock/<id>` | Flock detail + records |
| GET/POST | `/flock/<id>/edit` | Edit flock |
| POST | `/flock/<id>/delete` | Delete flock |
| GET/POST | `/flock/<id>/record/new` | Add poultry record |
| GET/POST | `/flock/<id>/record/<rid>/edit` | Edit record |
| POST | `/flock/<id>/record/<rid>/delete` | Delete record |

**Flock aggregations:** record_count, total_mortality, total_eggs_collected, latest_record

---

### 8.5 Cuniculture Blueprint

**Prefix:** `/cuniculture`  **Auth:** `technician_required`

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/` | List rabbit batches + stats |
| GET/POST | `/batch/new` | Create batch |
| GET | `/batch/<id>` | Batch detail + records |
| GET/POST | `/batch/<id>/edit` | Edit batch |
| POST | `/batch/<id>/delete` | Delete batch |
| GET/POST | `/batch/<id>/record/new` | Add cuniculture record |
| GET/POST | `/batch/<id>/record/<rid>/edit` | Edit record |
| POST | `/batch/<id>/record/<rid>/delete` | Delete record |

**Batch aggregations:** record_count, total_mortality, total_kits_born, total_kits_survived

---

### 8.6 Finance Blueprint

**Prefix:** `/finance`  **Auth:** `technician_required`

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/` | List entries (filterable), KPI strip, 6-month chart |
| GET/POST | `/entry/new` | Create finance entry |
| GET/POST | `/entry/<id>/edit` | Edit entry |
| POST | `/entry/<id>/delete` | Delete entry |
| GET | `/summary` | Aggregated summary by scope + category |

**Query filters** (URL params): `type` (EXPENSE/REVENUE), `scope`, `month` (YYYY-MM)

**Finance aggregations** (MongoDB pipeline):

```python
# monthly_totals — for 6-month chart
pipeline = [
  {"$match": {"entry_date": {"$gte": six_months_ago}}},
  {"$group": {
      "_id": {"year": {"$year": "$entry_date"},
              "month": {"$month": "$entry_date"},
              "type": "$entry_type"},
      "total": {"$sum": "$amount_xaf"}
  }},
  {"$sort": {"_id.year": 1, "_id.month": 1}}
]
```

---

### 8.7 Health Blueprint

**Prefix:** `/health`  **Auth:** `technician_required`

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/` | List health events, upcoming reminders |
| GET/POST | `/event/new` | Create health event |
| GET/POST | `/event/<id>/edit` | Edit event |
| POST | `/event/<id>/delete` | Delete event |

**Upcoming events** — events where `next_due_date` ≥ today, sorted ascending, limited to 5.

**Dynamic unit selection**: when `production_unit` changes in the form, the `unit_ref_id` select is populated from the relevant collection (Ponds, Flocks, or RabbitBatches).

---

### 8.8 Reports Blueprint

**Prefix:** `/reports`  **Auth:** `technician_required`

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/` | Summary metrics (all module counts) |
| GET | `/export/aquaculture` | CSV export with date range |
| GET | `/export/poultry` | CSV export |
| GET | `/export/cuniculture` | CSV export |
| GET | `/export/finance` | CSV export |
| GET | `/export/orders` | CSV export (admin_required) |
| GET | `/export/health` | CSV export |

**CSV Response pattern:**

```python
output = io.StringIO()
writer = csv.writer(output, dialect='excel')
writer.writerow(["Date", "Field1", "Field2", ...])
for doc in col.find(query, sort=[("date", -1)]):
    writer.writerow([doc["date"], ...])
response = make_response(output.getvalue())
response.headers["Content-Type"] = "text/csv; charset=utf-8"
response.headers["Content-Disposition"] = f'attachment; filename="{name}.csv"'
```

---

### 8.9 IoT Blueprint

**Prefix:** `/iot`  **Auth:** `technician_required`

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/` | IoT dashboard (scheduler status, latest readings) |
| GET | `/stream` | Server-Sent Events live feed |

**SSE Stream format:**

```
data: {"aqua": [{"pond_id": "...", "temp": 26.4, "ph": 7.2, "o2": 8.1, "turbidity": 12, "date": "04/06/2026"}], "poultry": [...], "cuniculture": [...]}

data: {...}   ← pushed every 8 seconds
```

**Scheduler jobs** (APScheduler):

```python
scheduler.add_job(
    func=poll_aquaculture,
    trigger="interval",
    minutes=IOT_POLL_INTERVAL_MINUTES,   # default 5
    id="poll_aquaculture",
    replace_existing=True,
    args=[app]
)
```

---

### 8.10 Marketplace Blueprint

**Prefix:** `/marketplace`

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/` | — | Product listing + carousel |
| GET | `/product/<id>` | — | Product detail page |
| GET | `/search` | — | AJAX product search (JSON) |
| GET | `/images/<file_id>` | — | Serve GridFS image |
| POST | `/cart/add` | — | Add to session cart (60/min) |
| POST | `/cart/remove/<id>` | — | Remove from cart |
| POST | `/cart/update` | — | Update quantities |
| GET | `/cart` | — | Cart view |
| GET/POST | `/checkout` | — | Checkout form + order creation |
| GET | `/order/<number>` | — | Order confirmation |
| GET | `/my-orders` | `login_required` | Customer orders |
| GET | `/admin/products` | `admin_required` | Product management |
| GET/POST | `/admin/products/new` | `admin_required` | Create product |
| GET/POST | `/admin/products/<id>/edit` | `admin_required` | Edit product |
| POST | `/admin/products/<id>/delete` | `admin_required` | Delete product |
| GET/POST | `/admin/carousel` | `admin_required` | Manage carousel slides |
| GET/POST | `/admin/carousel/new` | `admin_required` | Create slide |
| GET/POST | `/admin/carousel/<id>/edit` | `admin_required` | Edit slide |
| POST | `/admin/carousel/<id>/delete` | `admin_required` | Delete slide |
| GET | `/admin/orders` | `admin_required` | All orders management |
| POST | `/admin/orders/<id>/status` | `admin_required` | Update order status |
| GET | `/admin/analytics` | `admin_required` | Sales analytics |

**Session cart structure:**

```python
session["cart"] = {
    "64abc123...": 2.5,   # product_id → quantity
    "64def456...": 1.0,
}
```

**Cart helper class:**

```python
cart = Cart()
cart.add(product_id, quantity)
cart.remove(product_id)
cart.update(product_id, quantity)   # quantity=0 removes item
cart.get_items()    # → [(Product, quantity), ...]
cart.get_total()    # → float (sum of price * qty)
cart.get_cart_count()  # → int (number of distinct items)
cart.is_empty()     # → bool
cart.clear()        # empties session cart
```

---

### 8.11 API v1 Blueprint

**Prefix:** `/api/v1`

Full reference in [Section 13](#13-rest-api-reference).

---

## 9. Marketplace & Order Flow

### Complete Order Lifecycle

```
                    ┌────────────────────┐
                    │  Browse /marketplace│
                    │  Category filter    │
                    │  Search (AJAX)      │
                    └──────────┬─────────┘
                               │ Add to Cart
                    ┌──────────▼─────────┐
                    │  Session Cart       │
                    │  {product_id: qty}  │
                    │  Update / Remove    │
                    └──────────┬─────────┘
                               │ POST /checkout
                    ┌──────────▼─────────┐
                    │  CheckoutForm       │
                    │  name, phone, addr  │
                    │  payment method     │
                    └──────────┬─────────┘
                               │ form.validate()
                    ┌──────────▼─────────┐
                    │  Stock check        │
                    │  (per item, atomic) │
                    └──────────┬─────────┘
                               │ checkout_transact()
                    ┌──────────▼─────────┐
                    │  MongoDB Transaction│
                    │  • decrement stock  │
                    │  • insert order     │
                    └──────────┬─────────┘
                               │
              ┌────────────────┼─────────────────────┐
              │                │                     │
     Orange Money          MTN MoMo         Cash on Delivery
              │                │                     │
    initiate_orange()  initiate_mtn()        status=PROCESSING
    status=PAYMENT    status=PAYMENT         (no gateway)
    _PENDING           _PENDING
              │                │
    ┌─────────▼────────┬────────▼─────────┐
    │ Payment gateway  │ Push on phone    │
    │ webhook callback │ USSD prompt      │
    └─────────┬────────┴────────┬─────────┘
              │ success                │
    ┌─────────▼────────────────────────▼──┐
    │  order.status = PAID / PROCESSING    │
    │  send_order_confirmation() email     │
    │  clear session cart                  │
    │  redirect → /order/<number>          │
    └──────────────────────────────────────┘
                               │
              ┌────────────────▼───────────────┐
              │  Admin updates status           │
              │  (admin/orders → status form)   │
              │  → send_order_status_update()   │
              └────────────────────────────────┘
```

### Order Number Format

```
OMF-2026-A3B7C2
 │    │    └─── 6 random uppercase alphanumeric chars
 │    └──────── 4-digit year
 └───────────── "OmniFarm" prefix
```

### Transactional Checkout (`txn.py`)

```python
def checkout_transact(order: Order, items: list[tuple]) -> Order:
    """
    Atomically decrement product stock and insert the order.

    On replica set:  uses multi-document session transaction.
    On single-node:  falls back to sequential ops (no rollback).

    Raises InsufficientStockError if any item has qty < requested.
    Returns the saved Order with _id populated.
    """
```

**Transaction flow (replica set):**

```
session.start_transaction()
    for product, qty in items:
        col.update_one(
            {"_id": product._id, "stock_quantity": {"$gte": qty}},
            {"$inc": {"stock_quantity": -qty}}
        )
        if modified_count == 0:
            raise InsufficientStockError(product.name)
    orders_col.insert_one(order._to_doc())
session.commit_transaction()
```

---

## 10. Payment Gateway Integration

### Orange Money (Côte d'Ivoire / Chad)

```python
# Initiation
def initiate_orange_money(order, phone_number):
    token = get_oauth_token(CLIENT_ID, CLIENT_SECRET)
    payload = {
        "merchant_key": MERCHANT_KEY,
        "currency": "XAF",
        "order_id": order.order_number,
        "amount": order.total_xaf,
        "return_url": f"{BASE_URL}/marketplace/order/{order.order_number}",
        "cancel_url": f"{BASE_URL}/marketplace/cart",
        "notif_url": f"{BASE_URL}/api/v1/webhooks/orange",
    }
    response = requests.post(ORANGE_PAYMENT_URL, json=payload, ...)
    return response.json()["payment_url"]
```

### MTN Mobile Money (Cameroon/Chad)

```python
# Uses MTN MoMo Collections API
def initiate_mtn_mobile_money(order, phone_number):
    reference_id = str(uuid.uuid4())
    payload = {
        "amount": str(int(order.total_xaf)),
        "currency": "XAF",
        "externalId": order.order_number,
        "payer": {"partyIdType": "MSISDN", "partyId": phone_number},
        "payerMessage": f"OmniFarm commande {order.order_number}",
        "payeeNote": "Paiement OmniFarm"
    }
    headers = {
        "Authorization": f"Bearer {get_mtn_token()}",
        "X-Reference-Id": reference_id,
        "X-Target-Environment": TARGET_ENV,
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
    }
    requests.post(MTN_REQUEST_URL, json=payload, headers=headers)
    return reference_id   # stored as gateway_reference for status checks
```

### Payment Status Flow

```
order.payment.status:

pending
   │
   ├──► success   → order.status = PAID
   │               → send status update email
   │
   ├──► failed    → order.status = CANCELLED (or manual review)
   │
   └──► refunded  → admin action, manual refund process
```

---

## 11. IoT & Background Scheduler

### Scheduler Architecture

```
Application Start (create_app)
        │
        ▼
┌───────────────────────────────────┐
│ IoT Scheduler (APScheduler)       │
│ BackgroundScheduler               │
│ ThreadPoolExecutor (max_workers=4)│
│ Timezone: Africa/Douala           │
│                                   │
│  Job: poll_aquaculture  ──────────┤──► ModBus TCP ──► AquacultureRecord
│  Interval: 5 min                  │    (MODBUS_AQUA_HOST)
│                                   │
│  Job: poll_poultry  ──────────────┤──► ModBus TCP ──► PoultryRecord
│  Interval: 5 min                  │    (MODBUS_CLIMATE_HOST)
│                                   │
│  Job: poll_cuniculture  ──────────┤──► ModBus TCP ──► CunicultureRecord
│  Interval: 5 min                  │    (MODBUS_CLIMATE_HOST)
└───────────────────────────────────┘
```

### Sensor Polling Logic

```python
def poll_aquaculture(app):
    with app.app_context():
        client = ModbusTcpClient(host=MODBUS_AQUA_HOST, port=502)
        if not client.connect():
            logger.warning("ModBus aquaculture: connection failed (stub mode)")
            # Fall back to stub: generate realistic random readings
            return
        
        for pond in Pond.find_all({"status": "active"}):
            regs = client.read_holding_registers(address=0, count=4)
            record = AquacultureRecord(
                pond_id=str(pond._id),
                water_temp_c=regs.registers[0] / 10.0,  # e.g., 264 → 26.4°C
                ph=regs.registers[1] / 100.0,
                dissolved_oxygen_mgl=regs.registers[2] / 10.0,
                turbidity_ntu=regs.registers[3],
                ...
            )
            record.save()
        client.close()
```

### Stub Mode (No Physical Sensors)

When `MODBUS_AQUA_HOST` / `MODBUS_CLIMATE_HOST` are not configured, the poller falls back to generating simulated data within realistic ranges:

| Sensor | Range |
|--------|-------|
| Water temperature | 22–30°C |
| pH | 6.5–8.5 |
| Dissolved O₂ | 5–12 mg/L |
| Turbidity | 0–50 NTU |
| Ambient temperature | 20–35°C |
| Humidity | 40–85% |

### SSE Live Dashboard

```
Browser → GET /iot/stream (EventSource)
                │
                │ every 8 seconds
                ▼
        Flask generates:
        data: {
          "aqua": [{ pond_id, temp, ph, o2, turbidity, date }],
          "poultry": [{ flock_id, temp, humidity }],
          "cuniculture": [{ batch_id, temp }]
        }
        ←─────── streamed to browser

Browser DOM:
  document.querySelector('[data-pond-id="..."]')
    .querySelector('[data-field="temp"]')
    .textContent = "26.4°C"
```

---

## 12. Email System

### Overview

```
app/email.py
    │
    ├── send_order_confirmation(order)
    │       └─ Renders: templates/email/order_confirmation.html
    │          Subject: "Confirmation de commande {order.order_number}"
    │          To: order customer's User.email
    │
    └── send_order_status_update(order)
            └─ Renders: templates/email/order_status_update.html
               Subject: "Mise à jour de votre commande {order.order_number}"
               To: order customer's User.email
```

### Email Template Variables

**order_confirmation.html:**

```
{{ order.order_number }}
{{ order.customer_name }}
{{ order.customer_phone }}
{{ order.customer_address }}
{{ order.status_label() }}
{{ order.payment_method_label() }}
{{ order.total_xaf }}
{{ order.items }}           ← list of OrderItem
{{ order_url }}             ← BASE_URL + /marketplace/order/{number}
```

**order_status_update.html** — same variables plus `{{ order.status_label() }}` highlighting the new status.

### Locale-Aware Rendering

```python
# Determine customer's language preference
if order.customer_id:
    user = User.get_by_id(order.customer_id)
    lang = user.language if user else "fr"
else:
    lang = "fr"   # anonymous customer defaults to French

with force_locale(lang):
    html = render_template("email/order_confirmation.html", ...)

mail.send(Message(subject=subject, recipients=[email], html=html))
```

### Silent Failure

Emails never raise exceptions — failures are logged and swallowed:

```python
try:
    mail.send(msg)
except Exception as exc:
    app.logger.error(f"Email failed: {exc}")
    # flow continues normally
```

### Skip Conditions

- `MAIL_USERNAME` is empty or starts with `[PLACEHOLDER` → skip silently (dev mode)
- Customer has no email on record → skip

---

## 13. REST API Reference

**Base URL:** `/api/v1`  
**Content-Type:** `application/json`  
**OpenAPI spec:** `GET /api/v1/openapi.json`  
**Interactive docs:** `GET /api/v1/docs` (Swagger UI)

---

### Authentication Endpoints

#### `POST /api/v1/auth/token`

Obtain access and refresh tokens.

**Request:**
```json
{
  "username": "admin",
  "password": "secret"
}
```

**Response 200:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "64abc123...",
    "username": "admin",
    "role": "admin"
  }
}
```

**Response 401:**
```json
{ "error": "Identifiants invalides" }
```

---

#### `POST /api/v1/auth/refresh`

**Headers:** `Authorization: Bearer <refresh_token>`

**Response 200:**
```json
{ "access_token": "eyJ..." }
```

---

### Public Endpoints

#### `GET /api/v1/status`

Health check. No authentication required.

**Response 200:**
```json
{
  "status": "ok",
  "version": "1.0",
  "timestamp": "2026-06-04T10:30:00Z"
}
```

---

#### `GET /api/v1/products`

List available products with pagination.

**Query parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | int | Page number (default: 1) |
| `per_page` | int | Items per page (default: 20, max: 100) |
| `category` | string | Filter by category enum value |
| `q` | string | Search in name + description |
| `min_price` | float | Minimum price (XAF) |
| `max_price` | float | Maximum price (XAF) |

**Response 200:**
```json
{
  "products": [
    {
      "id": "64abc...",
      "name": "Tilapia frais",
      "description": "Élevage naturel...",
      "category": "fish",
      "category_label": "Poisson",
      "category_icon": "🐟",
      "price_xaf": 2500.0,
      "unit": "kg",
      "stock_quantity": 45.5,
      "is_available": true,
      "image_url": "/marketplace/images/64def...",
      "detail_url": "/marketplace/product/64abc...",
      "add_cart_url": "/marketplace/cart/add"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 12,
    "pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

---

#### `GET /api/v1/products/<product_id>`

Single product detail.

**Response 404:**
```json
{ "error": "Produit introuvable" }
```

---

### Protected Endpoints (Bearer token required)

#### `GET /api/v1/orders`

List current user's orders.

**Query parameters:** `page`, `per_page`, `status`

**Response 200:**
```json
{
  "orders": [
    {
      "id": "64abc...",
      "order_number": "OMF-2026-A3B7C2",
      "status": "delivered",
      "status_label": "Livré",
      "total_xaf": 7500.0,
      "created_at": "2026-06-04T09:00:00Z",
      "items_count": 3
    }
  ],
  "pagination": { ... }
}
```

---

#### `GET /api/v1/orders/<order_number>`

Order detail. Admins see all orders; others only their own (403 otherwise).

**Response 200:**
```json
{
  "order": {
    "order_number": "OMF-2026-A3B7C2",
    "status": "paid",
    "customer_name": "Jean Dupont",
    "customer_phone": "+235 66 XX XX XX",
    "total_xaf": 7500.0,
    "items": [
      {
        "product_name": "Tilapia frais",
        "unit_price_xaf": 2500.0,
        "quantity": 3.0,
        "unit": "kg",
        "subtotal_xaf": 7500.0
      }
    ],
    "payment": {
      "method": "orange_money",
      "status": "success",
      "completed_at": "2026-06-04T09:05:00Z"
    },
    "created_at": "2026-06-04T09:00:00Z"
  }
}
```

---

#### `POST /api/v1/orders`

Create a new order. Rate-limited: 10/min.

**Request:**
```json
{
  "customer_name": "Jean Dupont",
  "customer_phone": "+235 66 XX XX XX",
  "customer_address": "Quartier Moursal, N'Djamena",
  "payment_method": "orange_money",
  "mobile_money_phone": "+235 66 XX XX XX",
  "notes": "Livrer avant 18h",
  "items": [
    { "product_id": "64abc...", "quantity": 3.0 },
    { "product_id": "64def...", "quantity": 2.5 }
  ]
}
```

**Response 201:**
```json
{
  "order_number": "OMF-2026-A3B7C2",
  "status": "payment_pending",
  "total_xaf": 11250.0,
  "payment_url": "https://orange.money/pay/..."
}
```

**Response 409 (stock error):**
```json
{ "error": "Stock insuffisant pour : Tilapia frais" }
```

---

### Error Response Format

All API errors use the same structure:

```json
{
  "error": "Human-readable error message",
  "code": "MACHINE_READABLE_CODE"   ← optional
}
```

| HTTP Code | Meaning |
|-----------|---------|
| 400 | Validation error / bad request |
| 401 | Missing or invalid token |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 409 | Conflict (e.g., insufficient stock) |
| 429 | Rate limit exceeded |
| 500 | Server error |

---

## 14. Frontend Design System

### Layout Structure

```
Authenticated (base.html):                Public shop (base_shop.html):

┌──────────────────────────────┐          ┌──────────────────────────────┐
│ #sidebar (fixed, w-60)        │          │ .shop-nav (sticky, h-16)      │
│  ┌─ Logo                     │          │  Logo | Nav links | Cart btn  │
│  ├─ Nav sections              │          └──────────────────────────────┘
│  │   Production               │
│  │   Commerce                 │          ┌──────────────────────────────┐
│  │   Gestion                  │          │  <main>                       │
│  │   Système                  │          │  {% block content %}          │
│  │   Admin                    │          └──────────────────────────────┘
│  └─ User + theme + lang      │
├──────────────────────────────┤          ┌──────────────────────────────┐
│ lg:ml-60 main area           │          │  .shop-footer                 │
│  ┌─ .desktop-topbar (lg:flex)│          └──────────────────────────────┘
│  ├─ .mobile-topbar (lg:hidden)
│  ├─ Flash messages            │          Mobile: #mobile-drawer (slide-in)
│  └─ <main> {% block content %}
└──────────────────────────────┘
```

### CSS Custom Classes (premium.css)

#### Stat Card Backgrounds

```
.bg-stat-cyan   → aquaculture / water    (cyan gradient)
.bg-stat-amber  → poultry                (amber gradient)
.bg-stat-orange → cuniculture            (orange gradient)
.bg-stat-brand  → revenue / general      (green gradient)
.bg-stat-red    → expenses / danger      (red gradient)
.bg-stat-violet → admin / users          (violet gradient)
.bg-stat-indigo → system / IoT           (indigo gradient)
.bg-stat-slate  → neutral                (slate gradient)
```

#### Swatch Backgrounds (sensor/metric tiles)

```
.swatch-cyan · .swatch-green · .swatch-brand · .swatch-blue
.swatch-amber · .swatch-orange · .swatch-red · .swatch-slate
.swatch-indigo · .swatch-violet
```

Each has automatic `.dark` mode variant.

#### Icon Backgrounds

```
.icon-bg-cyan · .icon-bg-amber · .icon-bg-orange
.icon-bg-brand · .icon-bg-indigo · .icon-bg-violet
.icon-bg-red · .icon-bg-blue
```

#### Badges

```python
# Jinja2 macro
{{ status_badge('active',      _('Actif')) }}     # green
{{ status_badge('inactive',    _('Inactif')) }}   # slate
{{ status_badge('maintenance', _('Maintenance'))} # amber
{{ status_badge('harvested',   _('Récolté')) }}   # blue
{{ status_badge('culled',      _('Réformé')) }}   # red
```

**Direct CSS classes:**
```
.badge-p           — base badge
.badge-active-p    — green (active/delivered/paid)
.badge-inactive-p  — slate (inactive)
.badge-maint-p     — amber (pending/processing)
.badge-harvest-p   — blue (shipped/sold)
.badge-culled-p    — red (cancelled/culled/deceased)
```

#### Buttons

```
.btn-premium-primary  — brand green gradient, shadow, hover lift
```

#### Layout Components

```
.page-hero       — white card for page header strip
.card-inset      — premium inset shadow for cards
.shadow-card     — subtle multi-layer card shadow
.shadow-card-md  — elevated card shadow (on hover)
.form-section    — white rounded card for form sections
.tbl-premium     — styled table (thead gradient, hover rows)
.empty-icon-p    — centered empty-state icon box
.section-header  — uppercase section divider text
.desktop-topbar  — sticky glassmorphism top bar
.mobile-topbar   — dark mobile top bar
```

#### Color Trend Pills

```
.trend-up   → green (positive change)
.trend-down → red (negative change)
.trend-flat → slate (no change)
```

### Jinja2 Macros (`macros.html`)

```python
# Import
{% from 'macros.html' import render_field, status_badge, stat_card,
                              breadcrumb, empty_state, delete_btn, paginate %}

# Form field with label, error display, and focus styling
{{ render_field(form.customer_name, placeholder="Jean Dupont") }}

# Page breadcrumb
{{ breadcrumb([
    (url_for('marketplace.index'), _('Marché')),
    ('#', product.name)
]) }}

# Stats card (gradient background + icon)
{{ stat_card(_('Bassins'), pond_count, '🐟', 'bg-stat-cyan') }}

# Empty state with CTA button
{{ empty_state('🐟', _('Aucun bassin'), _('Créez votre premier bassin.'),
               url_for('aquaculture.create_pond'), _('Créer un bassin')) }}

# Premium pagination
{{ paginate(pagination) }}

# Confirm-then-delete form
{{ delete_btn(url_for('finance.delete_entry', entry_id=e.id),
              _('Supprimer'), _('Supprimer cette entrée ?')) }}
```

### Theme & Internationalization

**Theme toggle:** `toggleTheme()` in `base.html` — toggles `.dark` class on `<html>`, persists to DB via `GET /auth/set-theme/<theme>`.

**Language toggle:** Two-item pill in sidebar bottom — calls `GET /auth/set-language/<code>`. Language stored in session and user DB record.

**Locale detection order:**

```python
def get_locale():
    if session.get("lang"):
        return session["lang"]
    if current_user.is_authenticated:
        return current_user.language
    return request.accept_languages.best_match(["fr", "en"]) or "fr"
```

---

## 15. Security Model

### Defense Layers

```
Layer 1 — Network
  └─ HTTPS enforced (reverse proxy / Nginx)

Layer 2 — Rate Limiting (Flask-Limiter → Redis)
  ├─ Global:      500/day, 100/hour
  ├─ Login:       10/minute (prevents brute force)
  ├─ Register:    5/minute
  ├─ Cart add:    60/minute
  ├─ API orders:  10/minute
  └─ API tokens:  20/minute

Layer 3 — Authentication
  ├─ Web:  Flask-Login session cookie (HttpOnly, Secure, SameSite=Lax)
  └─ API:  JWT Bearer (HS256, 1h expiry)

Layer 4 — Authorization
  ├─ RBAC: admin / technician / client
  ├─ Route decorators: @admin_required, @technician_required
  └─ Resource ownership: order access checks customer_id vs JWT identity

Layer 5 — Input Validation
  ├─ CSRF: WTF_CSRF_ENABLED=True, 1h token lifetime
  ├─ WTForms: all web forms validated server-side
  └─ API: manual validation + type coercion

Layer 6 — Data Security
  ├─ Passwords: bcrypt (min cost 12)
  ├─ MongoDB: auth required, replica set TLS-capable
  └─ Secrets: environment variables, never in code

Layer 7 — Error Handling
  ├─ Custom error pages (no stack traces to users)
  ├─ Sentry for production error aggregation
  └─ Rotating log file (max 10 MB, 5 backups)
```

### CSRF Protection

All state-changing web forms include:

```html
{{ form.hidden_tag() }}       {# WTForms renders: #}
<input type="hidden" name="csrf_token" value="...">
```

For AJAX requests:

```html
<meta name="csrf-token" content="{{ csrf_token() }}" />
```

```javascript
const csrfToken = document.querySelector('meta[name=csrf-token]').content;
fetch(url, {
    method: "POST",
    headers: { "X-CSRFToken": csrfToken },
    ...
});
```

### Admin Safety Guard

```python
# Prevents demoting or deleting the last admin
if user.role == UserRole.ADMIN:
    admin_count = User.count({"role": "admin"})
    if admin_count <= 1:
        flash("Impossible de supprimer le dernier administrateur.", "danger")
        return redirect(...)
```

---

## 16. Development Setup

### Prerequisites

- Python 3.11+
- MongoDB 6+ (replica set **required** for transactions; see below for single-node)
- Redis (optional; falls back to in-memory)
- Git

### 1. Clone & Install

```bash
git clone https://github.com/b9bogo1/OmniFarm.git
cd OmniFarm

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. MongoDB Single-Node Replica Set (dev)

A replica set is needed even locally for multi-document transactions:

```bash
# Start MongoDB with replica set name
mongod --replSet rs0 --dbpath ./data/db --port 27017

# In mongo shell, initialize the replica set
mongosh
> rs.initiate()
> rs.status()
```

`.env` for single-node:
```ini
MONGO_URI=mongodb://localhost:27017/omnifarm_db?replicaSet=rs0
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
```

Minimum required for local dev:

```ini
SECRET_KEY=dev-secret-change-me
MONGO_URI=mongodb://localhost:27017/omnifarm_db?replicaSet=rs0
FLASK_ENV=development
JWT_SECRET_KEY=dev-jwt-secret
```

### 4. Run the Application

```bash
flask run
# or with hot reload:
flask run --debug
```

Visit: [http://localhost:5000](http://localhost:5000)

On first visit, you'll be redirected to `/setup` to create the initial admin account.

### 5. Common Dev Commands

```bash
# Open Python shell with app context
flask shell

# Access MongoDB directly
mongosh omnifarm_db

# Run IoT scheduler standalone (for testing)
flask run &
curl http://localhost:5000/iot/stream  # SSE test

# Extract/compile translations
pybabel extract -F babel.cfg -o messages.pot .
pybabel update -i messages.pot -d app/translations
pybabel compile -d app/translations
```

---

## 17. Testing

### Test Stack

- **pytest** — test runner
- **pytest-flask** — Flask test client integration
- **mongomock** — in-memory MongoDB mock (no real DB needed)

### Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_auth.py

# Verbose with output
pytest -v -s

# Stop on first failure
pytest -x

# Coverage (requires pytest-cov)
pytest --cov=app --cov-report=html
```

### Test Configuration (`pytest.ini`)

```ini
[pytest]
testpaths = tests
flask_app = run:app    # or your app entry point
```

### Test Fixtures (`tests/conftest.py`)

```python
@pytest.fixture
def app():
    """App factory with mongomock + test config."""
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "MONGO_URI": "mongomock://localhost/omnifarm_test",
        "JWT_SECRET_KEY": "test-secret",
        "RATELIMIT_ENABLED": False,
    })
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def admin_user(app):
    """Pre-created admin user for auth tests."""
    with app.app_context():
        user = User(username="admin", email="admin@test.com",
                    role=UserRole.ADMIN)
        user.set_password("password123")
        user.save()
    return user
```

### Test Coverage Areas

| File | What's Tested |
|------|---------------|
| `test_auth.py` | Login/logout, registration, role checks, CSRF bypass (test mode) |
| `test_api.py` | Token issuance, refresh, product listing, order creation, rate limits |
| `test_marketplace.py` | Cart operations, checkout flow, stock decrement, InsufficientStockError |

### Writing a New Test

```python
def test_add_to_cart(client, app):
    # Create product in DB
    with app.app_context():
        product = Product(name="Test", price_xaf=1000, stock_quantity=10,
                          category=ProductCategory.FISH, unit="kg")
        product.save()
        pid = str(product._id)

    # Add to cart
    response = client.post("/marketplace/cart/add",
                           data={"product_id": pid, "quantity": "2"},
                           follow_redirects=True)
    assert response.status_code == 200

    # Verify cart in session
    with client.session_transaction() as sess:
        assert pid in sess.get("cart", {})
        assert sess["cart"][pid] == 2.0
```

---

## 18. Deployment

### Production Checklist

```
[ ] SECRET_KEY            — strong random 64+ chars
[ ] JWT_SECRET_KEY        — strong random 64+ chars
[ ] FLASK_ENV=production
[ ] SENTRY_DSN            — configured
[ ] MONGO_URI             — replica set with auth + TLS
[ ] REDIS_URL             — configured
[ ] MAIL_*                — valid SMTP credentials
[ ] BASE_URL              — production domain
[ ] WTF_CSRF_TIME_LIMIT=3600
[ ] USE_ASSETS_BUNDLE=true  — serves minified CSS/JS
```

### Gunicorn Command

```bash
gunicorn "app:create_app()" \
  --workers 4 \
  --worker-class sync \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

> **Note:** APScheduler runs in the main worker process. With multi-worker Gunicorn, set `--preload` to prevent duplicate scheduler instances, or use a separate scheduler process.

### Docker Compose (example)

```yaml
version: "3.9"
services:

  web:
    build: .
    command: gunicorn "app:create_app()" --workers 2 --bind 0.0.0.0:8000
    env_file: .env
    depends_on: [mongo-1, redis]
    ports: ["8000:8000"]

  mongo-1:
    image: mongo:7
    command: mongod --replSet rs0 --port 27017
    volumes: [mongo1_data:/data/db]

  mongo-2:
    image: mongo:7
    command: mongod --replSet rs0 --port 27017
    volumes: [mongo2_data:/data/db]

  mongo-3:
    image: mongo:7
    command: mongod --replSet rs0 --port 27017
    volumes: [mongo3_data:/data/db]

  redis:
    image: redis:7-alpine

volumes:
  mongo1_data:
  mongo2_data:
  mongo3_data:
```

### MongoDB Replica Set Init (production)

```bash
mongosh --host mongo-1 --eval '
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongo-1:27017", priority: 2 },
    { _id: 1, host: "mongo-2:27017", priority: 1 },
    { _id: 2, host: "mongo-3:27017", priority: 1 },
  ]
})'
```

### Nginx Reverse Proxy (example)

```nginx
server {
    listen 80;
    server_name omnifarm.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name omnifarm.example.com;

    ssl_certificate     /etc/ssl/certs/omnifarm.crt;
    ssl_certificate_key /etc/ssl/private/omnifarm.key;

    client_max_body_size 10M;    # for image uploads

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    # SSE: disable buffering for /iot/stream
    location /iot/stream {
        proxy_pass http://127.0.0.1:8000;
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection "";
        proxy_http_version 1.1;
    }

    location /static/ {
        alias /app/app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

---

*OmniFarm Hub · © 2026 · Built with Flask, MongoDB & Tailwind CSS*
