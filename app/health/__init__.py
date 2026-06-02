from flask import Blueprint

health_bp = Blueprint(
    'health',
    __name__,
    template_folder='templates',
    url_prefix='/health',
)

from . import routes  # noqa: E402, F401
