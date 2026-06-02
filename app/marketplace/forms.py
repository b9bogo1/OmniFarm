from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, FloatField, TextAreaField,
    SelectField, BooleanField, SubmitField, IntegerField,
)
from wtforms.validators import DataRequired, Optional, NumberRange, Length
from flask_babel import lazy_gettext as _l
from app.models.marketplace import ProductCategory, PaymentMethod

_ALLOWED_IMG = ['jpg', 'jpeg', 'png', 'webp']


class ProductForm(FlaskForm):
    name = StringField(
        _l('Nom du produit'),
        validators=[DataRequired(), Length(max=200)],
    )
    description = TextAreaField(
        _l('Description'),
        validators=[Optional(), Length(max=2000)],
    )
    category = SelectField(
        _l('Catégorie'),
        choices=[
            (ProductCategory.FISH.value, _l('🐟 Poisson')),
            (ProductCategory.POULTRY.value, _l('🐔 Volaille')),
            (ProductCategory.RABBIT.value, _l('🐇 Lapin')),
            (ProductCategory.EGGS.value, _l('🥚 Œufs')),
            (ProductCategory.OTHER.value, _l('🌿 Autre')),
        ],
    )
    price_xaf = FloatField(
        _l('Prix unitaire (FCFA)'),
        validators=[DataRequired(), NumberRange(min=0, message=_l('Le prix doit être positif.'))],
    )
    unit = StringField(
        _l('Unité de vente'),
        validators=[DataRequired(), Length(max=50)],
        description=_l('Ex: kg, pièce, douzaine, sachet'),
    )
    stock_quantity = FloatField(
        _l('Stock disponible'),
        validators=[Optional(), NumberRange(min=0)],
        default=0.0,
    )
    is_available = BooleanField(_l('Visible et disponible à la vente'), default=True)
    image = FileField(
        _l('Photo du produit'),
        validators=[
            Optional(),
            FileAllowed(_ALLOWED_IMG, _l('JPG, PNG ou WebP uniquement (max 5 Mo).')),
        ],
        description=_l('Facultatif — JPG/PNG/WebP, max 5 Mo. L\'image sera recadrée en 400×400 px.'),
    )
    remove_image = BooleanField(_l('Supprimer la photo actuelle'), default=False)
    submit = SubmitField(_l('Enregistrer'))


class CheckoutForm(FlaskForm):
    customer_name = StringField(
        _l('Nom complet'),
        validators=[DataRequired(), Length(max=200)],
    )
    customer_phone = StringField(
        _l('Numéro de téléphone'),
        validators=[DataRequired(), Length(max=50)],
        description=_l('Ex: +237 6XX XXX XXX'),
    )
    customer_address = TextAreaField(
        _l('Adresse de livraison'),
        validators=[Optional(), Length(max=500)],
        description=_l('Quartier, ville, point de repère'),
    )
    payment_method = SelectField(
        _l('Mode de paiement'),
        choices=[
            (PaymentMethod.ORANGE_MONEY.value, _l('Orange Money')),
            (PaymentMethod.MTN_MOBILE_MONEY.value, _l('MTN Mobile Money (MoMo)')),
            (PaymentMethod.CASH_ON_DELIVERY.value, _l('Paiement à la livraison')),
        ],
    )
    mobile_money_phone = StringField(
        _l('Numéro Mobile Money'),
        validators=[Optional(), Length(max=50)],
        description=_l('Laissez vide si identique au numéro de contact'),
    )
    notes = TextAreaField(
        _l('Instructions / Notes'),
        validators=[Optional(), Length(max=500)],
    )
    submit = SubmitField(_l('Confirmer la commande'))


class UpdateOrderStatusForm(FlaskForm):
    status = SelectField(_l('Nouveau statut'), choices=[])
    submit = SubmitField(_l('Mettre à jour'))


_ALLOWED_CAROUSEL = ['jpg', 'jpeg', 'png', 'webp']


class CarouselSlideForm(FlaskForm):
    title = StringField(
        _l('Titre principal'),
        validators=[DataRequired(), Length(max=200)],
    )
    subtitle = TextAreaField(
        _l('Sous-titre'),
        validators=[Optional(), Length(max=500)],
        description=_l('Phrase d\'accroche visible sous le titre.'),
    )
    cta_text = StringField(
        _l('Texte du bouton'),
        validators=[Optional(), Length(max=100)],
        description=_l('Ex : Commander maintenant'),
    )
    cta_url = StringField(
        _l('Lien du bouton'),
        validators=[Optional(), Length(max=500)],
        default='#products',
        description=_l('URL de destination. Utilisez #products pour défiler vers le catalogue.'),
    )
    sort_order = IntegerField(
        _l("Ordre d'affichage"),
        validators=[Optional()],
        default=0,
        description=_l('Les valeurs les plus petites s\'affichent en premier.'),
    )
    is_active = BooleanField(_l('Slide visible dans le carousel'), default=True)
    image = FileField(
        _l('Image de fond'),
        validators=[
            Optional(),
            FileAllowed(_ALLOWED_CAROUSEL, _l('JPG, PNG ou WebP uniquement (max 8 Mo).')),
        ],
        description=_l('Recommandé : 1400 × 700 px (ratio 2:1), format paysage. Max 8 Mo.'),
    )
    remove_image = BooleanField(_l("Supprimer l'image actuelle"), default=False)
    submit = SubmitField(_l('Enregistrer'))
