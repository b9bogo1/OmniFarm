"""
Transactional email service for OmniFarm Hub.

Sends are fire-and-forget: errors are logged but never propagate to the caller.
Emails are silently skipped when MAIL_USERNAME is empty or a placeholder,
so the app works in development without any email credentials.
"""
import logging
from flask import render_template, current_app
from flask_babel import force_locale, gettext as _

logger = logging.getLogger(__name__)


def _configured() -> bool:
    username = current_app.config.get('MAIL_USERNAME', '')
    return bool(username) and not username.startswith('[PLACEHOLDER')


def _send(subject: str, recipients: list, html_body: str) -> None:
    if not _configured():
        logger.debug('[EMAIL] Skipped (no credentials): %s → %s', subject, recipients)
        return
    from app.extensions import mail
    from flask_mail import Message
    sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'OmniFarm <noreply@omnifarm.com>')
    try:
        msg = Message(subject=subject, sender=sender, recipients=recipients, html=html_body)
        mail.send(msg)
        logger.info('[EMAIL] Sent: %r → %s', subject, recipients)
    except Exception as exc:
        logger.error('[EMAIL] Failed %r → %s : %s', subject, recipients, exc)


def _get_customer(order):
    """Resolve the customer User object from order.customer_id (may be None)."""
    if not getattr(order, 'customer_id', None):
        return None
    try:
        from app.models.user import User
        return User.get_by_id(order.customer_id)
    except Exception:
        return None


def _customer_locale(order) -> str:
    try:
        customer = _get_customer(order)
        if customer and getattr(customer, 'language', None):
            return customer.language
    except Exception:
        pass
    return current_app.config.get('BABEL_DEFAULT_LOCALE', 'fr')


def _recipient(order) -> list:
    customer = _get_customer(order)
    if customer and getattr(customer, 'email', None):
        return [customer.email]
    return []


def _order_url(order) -> str:
    from flask import url_for
    try:
        return url_for(
            'marketplace.order_confirmation',
            order_number=order.order_number,
            _external=True,
        )
    except Exception:
        base = current_app.config.get('BASE_URL', '').rstrip('/')
        return f"{base}/marketplace/order/{order.order_number}"


def send_order_confirmation(order) -> None:
    recipients = _recipient(order)
    if not recipients:
        return
    with force_locale(_customer_locale(order)):
        html = render_template('email/order_confirmation.html', order=order,
                               order_url=_order_url(order))
        subject = _('[OmniFarm] Commande %(number)s confirmée', number=order.order_number)
    _send(subject=subject, recipients=recipients, html_body=html)


def send_order_status_update(order) -> None:
    recipients = _recipient(order)
    if not recipients:
        return
    with force_locale(_customer_locale(order)):
        html = render_template('email/order_status_update.html', order=order,
                               order_url=_order_url(order))
        subject = _('[OmniFarm] Mise à jour — Commande %(number)s', number=order.order_number)
    _send(subject=subject, recipients=recipients, html_body=html)
