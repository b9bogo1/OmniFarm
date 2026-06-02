import json
from datetime import date
from types import SimpleNamespace
from flask import render_template, redirect, url_for, flash, abort
from flask_login import current_user
from flask_babel import gettext as _

from app.db import get_col
from app.models.aquaculture import Pond, AquacultureRecord, PondStatus
from app.auth.decorators import technician_required
from . import aquaculture_bp
from .forms import PondForm, AquacultureRecordForm


# ── Pond index ──────────────────────────────────────────────────────────────

@aquaculture_bp.route('/')
@technician_required
def index():
    ponds = Pond.find_all()
    if ponds:
        pond_ids = [p.id for p in ponds]
        agg_rows = list(get_col('aquaculture_records').aggregate([
            {'$match': {'pond_id': {'$in': pond_ids}}},
            {'$group': {
                '_id':         '$pond_id',
                'cnt':         {'$sum': 1},
                'mort':        {'$sum': '$mortality_count'},
                'latest_date': {'$max': '$record_date'},
            }},
        ]))
        agg = {r['_id']: r for r in agg_rows}
        for p in ponds:
            a = agg.get(p.id)
            p._record_count   = a['cnt']  if a else 0
            p._total_mortality = a['mort'] if a else 0
            p._latest_record  = (SimpleNamespace(record_date=a['latest_date'].date()
                                                  if a['latest_date'] else None)
                                  if a and a.get('latest_date') else None)
    return render_template('aquaculture/index.html', ponds=ponds, title=_('Aquaculture'))


# ── Create / Edit Pond ───────────────────────────────────────────────────────

@aquaculture_bp.route('/pond/new', methods=['GET', 'POST'])
@technician_required
def create_pond():
    form = PondForm()
    if form.validate_on_submit():
        pond = Pond(
            name=form.name.data.strip(),
            species=form.species.data.strip(),
            capacity_m3=form.capacity_m3.data,
            status=PondStatus(form.status.data),
            installation_date=form.installation_date.data,
            notes=form.notes.data or None,
        )
        pond.save()
        flash(_('Bassin « %(name)s » créé avec succès.', name=pond.name), 'success')
        return redirect(url_for('aquaculture.pond_detail', pond_id=pond.id))
    return render_template(
        'aquaculture/pond_form.html', form=form,
        title=_('Nouveau bassin'), is_edit=False,
    )


@aquaculture_bp.route('/pond/<pond_id>/edit', methods=['GET', 'POST'])
@technician_required
def edit_pond(pond_id):
    pond = Pond.get_by_id(pond_id) or abort(404)
    form = PondForm(obj=pond)
    if form.validate_on_submit():
        pond.name              = form.name.data.strip()
        pond.species           = form.species.data.strip()
        pond.capacity_m3       = form.capacity_m3.data
        pond.status            = PondStatus(form.status.data)
        pond.installation_date = form.installation_date.data
        pond.notes             = form.notes.data or None
        pond.save()
        flash(_('Bassin « %(name)s » mis à jour.', name=pond.name), 'success')
        return redirect(url_for('aquaculture.pond_detail', pond_id=pond.id))
    form.status.data = pond.status.value
    return render_template(
        'aquaculture/pond_form.html', form=form, pond=pond,
        title=_('Modifier le bassin'), is_edit=True,
    )


@aquaculture_bp.route('/pond/<pond_id>/delete', methods=['POST'])
@technician_required
def delete_pond(pond_id):
    pond = Pond.get_by_id(pond_id) or abort(404)
    name = pond.name
    pond.delete()
    flash(_('Bassin « %(name)s » et toutes ses données supprimés.', name=name), 'success')
    return redirect(url_for('aquaculture.index'))


# ── Pond detail ──────────────────────────────────────────────────────────────

@aquaculture_bp.route('/pond/<pond_id>')
@technician_required
def pond_detail(pond_id):
    pond    = Pond.get_by_id(pond_id) or abort(404)
    records = AquacultureRecord.find_by_pond(pond_id, asc=True)

    chart_records = records[-20:] if len(records) > 20 else records
    chart_labels  = json.dumps([r.record_date.strftime('%d/%m') if r.record_date else '' for r in chart_records])
    chart_counts  = json.dumps([r.current_count   if r.current_count   is not None else None for r in chart_records])
    chart_weights = json.dumps([float(r.avg_weight_g) if r.avg_weight_g is not None else None for r in chart_records])
    chart_mort    = json.dumps([r.mortality_count  if r.mortality_count  is not None else 0    for r in chart_records])
    chart_temp    = json.dumps([float(r.water_temp_c) if r.water_temp_c is not None else None for r in chart_records])

    return render_template(
        'aquaculture/detail.html',
        pond=pond,
        records=list(reversed(records)),
        chart_labels=chart_labels,
        chart_counts=chart_counts,
        chart_weights=chart_weights,
        chart_mort=chart_mort,
        chart_temp=chart_temp,
        title=pond.name,
    )


# ── Records ──────────────────────────────────────────────────────────────────

@aquaculture_bp.route('/pond/<pond_id>/record/new', methods=['GET', 'POST'])
@technician_required
def add_record(pond_id):
    pond = Pond.get_by_id(pond_id) or abort(404)
    form = AquacultureRecordForm()
    if form.validate_on_submit():
        rec = AquacultureRecord(
            pond_id=pond.id,
            recorded_by_id=current_user.id,
            record_date=form.record_date.data,
            current_count=form.current_count.data,
            avg_weight_g=form.avg_weight_g.data,
            feed_quantity_kg=form.feed_quantity_kg.data,
            feed_type=form.feed_type.data or None,
            mortality_count=form.mortality_count.data or 0,
            mortality_cause=form.mortality_cause.data or None,
            water_temp_c=form.water_temp_c.data,
            ph=form.ph.data,
            dissolved_oxygen_mgl=form.dissolved_oxygen_mgl.data,
            turbidity_ntu=form.turbidity_ntu.data,
            notes=form.notes.data or None,
        )
        rec.save()
        flash(_('Saisie du %(date)s enregistrée.',
                date=rec.record_date.strftime('%d/%m/%Y')), 'success')
        return redirect(url_for('aquaculture.pond_detail', pond_id=pond.id))
    return render_template(
        'aquaculture/record_form.html', form=form, pond=pond,
        title=_('Nouvelle saisie journalière'), is_edit=False,
    )


@aquaculture_bp.route('/record/<record_id>/edit', methods=['GET', 'POST'])
@technician_required
def edit_record(record_id):
    rec  = AquacultureRecord.get_by_id(record_id) or abort(404)
    pond = Pond.get_by_id(rec.pond_id) or abort(404)
    form = AquacultureRecordForm(obj=rec)
    if form.validate_on_submit():
        form.populate_obj(rec)
        rec.mortality_count = rec.mortality_count or 0
        rec.save()
        flash(_('Saisie mise à jour.'), 'success')
        return redirect(url_for('aquaculture.pond_detail', pond_id=pond.id))
    return render_template(
        'aquaculture/record_form.html', form=form, pond=pond, record=rec,
        title=_('Modifier la saisie'), is_edit=True,
    )


@aquaculture_bp.route('/record/<record_id>/delete', methods=['POST'])
@technician_required
def delete_record(record_id):
    rec     = AquacultureRecord.get_by_id(record_id) or abort(404)
    pond_id = rec.pond_id
    rec.delete()
    flash(_('Enregistrement supprimé.'), 'success')
    return redirect(url_for('aquaculture.pond_detail', pond_id=pond_id))
