import enum
from datetime import datetime, timezone
from app.db import get_col, oid, date_to_dt, dt_to_date


class EntryType(str, enum.Enum):
    EXPENSE = 'EXPENSE'
    REVENUE = 'REVENUE'


class FinanceCategory(str, enum.Enum):
    FEED         = 'FEED'
    MEDICATION   = 'MEDICATION'
    EQUIPMENT    = 'EQUIPMENT'
    LABOR        = 'LABOR'
    UTILITIES    = 'UTILITIES'
    TRANSPORT    = 'TRANSPORT'
    MAINTENANCE  = 'MAINTENANCE'
    PRODUCT_SALE = 'PRODUCT_SALE'
    DIRECT_SALE  = 'DIRECT_SALE'
    SUBSIDY      = 'SUBSIDY'
    OTHER        = 'OTHER'


class ProductionScope(str, enum.Enum):
    AQUACULTURE = 'AQUACULTURE'
    POULTRY     = 'POULTRY'
    CUNICULTURE = 'CUNICULTURE'
    GENERAL     = 'GENERAL'


EXPENSE_CATEGORIES = [
    FinanceCategory.FEED, FinanceCategory.MEDICATION, FinanceCategory.EQUIPMENT,
    FinanceCategory.LABOR, FinanceCategory.UTILITIES, FinanceCategory.TRANSPORT,
    FinanceCategory.MAINTENANCE, FinanceCategory.OTHER,
]

REVENUE_CATEGORIES = [
    FinanceCategory.PRODUCT_SALE, FinanceCategory.DIRECT_SALE,
    FinanceCategory.SUBSIDY, FinanceCategory.OTHER,
]

CATEGORY_ICONS = {
    'FEED':         '🌾',
    'MEDICATION':   '💊',
    'EQUIPMENT':    '🔧',
    'LABOR':        '👷',
    'UTILITIES':    '⚡',
    'TRANSPORT':    '🚚',
    'MAINTENANCE':  '🛠️',
    'PRODUCT_SALE': '💰',
    'DIRECT_SALE':  '🏪',
    'SUBSIDY':      '🏛️',
    'OTHER':        '📌',
}


