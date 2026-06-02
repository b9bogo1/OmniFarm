import csv
import io
from datetime import date, datetime, timezone

from flask import render_template, request, Response, abort
from flask_babel import gettext as _

from app.db import get_col, date_to_dt
from app.models.aquaculture import AquacultureRecord, Pond
from app.models.poultry import PoultryRecord, Flock
from app.models.cuniculture import CunicultureRecord, RabbitBatch
from app.models.marketplace import Order, OrderStatus
from app.models.finance import FinanceEntry
from app.models.health import HealthEvent
from app.auth.decorators import technician_required
from . import reports_bp


def _parse_date(val):
    if not val:
        return None
    try:
        return date.fromisoformat(val)
    except ValueError:
        return None


def _csv_response(rows, headers, filename):
    output = io.StringIO()
    writer = csv.writer(output, dialect='excel')
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@reports_bp.route('/')
@technician_required
def index():
    metrics = {
        'aquaculture': AquacultureRecord.count_all(),
        'poultry':     PoultryRecord.count_all(),
        'cuniculture': CunicultureRecord.count_all(),
        'finance':     FinanceEntry.count_all(),
        'health':      HealthEvent.count_all(),
        'orders':      Order.count_all(),
    }
    return render_template('reports/index.html', title=_('Rapports'), metrics=metrics)


@reports_bp.route('/export/aquaculture')
@technician_required
def export_aquaculture():
    date_from = _parse_date(request.args.get('from'))
    date_to   = _parse_date(request.args.get('to'))

    filt: dict = {}
    if date_from:
        filt.setdefault('record_date', {})['$gte'] = date_to_dt(date_from)
    if date_to:
        filt.setdefault('record_date', {})['$lte'] = date_to_dt(date_to)

    rec_docs = list(get_col('aquaculture_records').find(filt).sort('record_date', -1))
    pond_ids  = list({d['pond_id'] for d in rec_docs if d.get('pond_id')})
    ponds_map = {p.id: p for p in [Pond.get_by_id(pid) for pid in pond_ids] if p}

    headers = [
        'Date', 'Bassin', 'Espèce', 'Effectif', 'Poids moy (g)',
        'Aliment (kg)', 'Type aliment', 'Mortalité', 'Cause mortalité',
        'Temp eau (°C)', 'pH', 'O2 dissous (mg/L)', 'Turbidité (NTU)', 'Notes',
    ]
    rows = []
    for d in rec_docs:
        r = AquacultureRecord(d)
        p = ponds_map.get(r.pond_id)
        rows.append([
            r.record_date.strftime('%d/%m/%Y') if r.record_date else '',
            p.name if p else '', p.species if p else '',
            r.current_count, r.avg_weight_g,
            r.feed_quantity_kg, r.feed_type or '',
            r.mortality_count, r.mortality_cause or '',
            r.water_temp_c, r.ph, r.dissolved_oxygen_mgl, r.turbidity_ntu,
            r.notes or '',
        ])
    return _csv_response(rows, headers, 'aquaculture_records.csv')


@reports_bp.route('/export/poultry')
@technician_required
def export_poultry():
    date_from = _parse_date(request.args.get('from'))
    date_to   = _parse_date(request.args.get('to'))

    filt: dict = {}
    if date_from:
        filt.setdefault('record_date', {})['$gte'] = date_to_dt(date_from)
    if date_to:
        filt.setdefault('record_date', {})['$lte'] = date_to_dt(date_to)

    rec_docs  = list(get_col('poultry_records').find(filt).sort('record_date', -1))
    flock_ids = list({d['flock_id'] for d in rec_docs if d.get('flock_id')})
    flocks_map = {f.id: f for f in [Flock.get_by_id(fid) for fid in flock_ids] if f}

    headers = [
        'Date', 'Lot', 'Espèce', 'Race', 'Aliment (kg)', 'Type aliment',
        'Eau (L)', 'Œufs', 'Poids moy (g)', 'Mortalité', 'Cause',
        'Temp amb (°C)', 'Humidité (%)', 'Notes',
    ]
    rows = []
    for d in rec_docs:
        r = PoultryRecord(d)
        f = flocks_map.get(r.flock_id)
        rows.append([
            r.record_date.strftime('%d/%m/%Y') if r.record_date else '',
            f.name if f else '', f.species if f else '', f.breed if f else '',
            r.feed_quantity_kg, r.feed_type or '', r.water_consumed_l,
            r.eggs_collected, r.avg_weight_g,
            r.mortality_count, r.mortality_cause or '',
            r.ambient_temp_c, r.humidity_pct,
            r.notes or '',
        ])
    return _csv_response(rows, headers, 'aviculture_records.csv')


