"""
Token Encryption Utility
Encrypts OAuth tokens at rest in PostgreSQL.

Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).
Key derived from TOKEN_ENCRYPTION_KEY env var (required in production).

Usage:
    from app.utils.token_encryption import encrypt_token, decrypt_token

    encrypted = encrypt_token(refresh_token)
    plaintext = decrypt_token(encrypted)
"""

import base64
import hashlib
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

_PREFIX = "enc:v1:"  # Version prefix for future key rotation


@lru_cache
def _get_fernet():
    """Lazy-init Fernet cipher from environment key."""
    raw_key = os.getenv("TOKEN_ENCRYPTION_KEY", "")
    if not raw_key:
        logger.warning(
            "TOKEN_ENCRYPTION_KEY not set — tokens stored in plaintext. "
            "Set this env var for production encryption."
        )
        return None

    try:
        from cryptography.fernet import Fernet

        # Derive a valid Fernet key (32 url-safe base64-encoded bytes)
        key_hash = hashlib.sha256(raw_key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_hash)
        return Fernet(fernet_key)
    except ImportError:
        logger.warning(
            "cryptography package not installed — "
            "run `pip install cryptography` for token encryption"
        )
        return None
    except Exception as e:
        logger.exception(f"Failed to initialize Fernet cipher: {e}")
        return None


def encrypt_token(plaintext: str | None) -> str | None:
    """
    Encrypt a token for storage.
    Returns prefixed ciphertext, or None if plaintext is None/empty.
    Falls back to plaintext if encryption is not configured.
    """
    if not plaintext:
        return plaintext

    # Already encrypted?
    if plaintext.startswith(_PREFIX):
        return plaintext

    fernet = _get_fernet()
    if fernet is None:
        # Encryption not configured — store with prefix to mark as unencrypted
        # (allows future migration without breaking existing data)
        return plaintext

    try:
        encrypted = fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        return f"{_PREFIX}{encrypted}"
    except Exception as e:
        logger.exception(f"Token encryption failed: {e}")
        # Fail open — store plaintext rather than losing the token
        return plaintext


def decrypt_token(ciphertext: str | None) -> str | None:
    """
    Decrypt a stored token.
    Handles both encrypted (prefix) and legacy plaintext tokens.
    """
    if not ciphertext:
        return ciphertext

    # Not encrypted — legacy plaintext
    if not ciphertext.startswith(_PREFIX):
        return ciphertext

    fernet = _get_fernet()
    if fernet is None:
        logger.error(
            "TOKEN_ENCRYPTION_KEY not set but token is encrypted. "
            "Cannot decrypt without the key."
        )
        return None

    try:
        raw = ciphertext[len(_PREFIX):]
        return fernet.decrypt(raw.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.exception(f"Token decryption failed: {e}")
        return None


def is_encrypted(value: str | None) -> bool:
    """Check if a value is already encrypted."""
    return bool(value and value.startswith(_PREFIX))


def migrate_plaintext_tokens():
    """
    One-time migration: encrypt any plaintext tokens in the DB.
    Run manually or on startup after TOKEN_ENCRYPTION_KEY is set.
    """
    fernet = _get_fernet()
    if fernet is None:
        logger.info("Token encryption not configured — skipping migration")
        return {"migrated": 0, "skipped": 0}

    from app.database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, google_access_token, google_refresh_token "
            "FROM users WHERE google_refresh_token IS NOT NULL"
        )
        users = cur.fetchall()
        migrated = 0
        skipped = 0

        for row in users:
            uid = row[0]
            access_token = row[1]
            refresh_token = row[2]

            # Skip already-encrypted tokens
            if is_encrypted(refresh_token):
                skipped += 1
                continue

            enc_access = encrypt_token(access_token)
            enc_refresh = encrypt_token(refresh_token)

            cur.execute(
                "UPDATE users SET google_access_token = %s, google_refresh_token = %s WHERE id = %s",
                (enc_access, enc_refresh, uid),
            )
            migrated += 1
            logger.info(f"Migrated tokens for user {uid}")

        conn.commit()
        logger.info(f"Token migration complete: {migrated} migrated, {skipped} skipped")
        return {"migrated": migrated, "skipped": skipped}
    except Exception as e:
        conn.rollback()
        logger.exception(f"Token migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()
