import json
import os
from datetime import date, timedelta, datetime, timezone

from flask import render_template, redirect, url_for, current_app
from flask_login import login_required, current_user
from flask_babel import gettext as _

from . import main_bp
from app.db import get_col
from app.auth.decorators import admin_required
from app.models.user import User
from app.models.aquaculture import Pond, PondStatus
from app.models.poultry import Flock, FlockStatus
from app.models.cuniculture import RabbitBatch, RabbitStatus
from app.models.marketplace import Order, OrderStatus
from app.models.finance import FinanceEntry, EntryType
from app.models.health import HealthEvent


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('marketplace.index'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    from app.iot.scheduler import get_scheduler

    ctx = {'title': _('Tableau de bord')}

    ctx['pond_count']  = Pond.count_by_status(PondStatus.ACTIVE)
    ctx['flock_count'] = Flock.count_by_status(FlockStatus.ACTIVE)
    ctx['batch_count'] = RabbitBatch.count_by_status(RabbitStatus.ACTIVE)

    if current_user.is_admin or current_user.is_technician:
        ctx['user_count'] = User.count_all() if current_user.is_admin else None

        # Order counts via aggregation
        status_counts = Order.count_by_statuses()
        ctx['order_count'] = sum(status_counts.values())
        _pending_vals = [OrderStatus.PENDING.value, OrderStatus.PAYMENT_PENDING.value,
                         OrderStatus.PROCESSING.value]
        ctx['pending_orders'] = sum(status_counts.get(s, 0) for s in _pending_vals)
        ctx['recent_orders']  = Order.recent(5)

        scheduler = get_scheduler()
        ctx['iot_running'] = scheduler.running if scheduler else False
        ctx['iot_jobs']    = len(scheduler.get_jobs()) if scheduler and scheduler.running else 0

        # ── Finance totals + monthly chart ────────────────────────────────
        today  = date.today()
        months = []
        for i in range(5, -1, -1):
            months.append((today.replace(day=1) - timedelta(days=i * 28)).replace(day=1))

        all_rows = FinanceEntry.monthly_totals()

        monthly = {}
        total_rev, total_exp = 0.0, 0.0
        for row in all_rows:
            yr, mo, etype = row['_id']['yr'], row['_id']['mo'], row['_id']['type']
            key = (yr, mo)
            monthly.setdefault(key, {})[etype] = float(row['total'])
            if etype == EntryType.REVENUE.value:
                total_rev += float(row['total'])
            else:
                total_exp += float(row['total'])

        labels, revenues, expenses = [], [], []
        for first in months:
            labels.append(first.strftime('%b %Y'))
            d = monthly.get((first.year, first.month), {})
            revenues.append(d.get(EntryType.REVENUE.value, 0))
            expenses.append(d.get(EntryType.EXPENSE.value, 0))

        ctx['chart_labels']      = json.dumps(labels)
        ctx['chart_revenues']    = json.dumps(revenues)
        ctx['chart_expenses']    = json.dumps(expenses)
        ctx['total_revenue_all'] = total_rev
        ctx['total_expense_all'] = total_exp
        ctx['net_balance_all']   = total_rev - total_exp

        # ── Order-status donut ────────────────────────────────────────────
        _status_label_map = {
            'pending':         _('En attente'),
            'payment_pending': _('Paiement'),
            'paid':            _('Payée'),
            'processing':      _('Traitement'),
            'shipped':         _('Expédiée'),
            'delivered':       _('Livrée'),
            'cancelled':       _('Annulée'),
        }
        order_status_labels, order_status_data = [], []
        for sv, count in status_counts.items():
            order_status_labels.append(_status_label_map.get(sv, sv))
            order_status_data.append(count)
        ctx['order_status_labels'] = json.dumps(order_status_labels)
        ctx['order_status_data']   = json.dumps(order_status_data)

        # ── Species / production donut ────────────────────────────────────
        ctx['species_labels'] = json.dumps([_('Bassins'), _('Volailles'), _('Lapins')])
        ctx['species_data']   = json.dumps([ctx['pond_count'], ctx['flock_count'], ctx['batch_count']])

        # ── Recent activity feed ──────────────────────────────────────────
        activity = []

        for o in Order.recent(3):
            activity.append({
                'type': 'order', 'icon': '📦',
                'dot_cls': 'bg-amber-500',
                'label': f"{o.order_number} — {o.customer_name}",
                'meta': o.status_label(),
                'ts': o.created_at,
            })

        try:
            recent_health = list(
                get_col('health_events').find().sort('event_date', -1).limit(3)
            )
            from app.models.health import HealthEvent
            for ev in [HealthEvent(d) for d in recent_health]:
                activity.append({
                    'type': 'health', 'icon': '🩺',
                    'dot_cls': 'bg-indigo-500',
                    'label': f"{ev.unit_icon()} {ev.unit_name} — {ev.event_type_label()}",
                    'meta': ev.event_date.strftime('%d/%m/%Y') if ev.event_date else '',
                    'ts': ev.event_date,
                })
        except Exception:
            pass

        recent_finance = list(
            get_col('finance_entries').find().sort('entry_date', -1).limit(3)
        )
        for fe in [FinanceEntry(d) for d in recent_finance]:
            activity.append({
                'type': 'finance', 'icon': fe.category_icon(),
                'dot_cls': 'bg-emerald-500' if fe.entry_type == EntryType.REVENUE else 'bg-red-500',
                'label': fe.description,
                'meta': ('+' if fe.entry_type == EntryType.REVENUE else '−')
                        + f"{fe.amount_float:,.0f} FCFA",
                'ts': fe.entry_date,
            })

        activity.sort(key=lambda x: x['ts'] if x['ts'] else date.min, reverse=True)
        ctx['activity_feed'] = activity[:8]

    return render_template('main/dashboard.html', **ctx)


@main_bp.route('/health')
def health():
    return {'status': 'ok', 'app': 'OmniFarm Hub'}, 200


@main_bp.route('/admin/monitor')
@login_required
@admin_required
def admin_monitor():
    from app.iot.scheduler import get_scheduler
    from app.extensions import mongo

    # ── MongoDB health ────────────────────────────────────────────────────
    try:
        mongo.cx.admin.command('ping')
        mongo_ok = True
        rs_status = mongo.cx.admin.command('replSetGetStatus')
        rs_members = [
            {
                'name':   m.get('name'),
                'state':  m.get('stateStr'),
                'health': m.get('health'),
            }
            for m in rs_status.get('members', [])
        ]
    except Exception as exc:
        mongo_ok = False
        rs_members = []

    # ── Scheduler ─────────────────────────────────────────────────────────
    scheduler = get_scheduler()
    jobs = []
    if scheduler and scheduler.running:
        jobs = [
            {
                'id':       j.id,
                'name':     j.name,
                'next_run': j.next_run_time,
                'trigger':  str(j.trigger),
            }
            for j in scheduler.get_jobs()
        ]

    # ── Log tail ──────────────────────────────────────────────────────────
    log_lines = []
    log_file  = current_app.config.get('LOG_FILE', 'logs/omnifarm.log')
    try:
        if os.path.exists(log_file):
            with open(log_file, encoding='utf-8', errors='replace') as fh:
                all_lines = fh.readlines()
            log_lines = all_lines[-200:]
            log_lines.reverse()
    except Exception:
        pass

    # ── DB stats ──────────────────────────────────────────────────────────
    try:
        stats = {
            'users':         get_col('users').count_documents({}),
            'orders':        get_col('orders').count_documents({}),
            'products':      get_col('products').count_documents({}),
            'finance':       get_col('finance_entries').count_documents({}),
            'health_events': get_col('health_events').count_documents({}),
        }
    except Exception:
        stats = {}

    # ── Error count (lines with ERROR in last 200) ────────────────────────
    error_count = sum(1 for ln in log_lines if ' ERROR ' in ln or ' CRITICAL ' in ln)

    return render_template(
        'main/admin_monitor.html',
        title=_('Monitoring système'),
        mongo_ok=mongo_ok,
        rs_members=rs_members,
        scheduler_running=scheduler.running if scheduler else False,
        jobs=jobs,
        log_lines=log_lines,
        db_stats=stats,
        error_count=error_count,
    )
