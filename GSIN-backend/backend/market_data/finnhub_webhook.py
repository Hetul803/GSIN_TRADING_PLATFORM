# backend/market_data/finnhub_webhook.py
"""
Finnhub Webhook Handler
Handles webhook events from Finnhub.io for real-time market data updates.
"""
import os
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException, status, Header
from typing import Optional
import json

router = APIRouter(prefix="/market/finnhub", tags=["finnhub-webhook"])

# Load webhook secret from environment
FINNHUB_WEBHOOK_SECRET = os.getenv("FINNHUB_WEBHOOK_SECRET", "d0jmr9pr01qjm8s24jb0")


def verify_finnhub_webhook(payload: bytes, signature: str) -> bool:
    """
    Verify Finnhub webhook signature.
    
    Args:
        payload: Raw request body
        signature: X-Finnhub-Signature header value
    
    Returns:
        True if signature is valid, False otherwise
    """
    if not FINNHUB_WEBHOOK_SECRET:
        return False  # No secret configured, reject
    
    # Finnhub uses HMAC-SHA256
    expected_signature = hmac.new(
        FINNHUB_WEBHOOK_SECRET.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


@router.post("/webhook")
async def finnhub_webhook(
    request: Request,
    x_finnhub_signature: Optional[str] = Header(None, alias="X-Finnhub-Signature")
):
    """
    Handle Finnhub webhook events.
    
    Webhook URL to configure in Finnhub dashboard:
    - Production: https://your-domain.com/api/market/finnhub/webhook
    - Development: http://localhost:8000/api/market/finnhub/webhook
    """
    # Get raw body for signature verification
    body = await request.body()
    
    # Verify signature if provided
    if x_finnhub_signature:
        if not verify_finnhub_webhook(body, x_finnhub_signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
    
    try:
        # Parse webhook payload
        payload = json.loads(body.decode('utf-8'))
        
        # Process webhook event
        event_type = payload.get("type")
        data = payload.get("data", {})
        
        # Handle different event types
        if event_type == "trade":
            # Real-time trade update
            symbol = data.get("s")
            price = data.get("p")
            volume = data.get("v")
            timestamp = data.get("t")
            
            # TODO: Broadcast to WebSocket clients subscribed to this symbol
            # from ..api.websocket import manager
            # await manager.broadcast(symbol, {"type": "trade", "price": price, "volume": volume})
            
            return {"status": "ok", "message": "Trade event processed"}
        
        elif event_type == "news":
            # News event
            # TODO: Process news and update sentiment
            return {"status": "ok", "message": "News event processed"}
        
        else:
            return {"status": "ok", "message": f"Unknown event type: {event_type}"}
    
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing failed: {str(e)}"
        )

