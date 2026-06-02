from flask import Blueprint

iot_bp = Blueprint('iot', __name__, url_prefix='/iot', template_folder='templates')

from . import routes  # noqa: E402,F401
