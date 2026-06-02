from flask import Blueprint

poultry_bp = Blueprint(
    'poultry',
    __name__,
    template_folder='templates',
    url_prefix='/poultry',
)

from . import routes  # noqa: E402, F401
