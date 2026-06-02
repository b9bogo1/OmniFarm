from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateField, TextAreaField, DecimalField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_babel import lazy_gettext as _l

from app.models.health import HealthEventType, HealthUnit

EVENT_TYPE_CHOICES = [
    (HealthEventType.VACCINATION.value, _l('Vaccination')),
    (HealthEventType.TREATMENT.value, _l('Traitement')),
    (HealthEventType.DEWORMING.value, _l('Déparasitage')),
    (HealthEventType.INSPECTION.value, _l('Inspection vétérinaire')),
    (HealthEventType.SURGERY.value, _l('Chirurgie')),
]

UNIT_CHOICES = [
    (HealthUnit.POULTRY.value, _l('Aviculture (Volailles)')),
    (HealthUnit.CUNICULTURE.value, _l('Cuniculture (Lapins)')),
    (HealthUnit.AQUACULTURE.value, _l('Aquaculture (Poissons)')),
]


class HealthEventForm(FlaskForm):
    production_unit = SelectField(
        _l('Espèce / Unité'),
        choices=UNIT_CHOICES,
        validators=[DataRequired()],
    )
    unit_ref_id = SelectField(
        _l('Lot / Bassin'),
        choices=[],
        coerce=int,
        validators=[DataRequired()],
    )
    event_type = SelectField(
        _l("Type d'événement"),
        choices=EVENT_TYPE_CHOICES,
        validators=[DataRequired()],
    )
    event_date = DateField(
        _l('Date'),
        validators=[DataRequired()],
    )
    product_used = StringField(
        _l('Produit utilisé'),
        validators=[Optional(), Length(max=200)],
    )
    dose = StringField(
        _l('Dose / Dosage'),
        validators=[Optional(), Length(max=100)],
    )
    administered_by = StringField(
        _l('Administré par'),
        validators=[Optional(), Length(max=200)],
    )
    next_due_date = DateField(
        _l('Prochaine échéance'),
        validators=[Optional()],
    )
    cost_xaf = DecimalField(
        _l('Coût (FCFA)'),
        places=0,
        validators=[Optional(), NumberRange(min=0)],
    )
    notes = TextAreaField(
        _l('Notes'),
        validators=[Optional()],
    )
