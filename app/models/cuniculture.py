import enum
from datetime import datetime, date, timezone
from app.db import get_col, oid, date_to_dt, dt_to_date


class RabbitStatus(enum.Enum):
    ACTIVE   = 'active'
    SOLD     = 'sold'
    DECEASED = 'deceased'


class RabbitBatch:
    def __init__(self, doc=None, **kw):
        doc = {**(doc or {}), **kw}
        object.__setattr__(self, '_id', doc.get('_id'))
        self.name             = doc.get('name', '')
        self.breed            = doc.get('breed')
        self.acquisition_date = dt_to_date(doc.get('acquisition_date'))
        self.initial_count    = doc.get('initial_count', 0)
        self.female_count     = doc.get('female_count', 0)
        self.male_count       = doc.get('male_count', 0)
        _s = doc.get('status', RabbitStatus.ACTIVE.value)
        self.status = RabbitStatus(_s.lower()) if isinstance(_s, str) else _s
        self.notes            = doc.get('notes')
        self.created_at       = doc.get('created_at', datetime.now(timezone.utc))
        self._record_count    = None
        self._total_mortality = None
        self._total_kits_born = None
        self._latest_record   = None

    @property
    def id(self):
        return str(self._id) if self._id else None

    @property
    def age_days(self) -> int | None:
        return (date.today() - self.acquisition_date).days if self.acquisition_date else None

    @property
    def record_count(self) -> int:
        if self._record_count is not None:
            return self._record_count
        return get_col('cuniculture_records').count_documents({'batch_id': self.id})

    @property
    def total_mortality(self) -> int:
        if self._total_mortality is not None:
            return self._total_mortality
        result = list(get_col('cuniculture_records').aggregate([
            {'$match': {'batch_id': self.id}},
            {'$group': {'_id': None, 'total': {'$sum': '$mortality_count'}}},
        ]))
        return result[0]['total'] if result else 0

    @property
    def total_kits_born(self) -> int:
        if self._total_kits_born is not None:
            return self._total_kits_born
        result = list(get_col('cuniculture_records').aggregate([
            {'$match': {'batch_id': self.id}},
            {'$group': {'_id': None, 'total': {'$sum': '$kits_born'}}},
        ]))
        return result[0]['total'] if result else 0

    @property
    def latest_record(self):
        if self._latest_record is not None:
            return self._latest_record
        doc = get_col('cuniculture_records').find_one(
            {'batch_id': self.id}, sort=[('record_date', -1)]
        )
        return CunicultureRecord(doc) if doc else None

    def save(self) -> 'RabbitBatch':
        col = get_col('rabbit_batches')
        doc = self._to_doc()
        if self._id:
            col.replace_one({'_id': self._id}, doc)
        else:
            result = col.insert_one(doc)
            object.__setattr__(self, '_id', result.inserted_id)
        return self

    def delete(self) -> None:
        if self._id:
            get_col('rabbit_batches').delete_one({'_id': self._id})
            get_col('cuniculture_records').delete_many({'batch_id': self.id})

    def _to_doc(self) -> dict:
        return {
            'name':             self.name,
            'breed':            self.breed,
            'acquisition_date': date_to_dt(self.acquisition_date),
            'initial_count':    self.initial_count,
            'female_count':     self.female_count or 0,
            'male_count':       self.male_count or 0,
            'status':           self.status.value,
            'notes':            self.notes,
            'created_at':       self.created_at,
        }

    @classmethod
    def get_by_id(cls, id_str) -> 'RabbitBatch | None':
        doc = get_col('rabbit_batches').find_one({'_id': oid(id_str)})
        return cls(doc) if doc else None

    @classmethod
    def find_all(cls) -> list['RabbitBatch']:
        return [cls(d) for d in get_col('rabbit_batches').find().sort('created_at', -1)]

    @classmethod
    def count_by_status(cls, status: RabbitStatus) -> int:
        return get_col('rabbit_batches').count_documents({'status': status.value})

    def __repr__(self) -> str:
        return f'<RabbitBatch {self.name!r}>'


class CunicultureRecord:
    def __init__(self, doc=None, **kw):
        doc = {**(doc or {}), **kw}
        object.__setattr__(self, '_id', doc.get('_id'))
        self.batch_id         = doc.get('batch_id')
        self.recorded_by_id   = doc.get('recorded_by_id')
        self.record_date      = dt_to_date(doc.get('record_date'))
        self.feed_quantity_kg = doc.get('feed_quantity_kg')
        self.feed_type        = doc.get('feed_type')
        self.litters_born     = doc.get('litters_born', 0)
        self.kits_born        = doc.get('kits_born', 0)
        self.kits_survived    = doc.get('kits_survived', 0)
        self.avg_weight_g     = doc.get('avg_weight_g')
        self.mortality_count  = doc.get('mortality_count', 0)
        self.mortality_cause  = doc.get('mortality_cause')
        self.ambient_temp_c   = doc.get('ambient_temp_c')
        self.notes            = doc.get('notes')
        self.created_at       = doc.get('created_at', datetime.now(timezone.utc))

    @property
    def id(self):
        return str(self._id) if self._id else None

    @property
    def batch(self) -> 'RabbitBatch | None':
        return RabbitBatch.get_by_id(self.batch_id) if self.batch_id else None

    def save(self) -> 'CunicultureRecord':
        col = get_col('cuniculture_records')
        doc = self._to_doc()
        if self._id:
            col.replace_one({'_id': self._id}, doc)
        else:
            result = col.insert_one(doc)
            object.__setattr__(self, '_id', result.inserted_id)
        return self

    def delete(self) -> None:
        if self._id:
            get_col('cuniculture_records').delete_one({'_id': self._id})

    def _to_doc(self) -> dict:
        return {
            'batch_id':         self.batch_id,
            'recorded_by_id':   self.recorded_by_id,
            'record_date':      date_to_dt(self.record_date),
            'feed_quantity_kg': self.feed_quantity_kg,
            'feed_type':        self.feed_type,
            'litters_born':     self.litters_born or 0,
            'kits_born':        self.kits_born or 0,
            'kits_survived':    self.kits_survived or 0,
            'avg_weight_g':     self.avg_weight_g,
            'mortality_count':  self.mortality_count or 0,
            'mortality_cause':  self.mortality_cause,
            'ambient_temp_c':   self.ambient_temp_c,
            'notes':            self.notes,
            'created_at':       self.created_at,
        }

    @classmethod
    def get_by_id(cls, id_str) -> 'CunicultureRecord | None':
        doc = get_col('cuniculture_records').find_one({'_id': oid(id_str)})
        return cls(doc) if doc else None

    @classmethod
    def find_by_batch(cls, batch_id_str: str, asc=True) -> list['CunicultureRecord']:
        order = 1 if asc else -1
        docs = get_col('cuniculture_records').find(
            {'batch_id': batch_id_str}
        ).sort('record_date', order)
        return [cls(d) for d in docs]

    @classmethod
    def count_all(cls) -> int:
        return get_col('cuniculture_records').count_documents({})

    def __repr__(self) -> str:
        return f'<CunicultureRecord batch={self.batch_id} date={self.record_date}>'
