from flask import Blueprint

cuniculture_bp = Blueprint(
    'cuniculture',
    __name__,
    template_folder='templates',
    url_prefix='/cuniculture',
)

from . import routes  # noqa: E402, F401
