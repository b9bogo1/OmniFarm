"""
APScheduler setup for OmniFarm IoT background polling.

Guard against double-start with Werkzeug reloader: only starts in the
main process (WERKZEUG_RUN_MAIN=true when debug=True) or in production.
"""
import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

_log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler


def init_scheduler(app) -> None:
    global _scheduler

    if app.testing:
        _log.debug('IoT scheduler: skipping start (testing mode).')
        return

    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        _log.debug('IoT scheduler: skipping start (Werkzeug reloader child process).')
        return

    jobstores = {'default': MemoryJobStore()}
    executors = {'default': ThreadPoolExecutor(max_workers=4)}

    _scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        timezone='Africa/Douala',
        job_defaults={'coalesce': True, 'max_instances': 1},
    )

    from .readers import poll_aquaculture, poll_poultry, poll_cuniculture

    _scheduler.add_job(
        func=poll_aquaculture,
        args=[app],
        trigger='interval',
        minutes=app.config.get('IOT_POLL_INTERVAL_MINUTES', 5),
        id='iot_aquaculture',
        name='Aquaculture sensor poll (ModBus TCP)',
        replace_existing=True,
    )
    _scheduler.add_job(
        func=poll_poultry,
        args=[app],
        trigger='interval',
        minutes=app.config.get('IOT_POLL_INTERVAL_MINUTES', 5),
        id='iot_poultry',
        name='Poultry climate sensor poll',
        replace_existing=True,
    )
    _scheduler.add_job(
        func=poll_cuniculture,
        args=[app],
        trigger='interval',
        minutes=app.config.get('IOT_POLL_INTERVAL_MINUTES', 5),
        id='iot_cuniculture',
        name='Cuniculture climate sensor poll',
        replace_existing=True,
    )

    _scheduler.start()
    _log.info(
        'IoT scheduler started — %d jobs registered (interval: %d min)',
        len(_scheduler.get_jobs()),
        app.config.get('IOT_POLL_INTERVAL_MINUTES', 5),
    )
