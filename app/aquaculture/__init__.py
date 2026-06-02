from flask import Blueprint

aquaculture_bp = Blueprint(
    'aquaculture',
    __name__,
    template_folder='templates',
    url_prefix='/aquaculture',
)

from . import routes  # noqa: E402, F401
