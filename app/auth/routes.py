from flask import render_template, redirect, url_for, flash, request, session, abort
from flask_login import login_user, logout_user, login_required, current_user
from flask_babel import gettext as _

from app.extensions import limiter
from app.db import get_col
from app.models.user import User, UserRole
from . import auth_bp
from .decorators import admin_required
from .forms import LoginForm, SetupForm, UserAdminForm, CustomerRegisterForm


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.username.data.strip()
        user = User.find_by_username_or_email(identifier)

        if user and user.is_active and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            user.touch_last_login()
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))

        flash(_('Identifiants incorrects ou compte désactivé. Veuillez réessayer.'), 'danger')

    return render_template('auth/login.html', form=form, title=_('Connexion'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('marketplace.index'))

    form = CustomerRegisterForm()
    if form.validate_on_submit():
        if User.find_by_username(form.username.data.strip()):
            form.username.errors.append(_('Ce nom d\'utilisateur est déjà utilisé.'))
        elif User.find_by_email(form.email.data.strip().lower()):
            form.email.errors.append(_('Cette adresse e-mail est déjà utilisée.'))
        else:
            user = User(
                username=form.username.data.strip(),
                email=form.email.data.strip().lower(),
                role=UserRole.CLIENT.value,
                is_active=True,
                language=session.get('language', 'fr'),
                theme='light',
            )
            user.set_password(form.password.data)
            user.save()
            login_user(user)
            user.touch_last_login()
            flash(_('Bienvenue %(u)s ! Votre compte a été créé avec succès.', u=user.username), 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('marketplace.index'))

    return render_template('auth/register.html', form=form, title=_('Créer un compte'))


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash(_('Vous avez été déconnecté avec succès.'), 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/set-language/<lang_code>')
def set_language(lang_code: str):
    from config import Config
    if lang_code in Config.LANGUAGES:
        session['language'] = lang_code
        if current_user.is_authenticated:
            current_user.language = lang_code
            current_user.save()
    return redirect(request.referrer or url_for('auth.login'))


@auth_bp.route('/set-theme/<theme>')
def set_theme(theme: str):
    if theme in ('light', 'dark'):
        session['theme'] = theme
        if current_user.is_authenticated:
            current_user.theme = theme
            current_user.save()
    return redirect(request.referrer or url_for('main.dashboard'))


@auth_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    if get_col('users').count_documents({}) > 0:
        return redirect(url_for('auth.login'))

    form = SetupForm()
    if form.validate_on_submit():
        admin = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            role=UserRole.ADMIN.value,
            is_active=True,
            language=session.get('language', 'fr'),
            theme='light',
        )
        admin.set_password(form.password.data)
        admin.save()
        flash(_('Compte administrateur créé. Connectez-vous pour commencer.'), 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/setup.html', form=form, title=_('Configuration initiale'))


# ── Admin: User Management ──────────────────────────────────────────────────

@auth_bp.route('/admin/users')
@admin_required
def admin_users():
    users = User.find_all()
    counts = {
        'total':      len(users),
        'admin':      sum(1 for u in users if u.role == UserRole.ADMIN),
        'technician': sum(1 for u in users if u.role == UserRole.TECHNICIAN),
        'client':     sum(1 for u in users if u.role == UserRole.CLIENT),
        'active':     sum(1 for u in users if u.is_active),
        'inactive':   sum(1 for u in users if not u.is_active),
    }
    return render_template('auth/admin_users.html', users=users, counts=counts,
                           UserRole=UserRole, title=_('Gestion des utilisateurs'))


@auth_bp.route('/admin/users/new', methods=['GET', 'POST'])
@admin_required
def admin_create_user():
    form = UserAdminForm()
    if form.validate_on_submit():
        if not form.new_password.data:
            form.new_password.errors.append(_('Le mot de passe est requis pour la création.'))
        elif User.find_by_username(form.username.data.strip()):
            form.username.errors.append(_('Ce nom d\'utilisateur est déjà utilisé.'))
        elif User.find_by_email(form.email.data.strip().lower()):
            form.email.errors.append(_('Cette adresse e-mail est déjà utilisée.'))
        else:
            user = User(
                username=form.username.data.strip(),
                email=form.email.data.strip().lower(),
                role=form.role.data,
                is_active=form.is_active.data,
                language='fr',
                theme='light',
            )
            user.set_password(form.new_password.data)
            user.save()
            flash(_('Utilisateur %(u)s créé avec succès.', u=user.username), 'success')
            return redirect(url_for('auth.admin_users'))

    return render_template('auth/admin_user_form.html', form=form, is_edit=False,
                           user=None, title=_('Nouvel utilisateur'))


@auth_bp.route('/admin/users/<user_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    user = User.get_by_id(user_id)
    if user is None:
        abort(404)

    form = UserAdminForm(obj=user)

    if request.method == 'GET':
        form.role.data = user.role.value
        form.is_active.data = user.is_active

    if form.validate_on_submit():
        dup_username = User.find_by_username(form.username.data.strip())
        dup_email    = User.find_by_email(form.email.data.strip().lower())

        if dup_username and dup_username.id != user_id:
            form.username.errors.append(_('Ce nom d\'utilisateur est déjà utilisé.'))
        elif dup_email and dup_email.id != user_id:
            form.email.errors.append(_('Cette adresse e-mail est déjà utilisée.'))
        else:
            if (user.role == UserRole.ADMIN
                    and UserRole(form.role.data) != UserRole.ADMIN
                    and User.count_by_role(UserRole.ADMIN) <= 1):
                flash(_('Impossible de rétrograder le dernier administrateur.'), 'danger')
                return render_template('auth/admin_user_form.html', form=form, is_edit=True,
                                       user=user, title=_('Modifier l\'utilisateur'))

            user.username  = form.username.data.strip()
            user.email     = form.email.data.strip().lower()
            user.role      = UserRole(form.role.data)
            user.is_active = form.is_active.data

            if form.new_password.data:
                user.set_password(form.new_password.data)

            user.save()
            flash(_('Utilisateur %(u)s mis à jour.', u=user.username), 'success')
            return redirect(url_for('auth.admin_users'))

    return render_template('auth/admin_user_form.html', form=form, is_edit=True,
                           user=user, title=_('Modifier l\'utilisateur'))


@auth_bp.route('/admin/users/<user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = User.get_by_id(user_id)
    if user is None:
        abort(404)

    if user.id == current_user.id:
        flash(_('Vous ne pouvez pas supprimer votre propre compte.'), 'danger')
        return redirect(url_for('auth.admin_users'))

    if (user.role == UserRole.ADMIN
            and User.count_by_role(UserRole.ADMIN) <= 1):
        flash(_('Impossible de supprimer le dernier administrateur.'), 'danger')
        return redirect(url_for('auth.admin_users'))

    username = user.username
    user.delete()
    flash(_('Utilisateur %(u)s supprimé.', u=username), 'success')
    return redirect(url_for('auth.admin_users'))
