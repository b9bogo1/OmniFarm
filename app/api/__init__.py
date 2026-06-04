from flask import Blueprint

api_bp = Blueprint(
    'api',
    __name__,
    url_prefix='/api/v1',
    template_folder='templates',
)

from . import routes  # noqa: E402, F401
