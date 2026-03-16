"""Security utilities for encryption and decryption.

This module provides utilities for encrypting/decrypting sensitive data
like GitLab Personal Access Tokens using AES-256-GCM AEAD encryption.

Encryption Algorithm: AES-256-GCM (Galois/Counter Mode)
- Industry-standard symmetric encryption (NIST approved, FIPS 140-2 compliant)
- AEAD (Authenticated Encryption with Associated Data)
- Hardware-accelerated on modern CPUs (AES-NI instructions)
- Used by: AWS KMS, Google Cloud KMS, Azure Key Vault, TLS 1.3 (majority), HTTPS
- Provides both confidentiality and authenticity
- 256-bit key size for maximum security

Compliance:
- NIST SP 800-38D approved
- FIPS 140-2 validated
- Required by: PCI-DSS, HIPAA, SOC 2, FedRAMP

For production: Integrate with HashiCorp Vault, AWS KMS, Google Cloud KMS,
or Azure Key Vault for key management and rotation.
"""

import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from api.context import get_current_app


class EncryptionError(Exception):
    """Raised when encryption/decryption fails."""

    pass


def get_encryptor() -> TokenEncryptor:
    """Get token encryptor from database plugin.

    Returns:
        TokenEncryptor instance

    Raises:
        RuntimeError: If database plugin not enabled or encryption key not configured
    """
    app = get_current_app()
    if not app.database:
        raise RuntimeError("Database plugin not enabled")

    encryption_key = app.database.get_encryption_key()
    if not encryption_key:
        raise RuntimeError("Encryption key not configured in database plugin")

    return TokenEncryptor(encryption_key)


class TokenEncryptor:
    """Handles encryption and decryption of sensitive tokens.

    Uses AES-256-GCM (AEAD) for industry-standard, hardware-accelerated,
    authenticated encryption. Automatically handles nonce generation and validation.
    """

    def __init__(self, encryption_key: str):
        """Initialize encryptor with encryption key.

        Args:
            encryption_key: 32-byte base64url-encoded key (256 bits)

        Raises:
            ValueError: If encryption_key is invalid format or size

        Example:
            >>> key = "WCG0dN_WKfmNvUBp4oV3jq1IhMY0jNoJCzuf1adYQtY="
            >>> encryptor = TokenEncryptor(key)
        """
        try:
            key_bytes = urlsafe_b64decode(encryption_key)
        except Exception as e:
            raise EncryptionError(f"Error while decoding encryption key: {e}") from e

        if len(key_bytes) != 32:
            raise EncryptionError(
                f"Encryption key must be exactly 32 bytes (256 bits) when decoded, got {len(key_bytes)} bytes. "
            )

        self.cipher = AESGCM(key_bytes)

    def encrypt(self, plaintext: str, associated_data: bytes | None = None) -> str:
        """Encrypt a plaintext string with AES-256-GCM.

        Args:
            plaintext: String to encrypt (e.g., GitLab PAT)
            associated_data: Optional additional authenticated data (not encrypted, but authenticated)

        Returns:
            Encrypted string in format: base64url(nonce || ciphertext || tag)
            The nonce is 12 bytes (96 bits), prepended to the ciphertext

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            # Generate random 96-bit (12-byte) nonce for AES-GCM
            nonce = secrets.token_bytes(12)

            # Encrypt and authenticate
            ciphertext = self.cipher.encrypt(nonce, plaintext.encode("utf-8"), associated_data)

            # Prepend nonce to ciphertext (nonce is not secret)
            encrypted_data = nonce + ciphertext

            # Return as base64url for safe storage
            return urlsafe_b64encode(encrypted_data).decode("utf-8")

        except Exception as e:
            raise EncryptionError(f"Failed to encrypt data: {e}") from e

    def decrypt(self, encrypted: str, associated_data: bytes | None = None) -> str:
        """Decrypt an encrypted string with AES-256-GCM.

        Args:
            encrypted: Encrypted string (base64url-encoded nonce || ciphertext || tag)
            associated_data: Optional additional authenticated data (must match encryption)

        Returns:
            Decrypted plaintext string

        Raises:
            EncryptionError: If decryption fails (wrong key, corrupted data, tampered data)
        """
        try:
            # Decode base64url
            encrypted_data = urlsafe_b64decode(encrypted)

            # Extract nonce (first 12 bytes) and ciphertext (rest)
            if len(encrypted_data) < 12:
                raise EncryptionError("Invalid encrypted data: too short")

            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]

            # Decrypt and verify authentication tag
            plaintext_bytes = self.cipher.decrypt(nonce, ciphertext, associated_data)

            return plaintext_bytes.decode("utf-8")

        except InvalidTag as e:
            raise EncryptionError(
                "Failed to decrypt data: Invalid authentication tag (wrong key or data tampered)"
            ) from e
        except Exception as e:
            raise EncryptionError(f"Failed to decrypt data: {e}") from e
