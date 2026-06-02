from flask import Blueprint

marketplace_bp = Blueprint(
    'marketplace',
    __name__,
    template_folder='templates',
    url_prefix='/marketplace',
)

from . import routes  # noqa: E402, F401
