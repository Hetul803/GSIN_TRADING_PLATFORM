# backend/middleware/jwt_auth.py
"""
JWT Authentication Middleware.
Replaces X-User-Id header with proper JWT token verification.
"""
from fastapi import HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from typing import Optional

from ..services.jwt_service import jwt_service


security = HTTPBearer(auto_error=False)


async def get_current_user_id(request: Request) -> Optional[str]:
    """
    Get current user ID from JWT token.
    
    PHASE 4: JWT-only authentication (X-User-Id removed).
    """
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None
    
    try:
        # Extract token from "Bearer <token>"
        if authorization.startswith("Bearer "):
            token = authorization[7:]
            payload = jwt_service.verify_token(token)
            if payload:
                user_id = payload.get("sub")
                if user_id:
                    return user_id
    except Exception:
        pass
    
    return None


async def require_auth(request: Request) -> str:
    """
    Require authentication and return user ID.
    Raises HTTPException if not authenticated.
    
    PHASE 4: JWT-only authentication.
    """
    user_id = await get_current_user_id(request)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid JWT token in the Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and validate JWT tokens.
    Adds user_id to request.state for easy access.
    """
    
    async def dispatch(self, request: StarletteRequest, call_next):
        # Skip JWT extraction for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Extract user ID from JWT or header
        user_id = await get_current_user_id(request)
        
        # Add to request state
        request.state.user_id = user_id
        
        # Continue with request
        response = await call_next(request)
        return response

