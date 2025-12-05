# backend/utils/jwt_deps.py
"""
JWT Dependencies for FastAPI routes.
PHASE 4: Unified JWT authentication (X-User-Id removed).
"""
from fastapi import Depends, HTTPException, status, Request
from typing import Optional

from ..middleware.jwt_auth import get_current_user_id, require_auth


async def get_current_user_id_dep(request: Request) -> str:
    """
    FastAPI dependency to get current user ID from JWT token.
    
    Use this in route handlers:
        @router.get("/endpoint")
        async def my_endpoint(user_id: str = Depends(get_current_user_id_dep)):
            ...
    
    Raises:
        HTTPException: 401 if JWT token is missing or invalid
    """
    user_id = await get_current_user_id(request)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid JWT token in the Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


async def get_current_user_id_optional(request: Request) -> Optional[str]:
    """
    FastAPI dependency to get current user ID from JWT token (optional).
    
    Use this for endpoints that work with or without authentication.
    """
    return await get_current_user_id(request)

