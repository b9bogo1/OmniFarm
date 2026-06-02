"""
Payment Gateway Integration — OmniFarm Hub
==========================================

Supports:
  • Orange Money WebPay (OAPI — Cameroon)  https://developer.orange.com/apis/om-webpay-prod
  • MTN Mobile Money Collection (MoMo API v1)  https://momodeveloper.mtn.com

Configure credentials in .env:
  ORANGE_MONEY_CLIENT_ID, ORANGE_MONEY_CLIENT_SECRET, ORANGE_MONEY_MERCHANT_KEY
  MTN_MOMO_SUBSCRIPTION_KEY, MTN_MOMO_API_USER, MTN_MOMO_API_KEY, MTN_MOMO_TARGET_ENV
  BASE_URL  (public root URL, e.g. https://omnifarm.example.com)

When credentials are absent the functions return success=False with a clear
message so the calling code can fall back gracefully (e.g. treat as cash order).
"""
from __future__ import annotations

import base64
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── Orange Money base URL (production) ───────────────────────────────────────
_ORANGE_API_BASE = 'https://api.orange.com'

# ── MTN MoMo base URLs ────────────────────────────────────────────────────────
_MTN_BASE_URLS: dict[str, str] = {
    'mtncameroon': 'https://proxy.momoapi.mtn.com',
    'sandbox':     'https://sandbox.momodeveloper.mtn.com',
}


# ── Shared response type ──────────────────────────────────────────────────────

@dataclass
class GatewayResponse:
    success: bool
    reference: str | None
    message: str
    payment_url: str | None = None          # Orange Money redirect URL
    raw_response: dict = field(default_factory=dict)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cfg(key: str) -> str:
    """Read a payment-related config value from the current Flask app."""
    from flask import current_app
    return current_app.config.get(key, '')


def _base_url() -> str:
    return _cfg('BASE_URL').rstrip('/')


# ── Orange Money ──────────────────────────────────────────────────────────────

