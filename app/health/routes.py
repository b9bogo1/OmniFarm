from datetime import date
from flask import render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import current_user
from flask_babel import gettext as _

from app.models.health import HealthEvent, HealthEventType, HealthUnit
from app.models.aquaculture import Pond
from app.models.poultry import Flock
from app.models.cuniculture import RabbitBatch
from app.auth.decorators import technician_required
from . import health_bp
from .forms import HealthEventForm


def _get_unit_choices(unit_value):
    if unit_value == HealthUnit.AQUACULTURE.value:
        docs = sorted(Pond.find_all(), key=lambda x: x.name)
        return [(p.id, p.name) for p in docs]
    if unit_value == HealthUnit.POULTRY.value:
        docs = sorted(Flock.find_all(), key=lambda x: x.name)
        return [(f.id, f.name) for f in docs]
    if unit_value == HealthUnit.CUNICULTURE.value:
        docs = sorted(RabbitBatch.find_all(), key=lambda x: x.name)
        return [(b.id, b.name) for b in docs]
    return []


def _get_unit_name(unit_value, ref_id):
    if unit_value == HealthUnit.AQUACULTURE.value:
        obj = Pond.get_by_id(ref_id)
    elif unit_value == HealthUnit.POULTRY.value:
        obj = Flock.get_by_id(ref_id)
    elif unit_value == HealthUnit.CUNICULTURE.value:
        obj = RabbitBatch.get_by_id(ref_id)
    else:
        obj = None
    return obj.name if obj else str(ref_id)


@health_bp.route('/')
@technician_required
def index():
    unit_filter = request.args.get('unit', '')
    type_filter = request.args.get('type', '')

    events   = HealthEvent.find_filtered(unit_filter, type_filter)
    upcoming = HealthEvent.find_upcoming(from_date=date.today(), limit=5)

    type_counts = {etype.value: HealthEvent.count_by_type(etype)
                   for etype in HealthEventType}

    return render_template(
        'health/index.html',
        events=events,
        upcoming=upcoming,
        unit_filter=unit_filter,
        type_filter=type_filter,
        type_counts=type_counts,
        today=date.today(),
        title=_('Santé animale'),
    )


@health_bp.route('/event/new', methods=['GET', 'POST'])
@technician_required
def create_event():
    form = HealthEventForm()
    selected_unit = request.form.get('production_unit') or HealthUnit.POULTRY.value
    form.unit_ref_id.choices = _get_unit_choices(selected_unit) or [(0, _('— aucun —'))]

    if form.validate_on_submit():
        unit_val = form.production_unit.data
        ref_id   = form.unit_ref_id.data
        event = HealthEvent(
            production_unit=HealthUnit(unit_val),
            unit_ref_id=ref_id,
            unit_name=_get_unit_name(unit_val, ref_id),
            event_type=HealthEventType(form.event_type.data),
            event_date=form.event_date.data,
            product_used=form.product_used.data or None,
            dose=form.dose.data or None,
            administered_by=form.administered_by.data or None,
            next_due_date=form.next_due_date.data or None,
            cost_xaf=form.cost_xaf.data if form.cost_xaf.data else None,
            notes=form.notes.data or None,
            recorded_by_id=current_user.id,
        )
        event.save()
        flash(_('Événement de santé enregistré.'), 'success')
        return redirect(url_for('health.index'))

    form.event_date.data = form.event_date.data or date.today()
    return render_template(
        'health/form.html', form=form,
        title=_('Nouvel événement de santé'), is_edit=False,
        selected_unit=selected_unit,
    )


@health_bp.route('/event/<event_id>/edit', methods=['GET', 'POST'])
@technician_required
def edit_event(event_id):
    event = HealthEvent.get_by_id(event_id) or abort(404)
    form  = HealthEventForm(obj=event)
    selected_unit = request.form.get('production_unit') or event.production_unit.value
    form.unit_ref_id.choices = _get_unit_choices(selected_unit) or [(0, _('— aucun —'))]

    if form.validate_on_submit():
        unit_val = form.production_unit.data
        ref_id   = form.unit_ref_id.data
        event.production_unit = HealthUnit(unit_val)
        event.unit_ref_id     = ref_id
        event.unit_name       = _get_unit_name(unit_val, ref_id)
        event.event_type      = HealthEventType(form.event_type.data)
        event.event_date      = form.event_date.data
        event.product_used    = form.product_used.data or None
        event.dose            = form.dose.data or None
        event.administered_by = form.administered_by.data or None
        event.next_due_date   = form.next_due_date.data or None
        event.cost_xaf        = form.cost_xaf.data if form.cost_xaf.data else None
        event.notes           = form.notes.data or None
        event.save()
        flash(_('Événement mis à jour.'), 'success')
        return redirect(url_for('health.index'))

    form.production_unit.data = event.production_unit.value
    form.event_type.data      = event.event_type.value
    form.unit_ref_id.data     = event.unit_ref_id
    return render_template(
        'health/form.html', form=form, event=event,
        title=_('Modifier l\'événement'), is_edit=True,
        selected_unit=selected_unit,
    )


@health_bp.route('/event/<event_id>/delete', methods=['POST'])
@technician_required
def delete_event(event_id):
    event = HealthEvent.get_by_id(event_id) or abort(404)
    event.delete()
    flash(_('Événement supprimé.'), 'success')
    return redirect(url_for('health.index'))


@health_bp.route('/api/unit-choices')
@technician_required
def api_unit_choices():
    unit    = request.args.get('unit', '')
    choices = _get_unit_choices(unit)
    return jsonify([{'id': c[0], 'name': c[1]} for c in choices])
