from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, DateField, TextAreaField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_babel import lazy_gettext as _l

from app.models.finance import EntryType, FinanceCategory, ProductionScope

ALL_CATEGORIES = [
    (FinanceCategory.FEED.value, _l('Alimentation')),
    (FinanceCategory.MEDICATION.value, _l('Médicaments')),
    (FinanceCategory.EQUIPMENT.value, _l('Équipement')),
    (FinanceCategory.LABOR.value, _l("Main d'œuvre")),
    (FinanceCategory.UTILITIES.value, _l('Services publics')),
    (FinanceCategory.TRANSPORT.value, _l('Transport')),
    (FinanceCategory.MAINTENANCE.value, _l('Maintenance')),
    (FinanceCategory.PRODUCT_SALE.value, _l('Vente produit')),
    (FinanceCategory.DIRECT_SALE.value, _l('Vente directe')),
    (FinanceCategory.SUBSIDY.value, _l('Subvention')),
    (FinanceCategory.OTHER.value, _l('Autre')),
]

SCOPE_CHOICES = [
    (ProductionScope.GENERAL.value, _l('Général')),
    (ProductionScope.AQUACULTURE.value, _l('Aquaculture')),
    (ProductionScope.POULTRY.value, _l('Aviculture')),
    (ProductionScope.CUNICULTURE.value, _l('Cuniculture')),
]


class FinanceEntryForm(FlaskForm):
    entry_type = SelectField(
        _l('Type'),
        choices=[
            (EntryType.EXPENSE.value, _l('Dépense')),
            (EntryType.REVENUE.value, _l('Revenu')),
        ],
        validators=[DataRequired()],
    )
    category = SelectField(
        _l('Catégorie'),
        choices=ALL_CATEGORIES,
        validators=[DataRequired()],
    )
    description = StringField(
        _l('Description'),
        validators=[DataRequired(), Length(max=300)],
    )
    amount_xaf = DecimalField(
        _l('Montant (FCFA)'),
        places=0,
        validators=[DataRequired(), NumberRange(min=1, message=_l('Le montant doit être positif.'))],
    )
    entry_date = DateField(
        _l('Date'),
        validators=[DataRequired()],
    )
    production_scope = SelectField(
        _l('Unité de production'),
        choices=SCOPE_CHOICES,
        validators=[DataRequired()],
    )
    payment_method = StringField(
        _l('Moyen de paiement'),
        validators=[Optional(), Length(max=50)],
    )
    reference_number = StringField(
        _l('Référence'),
        validators=[Optional(), Length(max=100)],
    )
    notes = TextAreaField(
        _l('Notes'),
        validators=[Optional()],
    )