def _orange_bearer_token() -> str | None:
    """Obtain a short-lived Bearer token via OAuth2 client_credentials."""
    import requests

    client_id     = _cfg('ORANGE_MONEY_CLIENT_ID')
    client_secret = _cfg('ORANGE_MONEY_CLIENT_SECRET')
    if not (client_id and client_secret):
        return None

    credentials = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()
    try:
        resp = requests.post(
            f'{_ORANGE_API_BASE}/oauth/v3/token',
            headers={
                'Authorization': f'Basic {credentials}',
                'Content-Type':  'application/x-www-form-urlencoded',
                'Accept':        'application/json',
            },
            data={'grant_type': 'client_credentials'},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get('access_token')
    except Exception as exc:
        logger.error('[ORANGE] Token request failed: %s', exc)
        return None


def initiate_orange_money(
    order_number: str,
    amount_xaf: int,
    phone: str,
    description: str = '',
) -> GatewayResponse:
    """
    Start an Orange Money WebPay session for a Cameroon merchant.

    Flow:
      1. Obtain Bearer token  → POST /oauth/v3/token
      2. Create payment       → POST /orange-money-webpay/cm/v1/webpayment
      3. Return payment_url   → caller redirects the customer there
      4. Orange calls our webhook (/marketplace/webhook/orange) when paid

    Returns GatewayResponse with:
      success      True when payment_url was obtained
      reference    pay_token from Orange (stored as gateway_reference)
      payment_url  URL to redirect the customer to
    """
    import requests as req

    client_id     = _cfg('ORANGE_MONEY_CLIENT_ID')
    client_secret = _cfg('ORANGE_MONEY_CLIENT_SECRET')
    merchant_key  = _cfg('ORANGE_MONEY_MERCHANT_KEY')

    if not all([client_id, client_secret, merchant_key]):
        logger.warning('[ORANGE] Credentials not configured — skipping gateway call.')
        return GatewayResponse(
            success=False,
            reference=None,
            message='Orange Money non configuré. Ajoutez les clés dans .env.',
            raw_response={'stub': True, 'order_number': order_number,
                          'amount_xaf': amount_xaf, 'ts': _now()},
        )

    token = _orange_bearer_token()
    if not token:
        return GatewayResponse(
            success=False,
            reference=None,
            message='Orange Money : impossible d\'obtenir un token d\'accès.',
            raw_response={'error': 'token_fetch_failed', 'ts': _now()},
        )

    base = _base_url()
    payload = {
        'merchant_key': merchant_key,
        'currency':     'XAF',
        'order_id':     order_number,
        'amount':       str(amount_xaf),
        'return_url':   f'{base}/marketplace/order/{order_number}',
        'cancel_url':   f'{base}/marketplace/cart',
        'notif_url':    f'{base}/marketplace/webhook/orange',
        'lang':         'fr',
        'reference':    order_number,
    }
    if description:
        payload['note'] = description[:255]

    try:
        resp = req.post(
            f'{_ORANGE_API_BASE}/orange-money-webpay/cm/v1/webpayment',
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type':  'application/json',
                'Accept':        'application/json',
            },
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        pay_token   = data.get('pay_token', '')
        payment_url = data.get('payment_url', '')

        logger.info('[ORANGE] Payment session created: order=%s token=%s', order_number, pay_token)
        return GatewayResponse(
            success=bool(payment_url),
            reference=pay_token or None,
            payment_url=payment_url or None,
            message='Redirection vers Orange Money...' if payment_url else 'Orange Money : URL de paiement manquante.',
            raw_response=data,
        )

    except Exception as exc:
        logger.exception('[ORANGE] Payment initiation failed: %s', exc)
        return GatewayResponse(
            success=False,
            reference=None,
            message=f'Orange Money : erreur — {exc}',
            raw_response={'error': str(exc), 'ts': _now()},
        )


def verify_orange_webhook(notif_token: str, pay_token: str) -> bool:
    """
    Verify that an Orange Money webhook notification is authentic.
    Orange sends notif_token in the callback body; it must match the
    pay_token returned when the payment session was created.
    """
    if not notif_token or not pay_token:
        return False
    return notif_token == pay_token


# ── MTN Mobile Money ──────────────────────────────────────────────────────────

def _mtn_credentials() -> tuple[str, str, str, str]:
    """Return (subscription_key, api_user, api_key, target_env)."""
    return (
        _cfg('MTN_MOMO_SUBSCRIPTION_KEY'),
        _cfg('MTN_MOMO_API_USER'),
        _cfg('MTN_MOMO_API_KEY'),
        _cfg('MTN_MOMO_TARGET_ENV') or 'mtncameroon',
    )


def _mtn_access_token(sub_key: str, api_user: str, api_key: str, base: str) -> str | None:
    """Obtain a short-lived access token from the MTN MoMo token endpoint."""
    import requests as req

    credentials = base64.b64encode(f'{api_user}:{api_key}'.encode()).decode()
    try:
        resp = req.post(
            f'{base}/collection/token/',
            headers={
                'Authorization':           f'Basic {credentials}',
                'Ocp-Apim-Subscription-Key': sub_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get('access_token')
    except Exception as exc:
        logger.error('[MTN] Token request failed: %s', exc)
        return None


def initiate_mtn_mobile_money(
    order_number: str,
    amount_xaf: int,
    phone: str,
    description: str = '',
) -> GatewayResponse:
    """
    Initiate an MTN MoMo Request-to-Pay (Collection API v1).

    Flow:
      1. Obtain access token  → POST /collection/token/
      2. Send R2P request     → PUT  /collection/v1_0/requesttopay/{uuid}  → 202 Accepted
      3. MTN pushes a prompt to the customer's phone
      4. MTN calls our webhook (/marketplace/webhook/mtn) with the result
         OR we poll GET /collection/v1_0/requesttopay/{uuid}

    Returns GatewayResponse with:
      success    True when 202 Accepted (request in flight, NOT yet paid)
      reference  UUID (X-Reference-Id) used for status polling
    """
    import requests as req

    sub_key, api_user, api_key, target_env = _mtn_credentials()
    if not all([sub_key, api_user, api_key]):
        logger.warning('[MTN] Credentials not configured — skipping gateway call.')
        return GatewayResponse(
            success=False,
            reference=None,
            message='MTN MoMo non configuré. Ajoutez les clés dans .env.',
            raw_response={'stub': True, 'order_number': order_number,
                          'amount_xaf': amount_xaf, 'ts': _now()},
        )

    base = _MTN_BASE_URLS.get(target_env, _MTN_BASE_URLS['sandbox'])
    token = _mtn_access_token(sub_key, api_user, api_key, base)
    if not token:
        return GatewayResponse(
            success=False,
            reference=None,
            message='MTN MoMo : impossible d\'obtenir un token d\'accès.',
            raw_response={'error': 'token_fetch_failed', 'ts': _now()},
        )

    reference_id = str(uuid.uuid4())
    # Normalize phone: remove +, spaces, dashes → plain digits
    phone_clean = ''.join(c for c in phone if c.isdigit())

    payload = {
        'amount':      str(amount_xaf),
        'currency':    'XAF',
        'externalId':  order_number,
        'payer': {
            'partyIdType': 'MSISDN',
            'partyId':     phone_clean,
        },
        'payerMessage': (description or f'OmniFarm {order_number}')[:160],
        'payeeNote':    f'Commande {order_number}'[:160],
    }

    try:
        resp = req.put(
            f'{base}/collection/v1_0/requesttopay/{reference_id}',
            headers={
                'Authorization':            f'Bearer {token}',
                'X-Reference-Id':            reference_id,
                'X-Target-Environment':      target_env,
                'Ocp-Apim-Subscription-Key': sub_key,
                'Content-Type':             'application/json',
            },
            json=payload,
            timeout=15,
        )

        if resp.status_code == 202:
            logger.info('[MTN] R2P accepted: order=%s ref=%s', order_number, reference_id)
            return GatewayResponse(
                success=True,
                reference=reference_id,
                message='Demande envoyée. Approuvez le paiement sur votre téléphone MTN.',
                raw_response={'reference_id': reference_id, 'status': 'PENDING', 'ts': _now()},
            )
        else:
            logger.error('[MTN] R2P rejected: %s %s', resp.status_code, resp.text)
            return GatewayResponse(
                success=False,
                reference=None,
                message=f'MTN MoMo : erreur {resp.status_code}.',
                raw_response={'status_code': resp.status_code, 'body': resp.text[:500]},
            )

    except Exception as exc:
        logger.exception('[MTN] R2P request failed: %s', exc)
        return GatewayResponse(
            success=False,
            reference=None,
            message=f'MTN MoMo : erreur — {exc}',
            raw_response={'error': str(exc), 'ts': _now()},
        )


def check_mtn_payment_status(reference_id: str) -> dict:
    """
    Poll the MTN MoMo API to check if a Request-to-Pay was approved.

    Returns dict with keys:
      status    'SUCCESSFUL' | 'FAILED' | 'PENDING' | 'error'
      reason    Failure reason (if FAILED)
      raw       Full API response
    """
    import requests as req

    sub_key, api_user, api_key, target_env = _mtn_credentials()
    if not all([sub_key, api_user, api_key]):
        return {'status': 'error', 'reason': 'not_configured', 'raw': {}}

    base  = _MTN_BASE_URLS.get(target_env, _MTN_BASE_URLS['sandbox'])
    token = _mtn_access_token(sub_key, api_user, api_key, base)
    if not token:
        return {'status': 'error', 'reason': 'token_fetch_failed', 'raw': {}}

    try:
        resp = req.get(
            f'{base}/collection/v1_0/requesttopay/{reference_id}',
            headers={
                'Authorization':            f'Bearer {token}',
                'X-Target-Environment':      target_env,
                'Ocp-Apim-Subscription-Key': sub_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            'status': data.get('status', 'PENDING'),
            'reason': data.get('reason', ''),
            'raw':    data,
        }
    except Exception as exc:
        logger.exception('[MTN] Status check failed: %s', exc)
        return {'status': 'error', 'reason': str(exc), 'raw': {}}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
