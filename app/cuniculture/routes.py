import json
from types import SimpleNamespace
from flask import render_template, redirect, url_for, flash, abort
from flask_login import current_user
from flask_babel import gettext as _

from app.db import get_col
from app.models.cuniculture import RabbitBatch, CunicultureRecord, RabbitStatus
from app.auth.decorators import technician_required
from . import cuniculture_bp
from .forms import RabbitBatchForm, CunicultureRecordForm


@cuniculture_bp.route('/')
@technician_required
def index():
    batches = RabbitBatch.find_all()
    if batches:
        batch_ids = [b.id for b in batches]
        agg_rows = list(get_col('cuniculture_records').aggregate([
            {'$match': {'batch_id': {'$in': batch_ids}}},
            {'$group': {
                '_id':         '$batch_id',
                'cnt':         {'$sum': 1},
                'mort':        {'$sum': '$mortality_count'},
                'kits':        {'$sum': '$kits_born'},
                'latest_date': {'$max': '$record_date'},
            }},
        ]))
        agg = {r['_id']: r for r in agg_rows}
        for b in batches:
            a = agg.get(b.id)
            b._record_count   = a['cnt']  if a else 0
            b._total_mortality = a['mort'] if a else 0
            b._total_kits_born = a['kits'] if a else 0
            b._latest_record  = (SimpleNamespace(record_date=a['latest_date'].date()
                                                   if a['latest_date'] else None)
                                  if a and a.get('latest_date') else None)
    return render_template('cuniculture/index.html', batches=batches, title=_('Cuniculture'))


@cuniculture_bp.route('/batch/new', methods=['GET', 'POST'])
@technician_required
def create_batch():
    form = RabbitBatchForm()
    if form.validate_on_submit():
        batch = RabbitBatch(
            name=form.name.data.strip(),
            breed=form.breed.data or None,
            acquisition_date=form.acquisition_date.data,
            initial_count=form.initial_count.data,
            female_count=form.female_count.data or 0,
            male_count=form.male_count.data or 0,
            status=RabbitStatus(form.status.data),
            notes=form.notes.data or None,
        )
        batch.save()
        flash(_('Lot « %(name)s » créé avec succès.', name=batch.name), 'success')
        return redirect(url_for('cuniculture.batch_detail', batch_id=batch.id))
    return render_template(
        'cuniculture/batch_form.html', form=form,
        title=_('Nouveau lot de lapins'), is_edit=False,
    )


@cuniculture_bp.route('/batch/<batch_id>/edit', methods=['GET', 'POST'])
@technician_required
def edit_batch(batch_id):
    batch = RabbitBatch.get_by_id(batch_id) or abort(404)
    form  = RabbitBatchForm(obj=batch)
    if form.validate_on_submit():
        batch.name             = form.name.data.strip()
        batch.breed            = form.breed.data or None
        batch.acquisition_date = form.acquisition_date.data
        batch.initial_count    = form.initial_count.data
        batch.female_count     = form.female_count.data or 0
        batch.male_count       = form.male_count.data or 0
        batch.status           = RabbitStatus(form.status.data)
        batch.notes            = form.notes.data or None
        batch.save()
        flash(_('Lot « %(name)s » mis à jour.', name=batch.name), 'success')
        return redirect(url_for('cuniculture.batch_detail', batch_id=batch.id))
    form.status.data = batch.status.value
    return render_template(
        'cuniculture/batch_form.html', form=form, batch=batch,
        title=_('Modifier le lot'), is_edit=True,
    )


@cuniculture_bp.route('/batch/<batch_id>/delete', methods=['POST'])
@technician_required
def delete_batch(batch_id):
    batch = RabbitBatch.get_by_id(batch_id) or abort(404)
    name  = batch.name
    batch.delete()
    flash(_('Lot « %(name)s » et toutes ses données supprimés.', name=name), 'success')
    return redirect(url_for('cuniculture.index'))


