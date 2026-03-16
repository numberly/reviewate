import secrets
from base64 import urlsafe_b64encode

import pytest


@pytest.fixture(scope="function")
def generate_encryption_key() -> str:
    """Generate a secure 32-byte (256-bit) encryption key for AES-256-GCM."""
    return urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8")
