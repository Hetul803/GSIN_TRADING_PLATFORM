# backend/utils/auth.py
"""
Password hashing and verification utilities.
Passwords are NEVER stored in plain text - only bcrypt hashes.
"""
import bcrypt

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    Returns the hashed password string (bcrypt hash).
    """
    # Generate salt and hash password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    Returns True if password matches, False otherwise.
    """
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

