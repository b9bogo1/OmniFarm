import enum
from datetime import datetime, timezone
from app.db import get_col, oid, date_to_dt, dt_to_date


class HealthEventType(str, enum.Enum):
    VACCINATION = 'VACCINATION'
    TREATMENT   = 'TREATMENT'
    DEWORMING   = 'DEWORMING'
    INSPECTION  = 'INSPECTION'
    SURGERY     = 'SURGERY'


class HealthUnit(str, enum.Enum):
    AQUACULTURE = 'AQUACULTURE'
    POULTRY     = 'POULTRY'
    CUNICULTURE = 'CUNICULTURE'


EVENT_ICONS = {
    'VACCINATION': '💉',
    'TREATMENT':   '🩺',
    'DEWORMING':   '🔬',
    'INSPECTION':  '🔍',
    'SURGERY':     '⚕️',
}

UNIT_ICONS = {
    'AQUACULTURE': '🐟',
    'POULTRY':     '🐔',
    'CUNICULTURE': '🐇',
}


class HealthEvent:
    def __init__(self, doc=None, **kw):
        doc = {**(doc or {}), **kw}
        object.__setattr__(self, '_id', doc.get('_id'))
        _u = doc.get('production_unit', HealthUnit.POULTRY.value)
        self.production_unit = HealthUnit(_u) if isinstance(_u, str) else _u
        self.unit_ref_id     = doc.get('unit_ref_id')
        self.unit_name       = doc.get('unit_name', '')
        _et = doc.get('event_type', HealthEventType.INSPECTION.value)
        self.event_type      = HealthEventType(_et) if isinstance(_et, str) else _et
        self.event_date      = dt_to_date(doc.get('event_date'))
        self.product_used    = doc.get('product_used')
        self.dose            = doc.get('dose')
        self.administered_by = doc.get('administered_by')
        self.next_due_date   = dt_to_date(doc.get('next_due_date'))
        self.cost_xaf        = float(doc.get('cost_xaf')) if doc.get('cost_xaf') is not None else None
        self.notes           = doc.get('notes')
        self.recorded_by_id  = doc.get('recorded_by_id')
        self.created_at      = doc.get('created_at', datetime.now(timezone.utc))

    @property
    def id(self):
        return str(self._id) if self._id else None

    @property
    def cost_float(self) -> float:
        return float(self.cost_xaf) if self.cost_xaf is not None else 0.0

    def _val(self, field):
        return field.value if hasattr(field, 'value') else str(field)

    def event_type_label(self) -> str:
        from flask_babel import lazy_gettext as _l
        labels = {
            'VACCINATION': _l('Vaccination'),
            'TREATMENT':   _l('Traitement'),
            'DEWORMING':   _l('Déparasitage'),
            'INSPECTION':  _l('Inspection vétérinaire'),
            'SURGERY':     _l('Chirurgie'),
        }
        return str(labels.get(self._val(self.event_type), self._val(self.event_type)))

    def event_type_icon(self) -> str:
        return EVENT_ICONS.get(self._val(self.event_type), '🏥')

    def unit_label(self) -> str:
        from flask_babel import lazy_gettext as _l
        labels = {
            'AQUACULTURE': _l('Aquaculture'),
            'POULTRY':     _l('Aviculture'),
            'CUNICULTURE': _l('Cuniculture'),
        }
        return str(labels.get(self._val(self.production_unit), self._val(self.production_unit)))

    def unit_icon(self) -> str:
        return UNIT_ICONS.get(self._val(self.production_unit), '🐾')

    def save(self) -> 'HealthEvent':
        col = get_col('health_events')
        doc = self._to_doc()
        if self._id:
            col.replace_one({'_id': self._id}, doc)
        else:
            result = col.insert_one(doc)
            object.__setattr__(self, '_id', result.inserted_id)
        return self

    def delete(self) -> None:
        if self._id:
            get_col('health_events').delete_one({'_id': self._id})

    def _to_doc(self) -> dict:
        return {
            'production_unit': self._val(self.production_unit),
            'unit_ref_id':     self.unit_ref_id,
            'unit_name':       self.unit_name,
            'event_type':      self._val(self.event_type),
            'event_date':      date_to_dt(self.event_date),
            'product_used':    self.product_used,
            'dose':            self.dose,
            'administered_by': self.administered_by,
            'next_due_date':   date_to_dt(self.next_due_date),
            'cost_xaf':        float(self.cost_xaf) if self.cost_xaf is not None else None,
            'notes':           self.notes,
            'recorded_by_id':  self.recorded_by_id,
            'created_at':      self.created_at,
        }

    @classmethod
    def get_by_id(cls, id_str) -> 'HealthEvent | None':
        doc = get_col('health_events').find_one({'_id': oid(id_str)})
        return cls(doc) if doc else None

    @classmethod
    def find_filtered(cls, unit_filter='', type_filter='') -> list['HealthEvent']:
        filt: dict = {}
        if unit_filter in [u.value for u in HealthUnit]:
            filt['production_unit'] = unit_filter
        if type_filter in [t.value for t in HealthEventType]:
            filt['event_type'] = type_filter
        docs = list(get_col('health_events').find(filt).sort('event_date', -1))
        return [cls(d) for d in docs]

    @classmethod
    def find_upcoming(cls, from_date, limit: int = 5) -> list['HealthEvent']:
        from app.db import date_to_dt
        docs = list(
            get_col('health_events')
            .find({'next_due_date': {'$gte': date_to_dt(from_date), '$ne': None}})
            .sort('next_due_date', 1)
            .limit(limit)
        )
        return [cls(d) for d in docs]

    @classmethod
    def count_by_type(cls, event_type: HealthEventType) -> int:
        return get_col('health_events').count_documents({'event_type': event_type.value})

    @classmethod
    def count_all(cls) -> int:
        return get_col('health_events').count_documents({})
