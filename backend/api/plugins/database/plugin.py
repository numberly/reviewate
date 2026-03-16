"""Database plugin - SQLAlchemy engine management."""

import base64
import os
from collections.abc import Generator
from contextlib import contextmanager

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.plugins.database.config import DatabasePluginConfig
from api.plugins.plugin import BasePlugin


class DatabasePlugin(BasePlugin[DatabasePluginConfig]):
    """Database plugin managing SQLAlchemy engine and sessions.

    This plugin creates and manages the database engine lifecycle.
    """

    plugin_name = "database"
    config_class = DatabasePluginConfig
    priority = 10

    def __init__(self, plugin_config: DatabasePluginConfig):
        """Initialize database plugin.

        Args:
            plugin_config: Database plugin configuration
        """
        self.config = plugin_config
        self.engine: Engine | None = None
        self.SessionLocal: sessionmaker[Session] | None = None

    async def startup(self) -> None:
        """Initialize the database engine."""
        self.engine = create_engine(
            self.config.url,
            echo=self.config.echo,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
            pool_pre_ping=True,  # Verify connections before using
        )

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

    async def shutdown(self) -> None:
        """Dispose the database engine."""
        if self.engine:
            self.engine.dispose()
            self.engine = None
            self.SessionLocal = None

    def get_session(self) -> Session:
        """Get a new database session.

        Returns:
            Database session

        Raises:
            RuntimeError: If plugin not started
        """
        if not self.SessionLocal:
            raise RuntimeError("DatabasePlugin not started")
        return self.SessionLocal()

    @contextmanager
    def session(self) -> Generator[Session]:
        """Context manager for database sessions.

        Yields:
            Database session

        Raises:
            RuntimeError: If plugin not started

        Example:
            with app.database.session() as db:
                user = db.query(User).first()
        """
        db = self.get_session()
        try:
            yield db
        finally:
            db.close()

    def get_encryption_key(self) -> str | None:
        """Get the encryption key for securing sensitive data.

        Returns:
            Base64url-encoded 256-bit encryption key, or None if not configured
        """
        return self.config.encryption_key

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string using AES-256-GCM.

        Args:
            plaintext: String to encrypt

        Returns:
            Base64-encoded encrypted string (nonce + ciphertext)

        Raises:
            RuntimeError: If encryption key not configured
        """
        key = self.config.encryption_key
        if not key:
            raise RuntimeError("Encryption key not configured")

        # Decode the base64 key
        key_bytes = base64.urlsafe_b64decode(key)
        aesgcm = AESGCM(key_bytes)

        # Generate random nonce (12 bytes for GCM)
        nonce = os.urandom(12)

        # Encrypt
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

        # Return nonce + ciphertext as base64
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")

    def decrypt(self, encrypted: str) -> str:
        """Decrypt an AES-256-GCM encrypted string.

        Args:
            encrypted: Base64-encoded encrypted string (nonce + ciphertext)

        Returns:
            Decrypted plaintext string

        Raises:
            RuntimeError: If encryption key not configured
        """
        key = self.config.encryption_key
        if not key:
            raise RuntimeError("Encryption key not configured")

        # Decode the base64 key
        key_bytes = base64.urlsafe_b64decode(key)
        aesgcm = AESGCM(key_bytes)

        # Decode the encrypted data
        data = base64.urlsafe_b64decode(encrypted)

        # Split nonce and ciphertext (nonce is first 12 bytes)
        nonce = data[:12]
        ciphertext = data[12:]

        # Decrypt
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
