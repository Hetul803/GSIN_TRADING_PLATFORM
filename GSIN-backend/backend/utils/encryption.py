# backend/utils/encryption.py
"""
Simple encryption utility for group messages.
Note: This is a basic implementation. For production, consider:
- Using a proper encryption library (e.g., cryptography with Fernet)
- Key management system (AWS KMS, HashiCorp Vault, etc.)
- End-to-end encryption with per-group keys
- Key rotation policies
"""
import base64
import os
from typing import Optional

# For now, use a simple XOR cipher with a secret key
# In production, use proper encryption (AES-256-GCM, etc.)
SECRET_KEY = os.environ.get("ENCRYPTION_SECRET_KEY", "gsin-default-secret-key-change-in-production")

def encrypt_message(message: str, key: Optional[str] = None) -> str:
    """
    Encrypt a message using a simple XOR cipher.
    In production, replace with proper encryption (AES-256-GCM).
    
    Args:
        message: Plain text message to encrypt
        key: Optional encryption key (defaults to SECRET_KEY)
    
    Returns:
        Base64-encoded encrypted message
    """
    if not message:
        return ""
    
    encryption_key = (key or SECRET_KEY).encode('utf-8')
    message_bytes = message.encode('utf-8')
    
    # Simple XOR encryption (for demo purposes)
    # In production, use: from cryptography.fernet import Fernet
    encrypted = bytearray()
    for i, byte in enumerate(message_bytes):
        encrypted.append(byte ^ encryption_key[i % len(encryption_key)])
    
    # Return base64-encoded string
    return base64.b64encode(bytes(encrypted)).decode('utf-8')

def decrypt_message(encrypted_message: str, key: Optional[str] = None) -> str:
    """
    Decrypt a message using XOR cipher.
    In production, replace with proper decryption.
    
    Args:
        encrypted_message: Base64-encoded encrypted message
        key: Optional decryption key (defaults to SECRET_KEY)
    
    Returns:
        Decrypted plain text message
    """
    if not encrypted_message:
        return ""
    
    try:
        encryption_key = (key or SECRET_KEY).encode('utf-8')
        encrypted_bytes = base64.b64decode(encrypted_message.encode('utf-8'))
        
        # Simple XOR decryption (symmetric)
        decrypted = bytearray()
        for i, byte in enumerate(encrypted_bytes):
            decrypted.append(byte ^ encryption_key[i % len(encryption_key)])
        
        return bytes(decrypted).decode('utf-8')
    except Exception as e:
        # If decryption fails, return error message
        return f"[Decryption Error: {str(e)}]"

