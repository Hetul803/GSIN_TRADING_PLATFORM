# backend/middleware/request_signing.py
"""
PHASE 6: Request Signing Middleware
Validates HMAC signatures for critical endpoints.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import Message
from typing import Callable
import json

from ..utils.request_signing import (
    CRITICAL_ENDPOINTS,
    verify_signature,
    extract_payload_from_request
)


class RequestSigningMiddleware(BaseHTTPMiddleware):
    """
    Validates request signatures for critical endpoints.
    Requires X-Signature header for POST/PUT/PATCH requests to critical endpoints.
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Skip OPTIONS requests (CORS preflight) and other non-modifying methods
        if request.method in ["OPTIONS", "GET", "HEAD", "DELETE"]:
            return await call_next(request)
        
        # Only check POST, PUT, PATCH requests
        if request.method not in ["POST", "PUT", "PATCH"]:
            return await call_next(request)
        
        # Check if endpoint requires signing
        path = request.url.path
        requires_signing = any(
            path.startswith(endpoint) for endpoint in CRITICAL_ENDPOINTS
        )
        
        if not requires_signing:
            return await call_next(request)
        
        # Get signature from header
        signature = request.headers.get("X-Signature")
        if not signature:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Request signature required. Include X-Signature header."
                }
            )
        
        # Read request body
        body = await request.body()
        
        # Verify signature
        try:
            payload = extract_payload_from_request(body)
            if not verify_signature(payload, signature):
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": "Invalid request signature."
                    }
                )
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": f"Signature verification failed: {str(e)}"
                }
            )
        
        # Recreate request with body (since we consumed it)
        async def receive() -> Message:
            return {"type": "http.request", "body": body}
        
        request._receive = receive
        
        return await call_next(request)

