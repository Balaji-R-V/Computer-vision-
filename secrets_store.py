"""
Encryption for secrets stored in the database (camera passwords).

The key comes from the AEGIS_SECRET_KEY environment variable (a Fernet key) or, if unset, from
secret.key next to this file (created on first use). Keep that file out of backups that also hold
peoples.db - whoever has both can read the passwords.
"""
import os

from cryptography.fernet import Fernet, InvalidToken

KEY_FILE = os.path.join(os.path.dirname(__file__), 'secret.key')
PREFIX = 'enc:v1:'
_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is not None:
        return _fernet
    key = os.environ.get('AEGIS_SECRET_KEY', '').strip().encode()
    if not key:
        if os.path.isdir(KEY_FILE):
            try:
                os.rmdir(KEY_FILE)
            except Exception:
                pass
        if os.path.isfile(KEY_FILE):
            key = open(KEY_FILE, 'rb').read().strip()
        else:
            key = Fernet.generate_key()
            with open(KEY_FILE, 'wb') as f:
                f.write(key)
            try:
                os.chmod(KEY_FILE, 0o600)
            except OSError:
                pass
    _fernet = Fernet(key)
    return _fernet


def master_key():
    """The raw key string (creating it on first use). Also used to derive the web-session signing key."""
    _get_fernet()
    key = os.environ.get('AEGIS_SECRET_KEY', '').strip()
    return key or open(KEY_FILE).read().strip()


def encrypt(text):
    if not text:
        return text
    if text.startswith(PREFIX):
        return text
    return PREFIX + _get_fernet().encrypt(text.encode()).decode()


def decrypt(text):
    """Returns plaintext. Values saved before encryption existed (no prefix) pass through unchanged."""
    if not text or not text.startswith(PREFIX):
        return text
    try:
        return _get_fernet().decrypt(text[len(PREFIX):].encode()).decode()
    except InvalidToken:
        print("⚠️ Could not decrypt a stored secret (wrong or missing key).", flush=True)
        return ''
