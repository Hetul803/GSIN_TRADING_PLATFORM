# backend/services/jwt_service.py
"""
JWT token service for generating and verifying authentication tokens.
"""
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from pathlib import Path
from dotenv import dotenv_values

CFG_PATH = Path(__file__).resolve().parents[2] / "config" / ".env"
cfg = dotenv_values(str(CFG_PATH)) if CFG_PATH.exists() else {}

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY") or cfg.get("JWT_SECRET_KEY") or "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7  # 7 days


class JWTService:
    """Service for JWT token generation and verification"""
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token.
        
        Args:
            data: Dictionary containing user data (e.g., {"sub": user_id, "email": email})
            expires_delta: Optional expiration time delta
        
        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        
        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token.
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None
    
    @staticmethod
    def get_user_id_from_token(token: str) -> Optional[str]:
        """
        Extract user ID from JWT token.
        
        Args:
            token: JWT token string
        
        Returns:
            User ID if token is valid, None otherwise
        """
        payload = JWTService.verify_token(token)
        if payload:
            return payload.get("sub")  # "sub" is the standard JWT claim for subject (user ID)
        return None


# Global instance
jwt_service = JWTService()

