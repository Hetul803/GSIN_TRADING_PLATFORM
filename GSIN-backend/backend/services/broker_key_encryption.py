# backend/services/broker_key_encryption.py
"""
PHASE 6: Broker API Key Encryption Service
Encrypts and stores user broker API keys using Fernet encryption.
Supports key rotation.
"""

import os
from typing import Optional
from pathlib import Path
from dotenv import dotenv_values
from cryptography.fernet import Fernet
import base64


class BrokerKeyEncryption:
    """
    Service for encrypting and decrypting broker API keys.
    Uses Fernet (symmetric encryption) with key derivation.
    """
    
    def __init__(self):
        self._cipher: Optional[Fernet] = None
        self._initialize_cipher()
    
    def _initialize_cipher(self):
        """Initialize Fernet cipher with key from environment or generate new one."""
        # Load from config/.env or environment variable
        # Go up from backend/services/broker_key_encryption.py -> backend/services -> backend -> GSIN-backend -> gsin_new_git (repo root)
        CFG_PATH = Path(__file__).resolve().parents[3] / "config" / ".env"
        cfg = {}
        if CFG_PATH.exists():
            cfg = dotenv_values(str(CFG_PATH))
            # Validate that we got a real key, not placeholder
            key_from_file = cfg.get("BROKER_ENCRYPTION_KEY", "")
            if key_from_file and ("your-" in key_from_file.lower() or len(key_from_file) < 32):
                # Invalid placeholder, ignore this file
                cfg = {}
        
        # Get encryption key from environment or config file
        encryption_key = os.getenv("BROKER_ENCRYPTION_KEY") or cfg.get("BROKER_ENCRYPTION_KEY")
        
        if not encryption_key:
            # Generate a new key (should be set in production)
            key = Fernet.generate_key()
            print(f"⚠️  WARNING: Generated new encryption key. Set BROKER_ENCRYPTION_KEY={key.decode()}")
            self._cipher = Fernet(key)
        else:
            # Use existing key - validate and convert if needed
            try:
                # Try to use the key as-is (should be base64-encoded)
                if isinstance(encryption_key, str):
                    # Check if it's a hex string (64 chars = 32 bytes in hex)
                    if len(encryption_key) == 64 and all(c in '0123456789abcdefABCDEF' for c in encryption_key):
                        # Convert hex to bytes, then to base64
                        key_bytes = bytes.fromhex(encryption_key)
                        key = base64.urlsafe_b64encode(key_bytes)
                    else:
                        # Assume it's already base64-encoded
                        key = encryption_key.encode() if isinstance(encryption_key, str) else encryption_key
                else:
                    key = encryption_key
                
                # Validate the key format
                self._cipher = Fernet(key)
            except (ValueError, TypeError) as e:
                # Key is invalid, generate a new one
                print(f"⚠️  WARNING: Invalid encryption key format. Generating new key. Error: {e}")
                key = Fernet.generate_key()
                print(f"⚠️  WARNING: Generated new encryption key. Set BROKER_ENCRYPTION_KEY={key.decode()}")
                self._cipher = Fernet(key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string (e.g., API key).
        
        Args:
            plaintext: The string to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        if not self._cipher:
            raise ValueError("Encryption cipher not initialized")
        
        encrypted = self._cipher.encrypt(plaintext.encode('utf-8'))
        return base64.b64encode(encrypted).decode('utf-8')
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.
        
        Args:
            ciphertext: Base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string
        """
        if not self._cipher:
            raise ValueError("Encryption cipher not initialized")
        
        try:
            encrypted_bytes = base64.b64decode(ciphertext.encode('utf-8'))
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")
    
    def rotate_key(self, old_key: str, new_key: str, encrypted_data: str) -> str:
        """
        Rotate encryption key (re-encrypt with new key).
        
        Args:
            old_key: Old encryption key
            new_key: New encryption key
            encrypted_data: Data encrypted with old key
            
        Returns:
            Data encrypted with new key
        """
        # Decrypt with old key
        old_cipher = Fernet(old_key.encode() if isinstance(old_key, str) else old_key)
        decrypted = old_cipher.decrypt(base64.b64decode(encrypted_data.encode('utf-8')))
        
        # Encrypt with new key
        new_cipher = Fernet(new_key.encode() if isinstance(new_key, str) else new_key)
        encrypted = new_cipher.encrypt(decrypted)
        return base64.b64encode(encrypted).decode('utf-8')
    
    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet key."""
        return Fernet.generate_key().decode('utf-8')


# Global instance
broker_key_encryption = BrokerKeyEncryption()

