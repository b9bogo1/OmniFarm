from datetime import date
from flask_wtf import FlaskForm
from wtforms import (
    StringField, FloatField, IntegerField,
    TextAreaField, SelectField, DateField, SubmitField,
)
from wtforms.validators import DataRequired, Optional, NumberRange, Length
from flask_babel import lazy_gettext as _l
from app.models.cuniculture import RabbitStatus


class RabbitBatchForm(FlaskForm):
    name = StringField(
        _l('Nom de la cage / lot'),
        validators=[DataRequired(), Length(max=100)],
        description=_l('Ex: Cage C12, Lot Géniteurs Mars-2026'),
    )
    breed = StringField(
        _l('Race'),
        validators=[Optional(), Length(max=100)],
        description=_l('Ex: Néo-Zélandais, Californien, Local'),
    )
    acquisition_date = DateField(
        _l('Date d\'acquisition'),
        validators=[DataRequired()],
        default=date.today,
    )
    initial_count = IntegerField(
        _l('Effectif initial'),
        validators=[DataRequired(), NumberRange(min=1)],
    )
    female_count = IntegerField(
        _l('Dont femelles'),
        validators=[Optional(), NumberRange(min=0)],
        default=0,
    )
    male_count = IntegerField(
        _l('Dont mâles'),
        validators=[Optional(), NumberRange(min=0)],
        default=0,
    )
    status = SelectField(
        _l('Statut'),
        choices=[
            (RabbitStatus.ACTIVE.value, _l('Actif')),
            (RabbitStatus.SOLD.value, _l('Vendu')),
            (RabbitStatus.DECEASED.value, _l('Décédé')),
        ],
    )
    notes = TextAreaField(_l('Notes'), validators=[Optional(), Length(max=2000)])
    submit = SubmitField(_l('Enregistrer'))


class CunicultureRecordForm(FlaskForm):
    record_date = DateField(
        _l('Date d\'observation'),
        validators=[DataRequired()],
        default=date.today,
    )

    # --- Feeding ---
    feed_quantity_kg = FloatField(
        _l('Aliment distribué (kg)'),
        validators=[Optional(), NumberRange(min=0)],
    )
    feed_type = StringField(
        _l('Type d\'aliment'),
        validators=[Optional(), Length(max=100)],
        description=_l('Ex: Granulés, Foin, Légumes verts'),
    )

    # --- Reproduction ---
    litters_born = IntegerField(
        _l('Portées mises bas'),
        validators=[Optional(), NumberRange(min=0)],
        default=0,
    )
    kits_born = IntegerField(
        _l('Lapereaux nés (total)'),
        validators=[Optional(), NumberRange(min=0)],
        default=0,
    )
    kits_survived = IntegerField(
        _l('Lapereaux survivants'),
        validators=[Optional(), NumberRange(min=0)],
        default=0,
    )

    # --- Growth ---
    avg_weight_g = FloatField(
        _l('Poids moyen (g)'),
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

    notes = TextAreaField(_l('Notes'), validators=[Optional(), Length(max=2000)])
    submit = SubmitField(_l('Enregistrer'))
