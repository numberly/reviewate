"""Tests for security/encryption utilities."""

import secrets
from base64 import urlsafe_b64encode

import pytest

from api.security import EncryptionError, TokenEncryptor


def test_encrypt_decrypt_basic(generate_encryption_key: str):
    """Test basic encryption and decryption."""
    encryptor = TokenEncryptor(generate_encryption_key)

    plaintext = "glpat-xxxxxxxxxxxxxxxxxxxx"  # Mock GitLab PAT

    # Encrypt
    encrypted = encryptor.encrypt(plaintext)
    assert isinstance(encrypted, str)
    assert encrypted != plaintext  # Should be different
    assert len(encrypted) > len(plaintext)  # Should be longer (nonce + ciphertext + tag)

    # Decrypt
    decrypted = encryptor.decrypt(encrypted)
    assert decrypted == plaintext


def test_encrypt_decrypt_with_unicode(generate_encryption_key: str):
    """Test encryption with unicode characters."""
    encryptor = TokenEncryptor(generate_encryption_key)

    plaintext = "Hello 世界 🔐 Encryption!"

    encrypted = encryptor.encrypt(plaintext)
    decrypted = encryptor.decrypt(encrypted)

    assert decrypted == plaintext


def test_decrypt_with_wrong_key(generate_encryption_key: str):
    """Test that decryption fails with wrong key."""
    key2 = urlsafe_b64encode(secrets.token_bytes(32)).decode()

    encryptor1 = TokenEncryptor(generate_encryption_key)
    encryptor2 = TokenEncryptor(key2)

    plaintext = "secret-data"
    encrypted = encryptor1.encrypt(plaintext)

    # Try to decrypt with different key
    with pytest.raises(EncryptionError, match="Invalid authentication tag"):
        encryptor2.decrypt(encrypted)


def test_decrypt_tampered_data(generate_encryption_key: str):
    """Test that decryption fails with tampered data."""
    encryptor = TokenEncryptor(generate_encryption_key)

    plaintext = "important-token"
    encrypted = encryptor.encrypt(plaintext)

    # Tamper with encrypted data (modify one character)
    tampered = encrypted[:-1] + ("A" if encrypted[-1] != "A" else "B")

    # Should fail authentication check
    with pytest.raises(EncryptionError):
        encryptor.decrypt(tampered)


@pytest.mark.parametrize(
    "invalid_key",
    [
        "not-valid-base64!!!",
        "",
        urlsafe_b64encode(b"short").decode(),
        urlsafe_b64encode(secrets.token_bytes(64)).decode(),
    ],
)
def test_invalid_key_format(invalid_key: str):
    """Test that invalid key format raises EncryptionError."""
    with pytest.raises(EncryptionError):
        TokenEncryptor(invalid_key)


def test_nonce_uniqueness(generate_encryption_key: str):
    """Test that encrypting same plaintext twice produces different ciphertext (due to random nonce)."""
    encryptor = TokenEncryptor(generate_encryption_key)

    plaintext = "same-data"

    encrypted1 = encryptor.encrypt(plaintext)
    encrypted2 = encryptor.encrypt(plaintext)

    # Ciphertexts should be different (different nonces)
    assert encrypted1 != encrypted2

    # But both should decrypt to same plaintext
    assert encryptor.decrypt(encrypted1) == plaintext
    assert encryptor.decrypt(encrypted2) == plaintext
