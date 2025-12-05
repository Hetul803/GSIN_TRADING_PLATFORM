# backend/api/system.py
"""
System health check and status endpoints.
"""
from fastapi import APIRouter, Depends
from typing import Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..utils.jwt_deps import get_current_user_id_optional
from ..market_data.market_data_provider import get_provider_with_fallback

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health-check")
async def health_check(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id_optional)
) -> Dict[str, Any]:
    """
    PHASE 6: System health check endpoint.
    
    Returns:
        {
            "status": "ok" | "degraded" | "down",
            "timestamp": str,
            "services": {
                "database": "ok" | "down",
                "market_data": "ok" | "degraded" | "down",
                "evolution_worker": "ok" | "unknown"
            },
            "details": {
                "database": {...},
                "market_data": {...},
                "evolution_worker": {...}
            }
        }
    """
    status = "ok"
    services: Dict[str, str] = {}
    details: Dict[str, Any] = {}
    
    # Check database
    try:
        db.execute("SELECT 1")
        services["database"] = "ok"
        details["database"] = {"status": "ok", "message": "Database connection healthy"}
    except Exception as e:
        services["database"] = "down"
        details["database"] = {"status": "down", "error": str(e)}
        status = "down"
    
    # Check market data provider
    try:
        provider = get_provider_with_fallback()
        if provider:
            # Try to get a test price
            try:
                test_price = provider.get_price("AAPL")
                if test_price and test_price.price:
                    services["market_data"] = "ok"
                    details["market_data"] = {
                        "status": "ok",
                        "provider": provider.__class__.__name__,
                        "test_symbol": "AAPL",
                        "test_price": test_price.price
                    }
                else:
                    services["market_data"] = "degraded"
                    details["market_data"] = {
                        "status": "degraded",
                        "provider": provider.__class__.__name__,
                        "message": "Provider available but returned no data"
                    }
                    if status == "ok":
                        status = "degraded"
            except Exception as e:
                services["market_data"] = "degraded"
                details["market_data"] = {
                    "status": "degraded",
                    "provider": provider.__class__.__name__,
                    "error": str(e)
                }
                if status == "ok":
                    status = "degraded"
        else:
            services["market_data"] = "down"
            details["market_data"] = {
                "status": "down",
                "message": "No market data provider available"
            }
            if status == "ok":
                status = "degraded"
    except Exception as e:
        services["market_data"] = "down"
        details["market_data"] = {"status": "down", "error": str(e)}
        if status == "ok":
            status = "degraded"
    
    # Check evolution worker (simplified - would need worker heartbeat tracking)
    services["evolution_worker"] = "unknown"
    details["evolution_worker"] = {
        "status": "unknown",
        "message": "Worker status not tracked (would need heartbeat mechanism)"
    }
    
    return {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "services": services,
        "details": details
    }
