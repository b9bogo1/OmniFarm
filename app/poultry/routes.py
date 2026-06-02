import json
from types import SimpleNamespace
from flask import render_template, redirect, url_for, flash, abort
from flask_login import current_user
from flask_babel import gettext as _

from app.db import get_col
from app.models.poultry import Flock, PoultryRecord, FlockStatus
from app.auth.decorators import technician_required
from . import poultry_bp
from .forms import FlockForm, PoultryRecordForm


@poultry_bp.route('/')
@technician_required
def index():
    flocks = Flock.find_all()
    if flocks:
        flock_ids = [f.id for f in flocks]
        agg_rows = list(get_col('poultry_records').aggregate([
            {'$match': {'flock_id': {'$in': flock_ids}}},
            {'$group': {
                '_id':         '$flock_id',
                'cnt':         {'$sum': 1},
                'mort':        {'$sum': '$mortality_count'},
                'eggs':        {'$sum': '$eggs_collected'},
                'latest_date': {'$max': '$record_date'},
            }},
        ]))
        agg = {r['_id']: r for r in agg_rows}
        for f in flocks:
            a = agg.get(f.id)
            f._record_count   = a['cnt']  if a else 0
            f._total_mortality = a['mort'] if a else 0
            f._total_eggs     = a['eggs'] if a else 0
            f._latest_record  = (SimpleNamespace(record_date=a['latest_date'].date()
                                                  if a['latest_date'] else None)
                                  if a and a.get('latest_date') else None)
    return render_template('poultry/index.html', flocks=flocks, title=_('Aviculture'))


@poultry_bp.route('/flock/new', methods=['GET', 'POST'])
@technician_required
def create_flock():
    form = FlockForm()
    if form.validate_on_submit():
        flock = Flock(
            name=form.name.data.strip(),
            species=form.species.data.strip(),
            breed=form.breed.data or None,
            placement_date=form.placement_date.data,
            initial_count=form.initial_count.data,
            house_number=form.house_number.data or None,
            status=FlockStatus(form.status.data),
            notes=form.notes.data or None,
        )
        flock.save()
        flash(_('Lot « %(name)s » créé avec succès.', name=flock.name), 'success')
        return redirect(url_for('poultry.flock_detail', flock_id=flock.id))
    return render_template(
        'poultry/flock_form.html', form=form,
        title=_('Nouveau lot de volailles'), is_edit=False,
    )


@poultry_bp.route('/flock/<flock_id>/edit', methods=['GET', 'POST'])
@technician_required
def edit_flock(flock_id):
    flock = Flock.get_by_id(flock_id) or abort(404)
    form  = FlockForm(obj=flock)
    if form.validate_on_submit():
        flock.name           = form.name.data.strip()
        flock.species        = form.species.data.strip()
        flock.breed          = form.breed.data or None
        flock.placement_date = form.placement_date.data
        flock.initial_count  = form.initial_count.data
        flock.house_number   = form.house_number.data or None
        flock.status         = FlockStatus(form.status.data)
        flock.notes          = form.notes.data or None
        flock.save()
        flash(_('Lot « %(name)s » mis à jour.', name=flock.name), 'success')
        return redirect(url_for('poultry.flock_detail', flock_id=flock.id))
    form.status.data = flock.status.value
    return render_template(
        'poultry/flock_form.html', form=form, flock=flock,
        title=_('Modifier le lot'), is_edit=True,
    )


@poultry_bp.route('/flock/<flock_id>/delete', methods=['POST'])
@technician_required
def delete_flock(flock_id):
    flock = Flock.get_by_id(flock_id) or abort(404)
    name  = flock.name
    flock.delete()
    flash(_('Lot « %(name)s » et toutes ses données supprimés.', name=name), 'success')
    return redirect(url_for('poultry.index'))


@poultry_bp.route('/flock/<flock_id>')
@technician_required
def flock_detail(flock_id):
    flock   = Flock.get_by_id(flock_id) or abort(404)
    records = PoultryRecord.find_by_flock(flock_id, asc=True)

    chart_records = records[-20:] if len(records) > 20 else records
    chart_labels  = json.dumps([r.record_date.strftime('%d/%m') if r.record_date else '' for r in chart_records])
    chart_weights = json.dumps([float(r.avg_weight_g) if r.avg_weight_g is not None else None for r in chart_records])
    chart_mort    = json.dumps([r.mortality_count if r.mortality_count is not None else 0 for r in chart_records])
    chart_eggs    = json.dumps([r.eggs_collected if r.eggs_collected is not None else None for r in chart_records])
    chart_temp    = json.dumps([float(r.ambient_temp_c) if r.ambient_temp_c is not None else None for r in chart_records])

    return render_template(
        'poultry/detail.html', flock=flock, records=list(reversed(records)), title=flock.name,
        chart_labels=chart_labels, chart_weights=chart_weights, chart_mort=chart_mort,
        chart_eggs=chart_eggs, chart_temp=chart_temp,
    )


@poultry_bp.route('/flock/<flock_id>/record/new', methods=['GET', 'POST'])
@technician_required
def add_record(flock_id):
    flock = Flock.get_by_id(flock_id) or abort(404)
    form  = PoultryRecordForm()
    if form.validate_on_submit():
        rec = PoultryRecord(
            flock_id=flock.id,
            recorded_by_id=current_user.id,
            record_date=form.record_date.data,
            feed_quantity_kg=form.feed_quantity_kg.data,
            feed_type=form.feed_type.data or None,
            water_consumed_l=form.water_consumed_l.data,
            eggs_collected=form.eggs_collected.data or 0,
            avg_weight_g=form.avg_weight_g.data,
            mortality_count=form.mortality_count.data or 0,
            mortality_cause=form.mortality_cause.data or None,
            ambient_temp_c=form.ambient_temp_c.data,
            humidity_pct=form.humidity_pct.data,
            notes=form.notes.data or None,
        )
        rec.save()
        flash(_('Saisie du %(date)s enregistrée.',
                date=rec.record_date.strftime('%d/%m/%Y')), 'success')
        return redirect(url_for('poultry.flock_detail', flock_id=flock.id))
    return render_template(
        'poultry/record_form.html', form=form, flock=flock,
        title=_('Nouvelle saisie journalière'), is_edit=False,
    )


@poultry_bp.route('/record/<record_id>/edit', methods=['GET', 'POST'])
@technician_required
def edit_record(record_id):
    rec   = PoultryRecord.get_by_id(record_id) or abort(404)
    flock = Flock.get_by_id(rec.flock_id) or abort(404)
    form  = PoultryRecordForm(obj=rec)
    if form.validate_on_submit():
        form.populate_obj(rec)
        rec.mortality_count = rec.mortality_count or 0
        rec.eggs_collected  = rec.eggs_collected or 0
        rec.save()
        flash(_('Saisie mise à jour.'), 'success')
        return redirect(url_for('poultry.flock_detail', flock_id=flock.id))
    return render_template(
        'poultry/record_form.html', form=form, flock=flock, record=rec,
        title=_('Modifier la saisie'), is_edit=True,
    )


@poultry_bp.route('/record/<record_id>/delete', methods=['POST'])
@technician_required
def delete_record(record_id):
    rec      = PoultryRecord.get_by_id(record_id) or abort(404)
    flock_id = rec.flock_id
    rec.delete()
    flash(_('Enregistrement supprimé.'), 'success')
    return redirect(url_for('poultry.flock_detail', flock_id=flock_id))
