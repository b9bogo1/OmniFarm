import json
import time

from flask import render_template, jsonify, Response, stream_with_context
from flask_login import login_required, current_user
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


@iot_bp.route('/stream')
@login_required
@technician_required
def stream():
    """SSE endpoint — pushes live sensor snapshot every 8 seconds."""
    def _build_payload():
        from app.db import get_col
        scheduler = get_scheduler()
        ponds   = [p for p in Pond.find_all()        if p.status == PondStatus.ACTIVE]
        flocks  = [f for f in Flock.find_all()       if f.status == FlockStatus.ACTIVE]
        batches = [b for b in RabbitBatch.find_all() if b.status == RabbitStatus.ACTIVE]

        def _aqua(pond):
            doc = get_col('aquaculture_records').find_one(
                {'pond_id': pond.id}, sort=[('record_date', -1)]
            )
            if not doc:
                return None
            r = AquacultureRecord(doc)
            return {
                'pond_id':   pond.id,
                'name':      pond.name,
                'temp':      r.water_temp_c,
                'ph':        r.ph,
                'o2':        r.dissolved_oxygen_mgl,
                'turbidity': r.turbidity_ntu,
                'date':      r.date.strftime('%d/%m/%Y') if r.date else None,
            }

        def _poultry(flock):
            doc = get_col('poultry_records').find_one(
                {'flock_id': flock.id}, sort=[('record_date', -1)]
            )
            if not doc:
                return None
            r = PoultryRecord(doc)
            return {
                'flock_id': flock.id,
                'name':     flock.name,
                'temp':     r.ambient_temp_c,
                'humidity': r.humidity_pct,
                'date':     r.date.strftime('%d/%m/%Y') if r.date else None,
            }

        def _cuniculture(batch):
            doc = get_col('cuniculture_records').find_one(
                {'batch_id': batch.id}, sort=[('record_date', -1)]
            )
            if not doc:
                return None
            r = CunicultureRecord(doc)
            return {
                'batch_id': batch.id,
                'name':     batch.name,
                'temp':     r.ambient_temp_c,
                'date':     r.date.strftime('%d/%m/%Y') if r.date else None,
            }

        return {
            'scheduler': 'running' if (scheduler and scheduler.running) else 'stopped',
            'job_count': len(scheduler.get_jobs()) if (scheduler and scheduler.running) else 0,
            'aqua':      [x for x in (_aqua(p) for p in ponds)      if x],
            'poultry':   [x for x in (_poultry(f) for f in flocks)  if x],
            'cuniculture': [x for x in (_cuniculture(b) for b in batches) if x],
        }

    def generate():
        while True:
            try:
                payload = _build_payload()
                yield f"data: {json.dumps(payload)}\n\n"
            except Exception:
                yield "data: {}\n\n"
            time.sleep(8)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
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
