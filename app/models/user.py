import enum
from datetime import datetime, timezone
from flask_login import UserMixin
from app.extensions import bcrypt


class UserRole(enum.Enum):
    ADMIN = 'admin'
    TECHNICIAN = 'technician'
    CLIENT = 'client'


class User(UserMixin):
    """MongoDB-backed user.  Wraps a document dict; no ORM."""

    def __init__(self, doc=None, **kw):
        doc = {**(doc or {}), **kw}
        object.__setattr__(self, '_id', doc.get('_id'))
        self.username   = doc.get('username', '')
        self.email      = doc.get('email', '')
        self.password_hash = doc.get('password_hash', '')
        _role = doc.get('role', UserRole.CLIENT.value)
        self.role = UserRole(_role.lower()) if isinstance(_role, str) else _role
        self._is_active = doc.get('is_active', True)
        self.language   = doc.get('language', 'fr')
        self.theme      = doc.get('theme', 'light')
        self.created_at = doc.get('created_at', datetime.now(timezone.utc))
        self.last_login = doc.get('last_login')

    # ── Flask-Login interface ────────────────────────────────────────────────

    @property
    def id(self):
        return str(self._id) if self._id else None

    @property
    def is_active(self):
        return self._is_active

    @is_active.setter
    def is_active(self, value):
        self._is_active = value

    # ── Password ─────────────────────────────────────────────────────────────

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    # ── Role helpers ─────────────────────────────────────────────────────────

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_technician(self) -> bool:
        return self.role == UserRole.TECHNICIAN

    @property
    def is_client(self) -> bool:
        return self.role == UserRole.CLIENT

    def get_role_label(self) -> str:
        labels = {
            UserRole.ADMIN:      'Administrateur',
            UserRole.TECHNICIAN: 'Technicien',
            UserRole.CLIENT:     'Client',
        }
        return labels.get(self.role, self.role.value.capitalize())

    def touch_last_login(self) -> None:
        self.last_login = datetime.now(timezone.utc)
        if self._id:
            from app.db import get_col
            get_col('users').update_one(
                {'_id': self._id},
                {'$set': {'last_login': self.last_login}},
            )

    # ── Persistence ──────────────────────────────────────────────────────────

    def save(self) -> 'User':
        from app.db import get_col
        col = get_col('users')
        doc = self._to_doc()
        if self._id:
            col.replace_one({'_id': self._id}, doc)
        else:
            result = col.insert_one(doc)
            object.__setattr__(self, '_id', result.inserted_id)
        return self

    def delete(self) -> None:
        if self._id:
            from app.db import get_col
            get_col('users').delete_one({'_id': self._id})

    def _to_doc(self) -> dict:
        return {
            'username':      self.username,
            'email':         self.email,
            'password_hash': self.password_hash,
            'role':          self.role.value,
            'is_active':     self._is_active,
            'language':      self.language,
            'theme':         self.theme,
            'created_at':    self.created_at,
            'last_login':    self.last_login,
        }

    # ── Class-level queries ──────────────────────────────────────────────────

    @classmethod
    def get_by_id(cls, id_str: str) -> 'User | None':
        from app.db import get_col, oid
        doc = get_col('users').find_one({'_id': oid(id_str)})
        return cls(doc) if doc else None

    @classmethod
    def find_by_username_or_email(cls, identifier: str) -> 'User | None':
        from app.db import get_col
        doc = get_col('users').find_one(
            {'$or': [{'username': identifier}, {'email': identifier}]}
        )
        return cls(doc) if doc else None

    @classmethod
    def find_by_username(cls, username: str) -> 'User | None':
        from app.db import get_col
        doc = get_col('users').find_one({'username': username})
        return cls(doc) if doc else None

    @classmethod
    def find_by_email(cls, email: str) -> 'User | None':
        from app.db import get_col
        doc = get_col('users').find_one({'email': email})
        return cls(doc) if doc else None

    @classmethod
    def find_all(cls) -> list['User']:
        from app.db import get_col
        return [cls(d) for d in get_col('users').find().sort('created_at', -1)]

    @classmethod
    def count_all(cls) -> int:
        from app.db import get_col
        return get_col('users').count_documents({})

    @classmethod
    def count_by_role(cls, role: UserRole) -> int:
        from app.db import get_col
        return get_col('users').count_documents({'role': role.value})

    def __repr__(self) -> str:
        return f'<User {self.username!r} role={self.role.value}>'