@cuniculture_bp.route('/batch/<batch_id>')
@technician_required
def batch_detail(batch_id):
    batch   = RabbitBatch.get_by_id(batch_id) or abort(404)
    records = CunicultureRecord.find_by_batch(batch_id, asc=True)

    chart_records = records[-20:] if len(records) > 20 else records
    chart_labels  = json.dumps([r.record_date.strftime('%d/%m') if r.record_date else '' for r in chart_records])
    chart_weights = json.dumps([float(r.avg_weight_g) if r.avg_weight_g is not None else None for r in chart_records])
    chart_mort    = json.dumps([r.mortality_count if r.mortality_count is not None else 0 for r in chart_records])
    chart_kits    = json.dumps([r.kits_born if r.kits_born is not None else None for r in chart_records])
    chart_temp    = json.dumps([float(r.ambient_temp_c) if r.ambient_temp_c is not None else None for r in chart_records])

    return render_template(
        'cuniculture/detail.html', batch=batch, records=list(reversed(records)), title=batch.name,
        chart_labels=chart_labels, chart_weights=chart_weights, chart_mort=chart_mort,
        chart_kits=chart_kits, chart_temp=chart_temp,
    )


@cuniculture_bp.route('/batch/<batch_id>/record/new', methods=['GET', 'POST'])
@technician_required
def add_record(batch_id):
    batch = RabbitBatch.get_by_id(batch_id) or abort(404)
    form  = CunicultureRecordForm()
    if form.validate_on_submit():
        rec = CunicultureRecord(
            batch_id=batch.id,
            recorded_by_id=current_user.id,
            record_date=form.record_date.data,
            feed_quantity_kg=form.feed_quantity_kg.data,
            feed_type=form.feed_type.data or None,
            litters_born=form.litters_born.data or 0,
            kits_born=form.kits_born.data or 0,
            kits_survived=form.kits_survived.data or 0,
            avg_weight_g=form.avg_weight_g.data,
            mortality_count=form.mortality_count.data or 0,
            mortality_cause=form.mortality_cause.data or None,
            ambient_temp_c=form.ambient_temp_c.data,
            notes=form.notes.data or None,
        )
        rec.save()
        flash(_('Saisie du %(date)s enregistrée.',
                date=rec.record_date.strftime('%d/%m/%Y')), 'success')
        return redirect(url_for('cuniculture.batch_detail', batch_id=batch.id))
    return render_template(
        'cuniculture/record_form.html', form=form, batch=batch,
        title=_('Nouvelle saisie journalière'), is_edit=False,
    )


@cuniculture_bp.route('/record/<record_id>/edit', methods=['GET', 'POST'])
@technician_required
def edit_record(record_id):
    rec   = CunicultureRecord.get_by_id(record_id) or abort(404)
    batch = RabbitBatch.get_by_id(rec.batch_id) or abort(404)
    form  = CunicultureRecordForm(obj=rec)
    if form.validate_on_submit():
        form.populate_obj(rec)
        rec.mortality_count = rec.mortality_count or 0
        rec.litters_born    = rec.litters_born or 0
        rec.kits_born       = rec.kits_born or 0
        rec.kits_survived   = rec.kits_survived or 0
        rec.save()
        flash(_('Saisie mise à jour.'), 'success')
        return redirect(url_for('cuniculture.batch_detail', batch_id=batch.id))
    return render_template(
        'cuniculture/record_form.html', form=form, batch=batch, record=rec,
        title=_('Modifier la saisie'), is_edit=True,
    )


@cuniculture_bp.route('/record/<record_id>/delete', methods=['POST'])
@technician_required
def delete_record(record_id):
    rec      = CunicultureRecord.get_by_id(record_id) or abort(404)
    batch_id = rec.batch_id
    rec.delete()
    flash(_('Enregistrement supprimé.'), 'success')
    return redirect(url_for('cuniculture.batch_detail', batch_id=batch_id))
