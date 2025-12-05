# backend/utils/request_signing.py
"""
PHASE 6: Request Signing Utility
HMAC-SHA256 request signing for critical endpoints.
"""

import hmac
import hashlib
import base64
import json
from typing import Optional, Dict, Any
import os


def get_signing_secret() -> str:
    """Get the signing secret from environment."""
    secret = os.getenv("REQUEST_SIGNING_SECRET")
    if not secret:
        raise ValueError("REQUEST_SIGNING_SECRET environment variable not set")
    return secret


def sign_payload(payload: Dict[str, Any] | str) -> str:
    """
    Sign a payload using HMAC-SHA256.
    
    Args:
        payload: Dictionary or JSON string to sign
        
    Returns:
        Base64-encoded signature
    """
    secret = get_signing_secret()
    
    # Convert payload to JSON string if it's a dict
    if isinstance(payload, dict):
        payload_str = json.dumps(payload, sort_keys=True)
    else:
        payload_str = payload
    
    # Create HMAC signature
    signature = hmac.new(
        secret.encode('utf-8'),
        payload_str.encode('utf-8'),
        hashlib.sha256
    ).digest()
    
    # Return base64-encoded signature
    return base64.b64encode(signature).decode('utf-8')


def verify_signature(payload: Dict[str, Any] | str, signature: str) -> bool:
    """
    Verify a request signature.
    
    Args:
        payload: Original payload
        signature: Signature to verify
        
    Returns:
        True if signature is valid
    """
    try:
        expected_signature = sign_payload(payload)
        return hmac.compare_digest(expected_signature, signature)
    except Exception:
        return False


def extract_payload_from_request(request_body: bytes) -> Dict[str, Any]:
    """Extract and parse JSON payload from request body."""
    try:
        return json.loads(request_body.decode('utf-8'))
    except json.JSONDecodeError:
        return {}


# Critical endpoints that require signing
CRITICAL_ENDPOINTS = [
    "/api/broker/place-order",
    "/api/brain/signal",
    "/api/strategies",
    "/api/strategies/upload",
]

