"""
IoT Sensor Readers — ModBus TCP + EtherNet-IP stubs.
DB layer now uses MongoDB via app.db.get_col instead of SQLAlchemy.
"""
import logging
from datetime import datetime, timezone

_log = logging.getLogger(__name__)


def _read_aqua_modbus(host: str) -> dict:
    _log.debug('[IoT:STUB] ModBus aquaculture read from %s', host)
    return {
        'water_temp_c': 27.4,
        'ph': 7.2,
        'dissolved_oxygen_mgl': 6.5,
        'turbidity_ntu': 12.0,
    }


def _read_climate_modbus(host: str) -> dict:
    _log.debug('[IoT:STUB] ModBus climate read from %s', host)
    return {
        'ambient_temp_c': 29.1,
        'humidity_pct': 68.0,
    }


def poll_aquaculture(app) -> None:
    with app.app_context():
        from app.models.aquaculture import Pond, PondStatus

        ponds = [p for p in Pond.find_all() if p.status == PondStatus.ACTIVE]
        if not ponds:
            _log.debug('[IoT:aqua] No active ponds — skipping poll.')
            return

        for pond in ponds:
            host = app.config.get('MODBUS_AQUA_HOST', '127.0.0.1')
            try:
                data = _read_aqua_modbus(host)
                _log.info(
                    '[IoT:aqua] Pond "%s" — T=%.1f°C pH=%.2f DO=%.2f mg/L Turb=%.0f NTU',
                    pond.name,
                    data['water_temp_c'], data['ph'],
                    data['dissolved_oxygen_mgl'], data['turbidity_ntu'],
                )
                # Production: uncomment to persist sensor readings automatically
                # from app.models.aquaculture import AquacultureRecord
                # from datetime import date
                # rec = AquacultureRecord(
                #     pond_id=pond.id,
                #     record_date=date.today(),
                #     water_temp_c=data['water_temp_c'],
                #     ph=data['ph'],
                #     dissolved_oxygen_mgl=data['dissolved_oxygen_mgl'],
                #     turbidity_ntu=data['turbidity_ntu'],
                #     notes='[auto IoT]',
                # )
                # rec.save()
            except Exception as exc:
                _log.error('[IoT:aqua] Pond "%s" read failed: %s', pond.name, exc)


def poll_poultry(app) -> None:
    with app.app_context():
        from app.models.poultry import Flock, FlockStatus

        flocks = [f for f in Flock.find_all() if f.status == FlockStatus.ACTIVE]
        if not flocks:
            _log.debug('[IoT:poultry] No active flocks — skipping poll.')
            return

        host = app.config.get('MODBUS_CLIMATE_HOST', '127.0.0.1')
        for flock in flocks:
            try:
                data = _read_climate_modbus(host)
                _log.info('[IoT:poultry] Flock "%s" — T=%.1f°C RH=%.0f%%',
                          flock.name, data['ambient_temp_c'], data['humidity_pct'])
            except Exception as exc:
                _log.error('[IoT:poultry] Flock "%s" read failed: %s', flock.name, exc)


def poll_cuniculture(app) -> None:
    with app.app_context():
        from app.models.cuniculture import RabbitBatch, RabbitStatus

        batches = [b for b in RabbitBatch.find_all() if b.status == RabbitStatus.ACTIVE]
        if not batches:
            _log.debug('[IoT:cuniculture] No active batches — skipping poll.')
            return

        host = app.config.get('MODBUS_CLIMATE_HOST', '127.0.0.1')
        for batch in batches:
            try:
                data = _read_climate_modbus(host)
                _log.info('[IoT:cuniculture] Batch "%s" — T=%.1f°C RH=%.0f%%',
                          batch.name, data['ambient_temp_c'], data['humidity_pct'])
            except Exception as exc:
                _log.error('[IoT:cuniculture] Batch "%s" read failed: %s', batch.name, exc)
