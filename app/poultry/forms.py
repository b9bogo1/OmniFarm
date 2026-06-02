from datetime import date
from flask_wtf import FlaskForm
from wtforms import (
    StringField, FloatField, IntegerField,
    TextAreaField, SelectField, DateField, SubmitField,
)
from wtforms.validators import DataRequired, Optional, NumberRange, Length
from flask_babel import lazy_gettext as _l
from app.models.poultry import FlockStatus


class FlockForm(FlaskForm):
    name = StringField(
        _l('Nom du lot'),
        validators=[DataRequired(), Length(max=100)],
        description=_l('Ex: Lot Poulet Mars-2026, Pondeuses Bâtiment B'),
    )
    species = StringField(
        _l('Espèce / Type'),
        validators=[DataRequired(), Length(max=100)],
        description=_l('Ex: Poulet de chair, Pondeuse, Pintade'),
    )
    breed = StringField(
        _l('Souche / Race'),
        validators=[Optional(), Length(max=100)],
        description=_l('Ex: Cobb 500, ISA Brown, Ross 308'),
    )
    placement_date = DateField(
        _l('Date de mise en place'),
        validators=[DataRequired()],
        default=date.today,
    )
    initial_count = IntegerField(
        _l('Effectif initial'),
        validators=[DataRequired(), NumberRange(min=1)],
    )
    house_number = StringField(
        _l('Bâtiment / Poulailler'),
        validators=[Optional(), Length(max=50)],
        description=_l('Ex: Bâtiment A, Poulailler 2'),
    )
    status = SelectField(
        _l('Statut'),
        choices=[
            (FlockStatus.ACTIVE.value, _l('Actif')),
            (FlockStatus.SOLD.value, _l('Vendu')),
            (FlockStatus.CULLED.value, _l('Réformé')),
        ],
    )
    notes = TextAreaField(_l('Notes'), validators=[Optional(), Length(max=2000)])
    submit = SubmitField(_l('Enregistrer'))


class PoultryRecordForm(FlaskForm):
    record_date = DateField(
        _l('Date d\'observation'),
        validators=[DataRequired()],
        default=date.today,
    )

    # --- Feeding & water ---
    feed_quantity_kg = FloatField(
        _l('Aliment consommé (kg)'),
        validators=[Optional(), NumberRange(min=0)],
    )
    feed_type = StringField(
        _l('Type d\'aliment'),
        validators=[Optional(), Length(max=100)],
        description=_l('Ex: Démarrage, Croissance, Finition'),
    )
    water_consumed_l = FloatField(
        _l('Eau consommée (L)'),
        validators=[Optional(), NumberRange(min=0)],
    )

    # --- Production ---
    eggs_collected = IntegerField(
        _l('Œufs collectés'),
        validators=[Optional(), NumberRange(min=0)],
        default=0,
        description=_l('Laisser à 0 pour les lots chair'),
    )
    avg_weight_g = FloatField(
        _l('Poids vif moyen (g)'),
        validators=[Optional(), NumberRange(min=0)],
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
    ambient_temp_c = FloatField(
        _l('Température ambiante (°C)'),
        validators=[Optional(), NumberRange(min=-10, max=60)],
    )
    humidity_pct = FloatField(
        _l('Humidité relative (%)'),
        validators=[Optional(), NumberRange(min=0, max=100)],
    )

    notes = TextAreaField(_l('Notes'), validators=[Optional(), Length(max=2000)])
    submit = SubmitField(_l('Enregistrer'))
