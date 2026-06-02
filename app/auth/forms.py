from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, BooleanField, SubmitField,
                     SelectField)
from wtforms.validators import DataRequired, Length, Email, EqualTo, Regexp, Optional
from flask_babel import lazy_gettext as _l


class LoginForm(FlaskForm):
    username = StringField(
        _l('Nom d\'utilisateur'),
        validators=[
            DataRequired(message=_l('Ce champ est requis.')),
            Length(1, 64, message=_l('Entre 1 et 64 caractères.')),
        ],
    )
    password = PasswordField(
        _l('Mot de passe'),
        validators=[DataRequired(message=_l('Ce champ est requis.'))],
    )
    remember_me = BooleanField(_l('Se souvenir de moi'))
    submit = SubmitField(_l('Connexion'))


class SetupForm(FlaskForm):
    username = StringField(
        _l('Nom d\'utilisateur'),
        validators=[
            DataRequired(message=_l('Ce champ est requis.')),
            Length(3, 64, message=_l('Entre 3 et 64 caractères.')),
            Regexp(r'^[A-Za-z0-9_.-]+$',
                   message=_l('Lettres, chiffres, tirets et points uniquement.')),
        ],
    )
    email = StringField(
        _l('Adresse e-mail'),
        validators=[
            DataRequired(message=_l('Ce champ est requis.')),
            Email(message=_l('Adresse e-mail invalide.')),
            Length(6, 120, message=_l('Entre 6 et 120 caractères.')),
        ],
    )
    password = PasswordField(
        _l('Mot de passe'),
        validators=[
            DataRequired(message=_l('Ce champ est requis.')),
            Length(8, 128, message=_l('Au moins 8 caractères.')),
        ],
    )
    confirm = PasswordField(
        _l('Confirmer le mot de passe'),
        validators=[
            DataRequired(message=_l('Ce champ est requis.')),
            EqualTo('password', message=_l('Les mots de passe ne correspondent pas.')),
        ],
    )
    submit = SubmitField(_l('Créer le compte administrateur'))


class CustomerRegisterForm(FlaskForm):
    username = StringField(
        _l('Nom d\'utilisateur'),
        validators=[
            DataRequired(message=_l('Ce champ est requis.')),
            Length(3, 64, message=_l('Entre 3 et 64 caractères.')),
            Regexp(r'^[A-Za-z0-9_.-]+$',
                   message=_l('Lettres, chiffres, tirets et points uniquement.')),
        ],
    )
    email = StringField(
        _l('Adresse e-mail'),
        validators=[
            DataRequired(message=_l('Ce champ est requis.')),
            Email(message=_l('Adresse e-mail invalide.')),
            Length(6, 120, message=_l('Entre 6 et 120 caractères.')),
        ],
    )
    password = PasswordField(
        _l('Mot de passe'),
        validators=[
            DataRequired(message=_l('Ce champ est requis.')),
            Length(8, 128, message=_l('Au moins 8 caractères.')),
        ],
    )
    confirm = PasswordField(
        _l('Confirmer le mot de passe'),
        validators=[
            DataRequired(message=_l('Ce champ est requis.')),
            EqualTo('password', message=_l('Les mots de passe ne correspondent pas.')),
        ],
    )
    submit = SubmitField(_l('Créer mon compte'))


class UserAdminForm(FlaskForm):
    username = StringField(
        _l('Nom d\'utilisateur'),
        validators=[
            DataRequired(message=_l('Ce champ est requis.')),
            Length(3, 64, message=_l('Entre 3 et 64 caractères.')),
            Regexp(r'^[A-Za-z0-9_.-]+$',
                   message=_l('Lettres, chiffres, tirets et points uniquement.')),
        ],
    )
    email = StringField(
        _l('Adresse e-mail'),
        validators=[
            DataRequired(message=_l('Ce champ est requis.')),
            Email(message=_l('Adresse e-mail invalide.')),
            Length(6, 120, message=_l('Entre 6 et 120 caractères.')),
        ],
    )
    role = SelectField(
        _l('Rôle'),
        choices=[
            ('admin',      _l('Administrateur')),
            ('technician', _l('Technicien')),
            ('client',     _l('Client')),
        ],
        validators=[DataRequired()],
    )
    is_active = BooleanField(_l('Compte actif'), default=True)
    new_password = PasswordField(
        _l('Mot de passe'),
        validators=[
            Optional(),
            Length(8, 128, message=_l('Au moins 8 caractères.')),
        ],
    )
    confirm_password = PasswordField(
        _l('Confirmer le mot de passe'),
        validators=[
            EqualTo('new_password', message=_l('Les mots de passe ne correspondent pas.')),
        ],
    )
    submit = SubmitField(_l('Enregistrer'))
