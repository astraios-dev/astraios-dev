"""
Fernet symmetric encryption for API keys stored in the database.
Keys are encrypted on save and decrypted on read in bybit.py.

If FERNET_KEY is not set, values are stored/returned as-is (dev fallback).
Generate a key once with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from cryptography.fernet import Fernet, InvalidToken
from api.config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet | None:
    global _fernet
    if _fernet is None and settings.fernet_key:
        _fernet = Fernet(settings.fernet_key.encode())
    return _fernet


def encrypt_key(value: str | None) -> str | None:
    if not value:
        return value
    f = _get_fernet()
    if f is None:
        return value
    return f.encrypt(value.encode()).decode()


def decrypt_key(value: str | None) -> str | None:
    if not value:
        return value
    f = _get_fernet()
    if f is None:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        return value
