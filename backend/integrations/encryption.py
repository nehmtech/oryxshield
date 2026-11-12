"""
Fernet-based credential encryption for integration credentials.

Uses the FIELD_ENCRYPTION_KEY setting (from .env).
Falls back to plaintext storage with a warning if the key is not set.

Generate a key:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Usage on the model:
    from .encryption import encrypt_credentials, decrypt_credentials

    # Store
    instance.credentials = encrypt_credentials({'api_key': 'secret'})
    instance.save()

    # Retrieve
    plain = decrypt_credentials(instance.credentials)
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Sentinel prefix written into the stored value so we can tell encrypted from plaintext
_ENC_PREFIX = "fernet:"


def _get_fernet():
    """Return a Fernet instance or None if the key is not configured."""
    key = getattr(settings, 'FIELD_ENCRYPTION_KEY', '') or ''
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        logger.error("FIELD_ENCRYPTION_KEY is invalid: %s", exc)
        return None


def encrypt_credentials(data: dict) -> dict:
    """
    Encrypt a credentials dict.

    Returns {"_enc": "<fernet-token>"} when key is configured.
    Returns the original dict with a warning when key is missing.
    """
    if not data:
        return data

    fernet = _get_fernet()
    if fernet is None:
        logger.warning(
            "FIELD_ENCRYPTION_KEY not set — integration credentials stored as plaintext. "
            "Set this key in .env before storing real API credentials in production."
        )
        return data

    try:
        plaintext = json.dumps(data, ensure_ascii=False).encode()
        token = fernet.encrypt(plaintext).decode()
        return {"_enc": _ENC_PREFIX + token}
    except Exception as exc:
        logger.error("Credential encryption failed: %s", exc)
        return data


def decrypt_credentials(stored: dict) -> dict:
    """
    Decrypt a credentials dict produced by encrypt_credentials().

    Returns the original plaintext dict.
    Returns the stored dict as-is if it was never encrypted.
    """
    if not stored:
        return stored or {}

    enc_blob = stored.get("_enc", "")
    if not enc_blob:
        # Plaintext (unencrypted legacy data) — return as-is
        return stored

    if not enc_blob.startswith(_ENC_PREFIX):
        return stored

    fernet = _get_fernet()
    if fernet is None:
        logger.error(
            "Cannot decrypt credentials — FIELD_ENCRYPTION_KEY is not set. "
            "Integration will not be able to authenticate."
        )
        return {}

    try:
        token = enc_blob[len(_ENC_PREFIX):]
        plaintext = fernet.decrypt(token.encode())
        return json.loads(plaintext)
    except Exception as exc:
        logger.error("Credential decryption failed: %s", exc)
        return {}


def is_encrypted(stored: dict) -> bool:
    """Return True if the stored value is Fernet-encrypted."""
    if not isinstance(stored, dict):
        return False
    enc_blob = stored.get("_enc", "")
    return isinstance(enc_blob, str) and enc_blob.startswith(_ENC_PREFIX)
