from flask import render_template, jsonify
from flask_login import login_required
from flask_babel import gettext as _

from . import iot_bp
from .scheduler import get_scheduler
from ..auth.decorators import technician_required
from ..models.aquaculture import Pond, PondStatus, AquacultureRecord
from ..models.poultry import Flock, FlockStatus, PoultryRecord
from ..models.cuniculture import RabbitBatch, RabbitStatus, CunicultureRecord


@iot_bp.route('/')
@login_required
@technician_required
def dashboard():
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

    ponds   = [p for p in Pond.find_all()        if p.status == PondStatus.ACTIVE]
    flocks  = [f for f in Flock.find_all()       if f.status == FlockStatus.ACTIVE]
    batches = [b for b in RabbitBatch.find_all() if b.status == RabbitStatus.ACTIVE]

    latest_aqua = {}
    for pond in ponds:
        from app.db import get_col
        doc = get_col('aquaculture_records').find_one(
            {'pond_id': pond.id}, sort=[('record_date', -1)]
        )
        latest_aqua[pond.id] = AquacultureRecord(doc) if doc else None

    latest_poultry = {}
    for flock in flocks:
        from app.db import get_col
        doc = get_col('poultry_records').find_one(
            {'flock_id': flock.id}, sort=[('record_date', -1)]
        )
        latest_poultry[flock.id] = PoultryRecord(doc) if doc else None

    latest_cuniculture = {}
    for batch in batches:
        from app.db import get_col
        doc = get_col('cuniculture_records').find_one(
            {'batch_id': batch.id}, sort=[('record_date', -1)]
        )
        latest_cuniculture[batch.id] = CunicultureRecord(doc) if doc else None

    return render_template(
        'iot/dashboard.html',
        title=_('IoT & Télémétrie'),
        scheduler_running=scheduler.running if scheduler else False,
        jobs=jobs,
        ponds=ponds,
        flocks=flocks,
        batches=batches,
        latest_aqua=latest_aqua,
        latest_poultry=latest_poultry,
        latest_cuniculture=latest_cuniculture,
    )


@iot_bp.route('/api/status')
@login_required
@technician_required
def api_status():
    scheduler  = get_scheduler()
    jobs_data  = []
    if scheduler and scheduler.running:
        jobs_data = [
            {
                'id':       j.id,
                'name':     j.name,
                'next_run': j.next_run_time.isoformat() if j.next_run_time else None,
            }
            for j in scheduler.get_jobs()
        ]
    return jsonify({
        'scheduler': 'running' if (scheduler and scheduler.running) else 'stopped',
        'jobs': jobs_data,
    })