class FinanceEntry:
    def __init__(self, doc=None, **kw):
        doc = {**(doc or {}), **kw}
        object.__setattr__(self, '_id', doc.get('_id'))
        _t = doc.get('entry_type', EntryType.EXPENSE.value)
        self.entry_type = EntryType(_t) if isinstance(_t, str) else _t
        self.category         = doc.get('category', 'OTHER')
        self.description      = doc.get('description', '')
        self.amount_xaf       = float(doc.get('amount_xaf', 0))
        self.entry_date       = dt_to_date(doc.get('entry_date'))
        _sc = doc.get('production_scope', ProductionScope.GENERAL.value)
        self.production_scope = ProductionScope(_sc) if isinstance(_sc, str) else _sc
        self.payment_method   = doc.get('payment_method')
        self.reference_number = doc.get('reference_number')
        self.recorded_by_id   = doc.get('recorded_by_id')
        self.notes            = doc.get('notes')
        self.created_at       = doc.get('created_at', datetime.now(timezone.utc))

    @property
    def id(self):
        return str(self._id) if self._id else None

    @property
    def amount_float(self) -> float:
        return float(self.amount_xaf) if self.amount_xaf is not None else 0.0

    def category_label(self) -> str:
        from flask_babel import lazy_gettext as _l
        labels = {
            'FEED':         _l('Alimentation'),
            'MEDICATION':   _l('Médicaments'),
            'EQUIPMENT':    _l('Équipement'),
            'LABOR':        _l("Main d'œuvre"),
            'UTILITIES':    _l('Services publics'),
            'TRANSPORT':    _l('Transport'),
            'MAINTENANCE':  _l('Maintenance'),
            'PRODUCT_SALE': _l('Vente produit'),
            'DIRECT_SALE':  _l('Vente directe'),
            'SUBSIDY':      _l('Subvention'),
            'OTHER':        _l('Autre'),
        }
        return str(labels.get(self.category, self.category))

    def category_icon(self) -> str:
        return CATEGORY_ICONS.get(self.category, '📌')

    def scope_label(self) -> str:
        from flask_babel import lazy_gettext as _l
        labels = {
            'AQUACULTURE': _l('Aquaculture'),
            'POULTRY':     _l('Aviculture'),
            'CUNICULTURE': _l('Cuniculture'),
            'GENERAL':     _l('Général'),
        }
        val = self.production_scope.value if hasattr(self.production_scope, 'value') else str(self.production_scope)
        return str(labels.get(val, val))

    def save(self) -> 'FinanceEntry':
        col = get_col('finance_entries')
        doc = self._to_doc()
        if self._id:
            col.replace_one({'_id': self._id}, doc)
        else:
            result = col.insert_one(doc)
            object.__setattr__(self, '_id', result.inserted_id)
        return self

    def delete(self) -> None:
        if self._id:
            get_col('finance_entries').delete_one({'_id': self._id})

    def _to_doc(self) -> dict:
        return {
            'entry_type':       self.entry_type.value,
            'category':         self.category,
            'description':      self.description,
            'amount_xaf':       float(self.amount_xaf),
            'entry_date':       date_to_dt(self.entry_date),
            'production_scope': self.production_scope.value if hasattr(self.production_scope, 'value') else self.production_scope,
            'payment_method':   self.payment_method,
            'reference_number': self.reference_number,
            'recorded_by_id':   self.recorded_by_id,
            'notes':            self.notes,
            'created_at':       self.created_at,
        }

    @classmethod
    def get_by_id(cls, id_str) -> 'FinanceEntry | None':
        doc = get_col('finance_entries').find_one({'_id': oid(id_str)})
        return cls(doc) if doc else None

    @classmethod
    def find_filtered(cls, type_filter='', scope_filter='', month_filter='') -> list['FinanceEntry']:
        filt: dict = {}
        if type_filter in (EntryType.EXPENSE.value, EntryType.REVENUE.value):
            filt['entry_type'] = type_filter
        if scope_filter in [s.value for s in ProductionScope]:
            filt['production_scope'] = scope_filter
        if month_filter:
            try:
                y, m = int(month_filter[:4]), int(month_filter[5:7])
                from datetime import datetime as dt2
                start = dt2(y, m, 1, tzinfo=timezone.utc)
                if m == 12:
                    end = dt2(y + 1, 1, 1, tzinfo=timezone.utc)
                else:
                    end = dt2(y, m + 1, 1, tzinfo=timezone.utc)
                filt['entry_date'] = {'$gte': start, '$lt': end}
            except (ValueError, IndexError):
                pass
        docs = list(get_col('finance_entries').find(filt).sort('entry_date', -1))
        return [cls(d) for d in docs]

    @classmethod
    def monthly_totals(cls) -> list:
        pipeline = [
            {'$group': {
                '_id': {
                    'yr':   {'$year': '$entry_date'},
                    'mo':   {'$month': '$entry_date'},
                    'type': '$entry_type',
                },
                'total': {'$sum': '$amount_xaf'},
            }}
        ]
        return list(get_col('finance_entries').aggregate(pipeline))

    @classmethod
    def summary_by_scope_and_type(cls) -> list:
        pipeline = [
            {'$group': {
                '_id': {
                    'scope': '$production_scope',
                    'type':  '$entry_type',
                },
                'total': {'$sum': '$amount_xaf'},
            }}
        ]
        return list(get_col('finance_entries').aggregate(pipeline))

    @classmethod
    def summary_by_category(cls) -> list:
        pipeline = [
            {'$group': {
                '_id': {
                    'category': '$category',
                    'type':     '$entry_type',
                },
                'total': {'$sum': '$amount_xaf'},
            }},
            {'$sort': {'total': -1}},
        ]
        return list(get_col('finance_entries').aggregate(pipeline))

    @classmethod
    def count_all(cls) -> int:
        return get_col('finance_entries').count_documents({})
