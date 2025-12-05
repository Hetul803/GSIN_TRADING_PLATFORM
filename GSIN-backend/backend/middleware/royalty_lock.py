# backend/middleware/royalty_lock.py
"""
PHASE 4: Middleware to enforce hard lock for users with unpaid royalties.
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Callable

from ..services.royalty_billing import royalty_billing_service
from ..db.session import get_db
from ..utils.jwt_deps import get_current_user_id_dep


class RoyaltyLockMiddleware(BaseHTTPMiddleware):
    """
    Middleware that blocks access for users with unpaid royalties above threshold.
    
    Hard lock is applied if:
    - User has unpaid royalties >= $10
    - User is trying to access premium features (not basic read-only endpoints)
    """
    
    # Endpoints that are exempt from royalty lock (basic read-only)
    EXEMPT_PATHS = [
        "/api/health",
        "/api/metrics",
        "/api/users/me",
        "/api/royalties/billing/status",  # Allow checking status
        "/api/royalties/billing/process",  # Allow processing payment
        "/api/notifications",  # Allow checking notifications
        "/api/subscriptions",  # Allow subscription management
    ]
    
    # Premium features that require payment
    PREMIUM_PATHS = [
        "/api/broker/place-order",
        "/api/broker/close-position",
        "/api/strategies/create",
        "/api/strategies/backtest",
        "/api/brain/recommended-strategies",
    ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Check if user should be locked out due to unpaid royalties.
        """
        # Skip lock check for exempt paths
        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            return await call_next(request)
        
        # Only check lock for premium features
        is_premium = any(request.url.path.startswith(path) for path in self.PREMIUM_PATHS)
        if not is_premium:
            return await call_next(request)
        
        # Try to get user_id from request state (set by JWT middleware)
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            # If no user_id, let JWT middleware handle auth
            return await call_next(request)
        
        # Check payment status
        try:
            from ..db.session import SessionLocal
            db = SessionLocal()
            try:
                payment_status = royalty_billing_service.check_payment_status(user_id, db)
                
                if payment_status["should_lock"]:
                    # Return 402 Payment Required response
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        content={
                            "error": "Payment required",
                            "message": f"You have outstanding royalties of ${payment_status['outstanding_amount']:.2f}. "
                                      f"Please pay your outstanding balance to continue using premium features.",
                            "outstanding_amount": payment_status["outstanding_amount"],
                            "lock_threshold": payment_status["lock_threshold"],
                            "payment_url": "/api/royalties/billing/process"
                        }
                    )
            finally:
                db.close()
        except Exception as e:
            # If check fails, log but don't block (fail open for now)
            print(f"⚠️  Royalty lock check failed: {e}")
            pass
        
        return await call_next(request)

