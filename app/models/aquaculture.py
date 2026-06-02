import enum
from datetime import datetime, date, timezone
from app.db import get_col, oid, date_to_dt, dt_to_date


class PondStatus(enum.Enum):
    ACTIVE      = 'active'
    INACTIVE    = 'inactive'
    MAINTENANCE = 'maintenance'
    HARVESTED   = 'harvested'


class Pond:
    def __init__(self, doc=None, **kw):
        doc = {**(doc or {}), **kw}
        object.__setattr__(self, '_id', doc.get('_id'))
        self.name              = doc.get('name', '')
        self.species           = doc.get('species', '')
        self.capacity_m3       = doc.get('capacity_m3')
        _s = doc.get('status', PondStatus.ACTIVE.value)
        self.status = PondStatus(_s) if isinstance(_s, str) else _s
        self.installation_date = dt_to_date(doc.get('installation_date'))
        self.notes             = doc.get('notes')
        self.created_at        = doc.get('created_at', datetime.now(timezone.utc))
        # Cached aggregates injected by index route
        self._record_count   = None
        self._total_mortality = None
        self._latest_record  = None

    @property
    def id(self):
        return str(self._id) if self._id else None

    # ── Computed properties ──────────────────────────────────────────────────

    @property
    def record_count(self) -> int:
        if self._record_count is not None:
            return self._record_count
        return get_col('aquaculture_records').count_documents({'pond_id': self.id})

    @property
    def total_mortality(self) -> int:
        if self._total_mortality is not None:
            return self._total_mortality
        result = list(get_col('aquaculture_records').aggregate([
            {'$match': {'pond_id': self.id}},
            {'$group': {'_id': None, 'total': {'$sum': '$mortality_count'}}},
        ]))
        return result[0]['total'] if result else 0

    @property
    def latest_record(self):
        if self._latest_record is not None:
            return self._latest_record
        doc = get_col('aquaculture_records').find_one(
            {'pond_id': self.id}, sort=[('record_date', -1)]
        )
        return AquacultureRecord(doc) if doc else None

    # ── Persistence ──────────────────────────────────────────────────────────

    def save(self) -> 'Pond':
        col = get_col('ponds')
        doc = self._to_doc()
        if self._id:
            col.replace_one({'_id': self._id}, doc)
        else:
            result = col.insert_one(doc)
            object.__setattr__(self, '_id', result.inserted_id)
        return self

    def delete(self) -> None:
        if self._id:
            get_col('ponds').delete_one({'_id': self._id})
            get_col('aquaculture_records').delete_many({'pond_id': self.id})

    def _to_doc(self) -> dict:
        return {
            'name':              self.name,
            'species':           self.species,
            'capacity_m3':       self.capacity_m3,
            'status':            self.status.value,
            'installation_date': date_to_dt(self.installation_date),
            'notes':             self.notes,
            'created_at':        self.created_at,
        }

    # ── Class-level queries ──────────────────────────────────────────────────

    @classmethod
    def get_by_id(cls, id_str) -> 'Pond | None':
        doc = get_col('ponds').find_one({'_id': oid(id_str)})
        return cls(doc) if doc else None

    @classmethod
    def find_all(cls) -> list['Pond']:
        return [cls(d) for d in get_col('ponds').find().sort('created_at', -1)]

    @classmethod
    def count_by_status(cls, status: PondStatus) -> int:
        return get_col('ponds').count_documents({'status': status.value})

    def __repr__(self) -> str:
        return f'<Pond {self.name!r}>'


class AquacultureRecord:
    def __init__(self, doc=None, **kw):
        doc = {**(doc or {}), **kw}
        object.__setattr__(self, '_id', doc.get('_id'))
        self.pond_id            = doc.get('pond_id')     # str of Pond._id
        self.recorded_by_id     = doc.get('recorded_by_id')
        self.record_date        = dt_to_date(doc.get('record_date'))
        self.current_count      = doc.get('current_count')
        self.avg_weight_g       = doc.get('avg_weight_g')
        self.feed_quantity_kg   = doc.get('feed_quantity_kg')
        self.feed_type          = doc.get('feed_type')
        self.mortality_count    = doc.get('mortality_count', 0)
        self.mortality_cause    = doc.get('mortality_cause')
        self.water_temp_c       = doc.get('water_temp_c')
        self.ph                 = doc.get('ph')
        self.dissolved_oxygen_mgl = doc.get('dissolved_oxygen_mgl')
        self.turbidity_ntu      = doc.get('turbidity_ntu')
        self.notes              = doc.get('notes')
        self.created_at         = doc.get('created_at', datetime.now(timezone.utc))

    @property
    def id(self):
        return str(self._id) if self._id else None

    @property
    def pond(self) -> 'Pond | None':
        return Pond.get_by_id(self.pond_id) if self.pond_id else None

    def save(self) -> 'AquacultureRecord':
        col = get_col('aquaculture_records')
        doc = self._to_doc()
        if self._id:
            col.replace_one({'_id': self._id}, doc)
        else:
            result = col.insert_one(doc)
            object.__setattr__(self, '_id', result.inserted_id)
        return self

    def delete(self) -> None:
        if self._id:
            get_col('aquaculture_records').delete_one({'_id': self._id})

    def _to_doc(self) -> dict:
        return {
            'pond_id':              self.pond_id,
            'recorded_by_id':       self.recorded_by_id,
            'record_date':          date_to_dt(self.record_date),
            'current_count':        self.current_count,
            'avg_weight_g':         self.avg_weight_g,
            'feed_quantity_kg':     self.feed_quantity_kg,
            'feed_type':            self.feed_type,
            'mortality_count':      self.mortality_count or 0,
            'mortality_cause':      self.mortality_cause,
            'water_temp_c':         self.water_temp_c,
            'ph':                   self.ph,
            'dissolved_oxygen_mgl': self.dissolved_oxygen_mgl,
            'turbidity_ntu':        self.turbidity_ntu,
            'notes':                self.notes,
            'created_at':           self.created_at,
        }

    @classmethod
    def get_by_id(cls, id_str) -> 'AquacultureRecord | None':
        doc = get_col('aquaculture_records').find_one({'_id': oid(id_str)})
        return cls(doc) if doc else None

    @classmethod
    def find_by_pond(cls, pond_id_str: str, asc=True) -> list['AquacultureRecord']:
        order = 1 if asc else -1
        docs = get_col('aquaculture_records').find(
            {'pond_id': pond_id_str}
        ).sort('record_date', order)
        return [cls(d) for d in docs]

    @classmethod
    def count_all(cls) -> int:
        return get_col('aquaculture_records').count_documents({})

    def __repr__(self) -> str:
        return f'<AquacultureRecord pond={self.pond_id} date={self.record_date}>'
