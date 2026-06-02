import json
from datetime import date, timedelta, datetime, timezone

from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from flask_babel import gettext as _

from . import main_bp
from app.db import get_col
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