@reports_bp.route('/export/cuniculture')
@technician_required
def export_cuniculture():
    date_from = _parse_date(request.args.get('from'))
    date_to   = _parse_date(request.args.get('to'))

    filt: dict = {}
    if date_from:
        filt.setdefault('record_date', {})['$gte'] = date_to_dt(date_from)
    if date_to:
        filt.setdefault('record_date', {})['$lte'] = date_to_dt(date_to)

    rec_docs   = list(get_col('cuniculture_records').find(filt).sort('record_date', -1))
    batch_ids  = list({d['batch_id'] for d in rec_docs if d.get('batch_id')})
    batches_map = {b.id: b for b in [RabbitBatch.get_by_id(bid) for bid in batch_ids] if b}

    headers = [
        'Date', 'Lot', 'Race', 'Aliment (kg)', 'Type aliment',
        'Portées', 'Lapereaux nés', 'Lapereaux survivants',
        'Poids moy (g)', 'Mortalité', 'Cause', 'Temp amb (°C)', 'Notes',
    ]
    rows = []
    for d in rec_docs:
        r = CunicultureRecord(d)
        b = batches_map.get(r.batch_id)
        rows.append([
            r.record_date.strftime('%d/%m/%Y') if r.record_date else '',
            b.name if b else '', b.breed if b else '',
            r.feed_quantity_kg, r.feed_type or '',
            r.litters_born, r.kits_born, r.kits_survived,
            r.avg_weight_g, r.mortality_count, r.mortality_cause or '',
            r.ambient_temp_c, r.notes or '',
        ])
    return _csv_response(rows, headers, 'cuniculture_records.csv')


@reports_bp.route('/export/finance')
@technician_required
def export_finance():
    date_from = _parse_date(request.args.get('from'))
    date_to   = _parse_date(request.args.get('to'))
    entries   = FinanceEntry.find_filtered(month_filter='')

    if date_from or date_to:
        entries = FinanceEntry.find_filtered(month_filter='')
        if date_from:
            entries = [e for e in entries if e.entry_date and e.entry_date >= date_from]
        if date_to:
            entries = [e for e in entries if e.entry_date and e.entry_date <= date_to]

    headers = [
        'Date', 'Type', 'Catégorie', 'Description', 'Montant (FCFA)',
        'Unité', 'Moyen paiement', 'Référence', 'Notes',
    ]
    rows = [
        [
            e.entry_date.strftime('%d/%m/%Y') if e.entry_date else '',
            e.entry_type.value,
            e.category,
            e.description,
            e.amount_float,
            e.production_scope.value if hasattr(e.production_scope, 'value') else e.production_scope,
            e.payment_method or '',
            e.reference_number or '',
            e.notes or '',
        ]
        for e in entries
    ]
    return _csv_response(rows, headers, 'finances.csv')


@reports_bp.route('/export/health')
@technician_required
def export_health():
    date_from = _parse_date(request.args.get('from'))
    date_to   = _parse_date(request.args.get('to'))
    events    = HealthEvent.find_filtered()
    if date_from:
        events = [ev for ev in events if ev.event_date and ev.event_date >= date_from]
    if date_to:
        events = [ev for ev in events if ev.event_date and ev.event_date <= date_to]

    headers = [
        'Date', 'Espèce', 'Lot/Bassin', 'Événement', 'Produit',
        'Dose', 'Administré par', 'Prochaine échéance', 'Coût (FCFA)', 'Notes',
    ]
    rows = [
        [
            ev.event_date.strftime('%d/%m/%Y') if ev.event_date else '',
            ev.production_unit.value if hasattr(ev.production_unit, 'value') else ev.production_unit,
            ev.unit_name,
            ev.event_type.value if hasattr(ev.event_type, 'value') else ev.event_type,
            ev.product_used or '',
            ev.dose or '',
            ev.administered_by or '',
            ev.next_due_date.strftime('%d/%m/%Y') if ev.next_due_date else '',
            ev.cost_float,
            ev.notes or '',
        ]
        for ev in events
    ]
    return _csv_response(rows, headers, 'sante_animale.csv')


@reports_bp.route('/export/orders')
@technician_required
def export_orders():
    date_from = _parse_date(request.args.get('from'))
    date_to   = _parse_date(request.args.get('to'))

    filt: dict = {}
    if date_from:
        filt.setdefault('created_at', {})['$gte'] = date_to_dt(date_from)
    if date_to:
        from datetime import timedelta
        filt.setdefault('created_at', {})['$lte'] = date_to_dt(date_to) + timedelta(days=1)

    order_docs = list(get_col('orders').find(filt).sort('created_at', -1))
    from app.models.marketplace import Order as Ord
    orders = [Ord(d) for d in order_docs]

    headers = [
        'N° commande', 'Date', 'Client', 'Téléphone', 'Adresse',
        'Statut', 'Paiement', 'Total (FCFA)', 'Notes',
    ]
    rows = [
        [
            o.order_number,
            o.created_at.strftime('%d/%m/%Y %H:%M') if o.created_at else '',
            o.customer_name,
            o.customer_phone,
            o.customer_address or '',
            o.status.value if hasattr(o.status, 'value') else o.status,
            o.payment_method.value if hasattr(o.payment_method, 'value') else o.payment_method,
            float(o.total_xaf),
            o.notes or '',
        ]
        for o in orders
    ]
    return _csv_response(rows, headers, 'commandes.csv')
