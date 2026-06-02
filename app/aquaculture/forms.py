from datetime import date
from flask_wtf import FlaskForm
from wtforms import (
    StringField, FloatField, IntegerField,
    TextAreaField, SelectField, DateField, SubmitField,
)
from wtforms.validators import DataRequired, Optional, NumberRange, Length
from flask_babel import lazy_gettext as _l
from app.models.aquaculture import PondStatus


class PondForm(FlaskForm):
    name = StringField(
        _l('Nom du bassin'),
        validators=[DataRequired(), Length(max=100)],
        description=_l('Ex: Bassin A1, Mare Nord'),
    )
    species = StringField(
        _l('Espèce principale'),
        validators=[DataRequired(), Length(max=100)],
        description=_l('Ex: Tilapia, Silure, Carpe commune'),
    )
    capacity_m3 = FloatField(
        _l('Capacité (m³)'),
        validators=[Optional(), NumberRange(min=0, message=_l('Doit être positif.'))],
    )
    status = SelectField(
        _l('Statut'),
        choices=[
            (PondStatus.ACTIVE.value, _l('Actif')),
            (PondStatus.INACTIVE.value, _l('Inactif')),
            (PondStatus.MAINTENANCE.value, _l('En maintenance')),
            (PondStatus.HARVESTED.value, _l('Vidé / Récolté')),
        ],
    )
    installation_date = DateField(_l('Date d\'installation'), validators=[Optional()])
    notes = TextAreaField(_l('Notes'), validators=[Optional(), Length(max=2000)])
    submit = SubmitField(_l('Enregistrer'))


class AquacultureRecordForm(FlaskForm):
    record_date = DateField(
        _l('Date d\'observation'),
        validators=[DataRequired()],
        default=date.today,
    )

    # --- Stock ---
    current_count = IntegerField(
        _l('Effectif actuel (poissons)'),
        validators=[Optional(), NumberRange(min=0)],
    )
    avg_weight_g = FloatField(
        _l('Poids moyen (g)'),
        validators=[Optional(), NumberRange(min=0)],
        description=_l('Poids moyen mesuré par sondage'),
    )

    # --- Feeding ---
    feed_quantity_kg = FloatField(
        _l('Aliment distribué (kg)'),
        validators=[Optional(), NumberRange(min=0)],
    )
    feed_type = StringField(
        _l('Type d\'aliment'),
        validators=[Optional(), Length(max=100)],
        description=_l('Ex: Granulés 3mm, Farine de poisson'),
    )

    # --- Mortality ---
    mortality_count = IntegerField(
        _l('Mortalité (nombre)'),
        validators=[Optional(), NumberRange(min=0)],
        default=0,
    )
    mortality_cause = StringField(
        _l('Cause de mortalité'),
        validators=[Optional(), Length(max=200)],
    )

    # --- Environmental (IoT-ready) ---
    water_temp_c = FloatField(
        _l('Température eau (°C)'),
        validators=[Optional(), NumberRange(min=0, max=50)],
    )
    ph = FloatField(
        _l('pH'),
        validators=[Optional(), NumberRange(min=0, max=14)],
    )
    dissolved_oxygen_mgl = FloatField(
        _l('Oxygène dissous (mg/L)'),
        validators=[Optional(), NumberRange(min=0, max=30)],
    )
    turbidity_ntu = FloatField(
        _l('Turbidité (NTU)'),
        validators=[Optional(), NumberRange(min=0)],
    )

    notes = TextAreaField(_l('Notes'), validators=[Optional(), Length(max=2000)])
    submit = SubmitField(_l('Enregistrer'))
