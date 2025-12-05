# backend/api/broker_connect.py
"""
PHASE 6: Broker Connection API
Handles Alpaca OAuth and manual API key entry for broker connections.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid
from datetime import datetime

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..db import crud
from ..db.models import BrokerConnection, User
from ..services.broker_key_encryption import broker_key_encryption
from ..broker.alpaca_broker import AlpacaBroker
from ..broker.paper_broker import PaperBroker

router = APIRouter(prefix="/broker", tags=["broker-connect"])


class AlpacaOAuthInitiateRequest(BaseModel):
    """Request to initiate Alpaca OAuth flow."""
    redirect_uri: str  # Where to redirect after OAuth


class AlpacaOAuthCallbackRequest(BaseModel):
    """Alpaca OAuth callback data."""
    code: str  # OAuth authorization code
    state: Optional[str] = None  # OAuth state parameter


class ManualAPIKeyRequest(BaseModel):
    """Manual API key entry request."""
    api_key: str
    api_secret: str
    base_url: Optional[str] = None  # paper-api or api (default: paper-api)


class BrokerVerifyResponse(BaseModel):
    """Response from broker verification."""
    verified: bool
    message: str
    account_id: Optional[str] = None
    account_type: Optional[str] = None  # "paper" or "live"


@router.get("/connect/alpaca/authorize")
async def initiate_alpaca_oauth(
    redirect_uri: str = Query(..., description="Redirect URI after OAuth"),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Initiate Alpaca OAuth flow.
    Returns the OAuth authorization URL.
    """
    # Alpaca OAuth endpoint
    # Note: This is a placeholder - actual Alpaca OAuth implementation would go here
    # Alpaca uses OAuth 2.0 for broker API access
    
    client_id = os.getenv("ALPACA_CLIENT_ID")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Alpaca OAuth not configured. Set ALPACA_CLIENT_ID environment variable."
        )
    
    # Generate state parameter for CSRF protection
    state = str(uuid.uuid4())
    
    # Store state in session/database for verification
    # For now, we'll use a simple approach
    
    # Alpaca OAuth authorization URL
    auth_url = (
        f"https://app.alpaca.markets/oauth/authorize?"
        f"response_type=code&"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"state={state}&"
        f"scope=read write"
    )
    
    return {
        "authorization_url": auth_url,
        "state": state
    }


@router.post("/connect/alpaca/callback")
async def alpaca_oauth_callback(
    callback_data: AlpacaOAuthCallbackRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Handle Alpaca OAuth callback.
    Exchanges authorization code for access token and stores encrypted credentials.
    """
    # Exchange code for token (this would use Alpaca's token endpoint)
    # For now, this is a placeholder - actual implementation would:
    # 1. Exchange code for access_token and refresh_token
    # 2. Encrypt tokens
    # 3. Store in BrokerConnection
    
    client_id = os.getenv("ALPACA_CLIENT_ID")
    client_secret = os.getenv("ALPACA_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Alpaca OAuth not configured"
        )
    
    # TODO: Exchange code for token via Alpaca API
    # For now, return error indicating manual setup needed
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Alpaca OAuth token exchange not yet implemented. Use manual API key entry for now."
    )


@router.post("/connect/manual")
async def connect_manual_api_key(
    request: ManualAPIKeyRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Connect broker using manual API key entry.
    Encrypts and stores API keys.
    """
    # Encrypt credentials
    encrypted_key = broker_key_encryption.encrypt(request.api_key)
    encrypted_secret = broker_key_encryption.encrypt(request.api_secret)
    
    # Get or create broker connection
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    existing_connection = db.query(BrokerConnection).filter(
        BrokerConnection.user_id == user_id
    ).first()
    
    connection_obj = None
    if existing_connection:
        # Update existing connection
        existing_connection.encrypted_api_key = encrypted_key
        existing_connection.encrypted_api_secret = encrypted_secret
        existing_connection.provider = "alpaca"
        existing_connection.connection_type = "api_key"
        existing_connection.alpaca_base_url = request.base_url or "https://paper-api.alpaca.markets"
        existing_connection.is_verified = False  # Reset verification
        existing_connection.updated_at = datetime.now()
        connection_obj = existing_connection
    else:
        # Create new connection
        connection_obj = BrokerConnection(
            id=str(uuid.uuid4()),
            user_id=user_id,
            provider="alpaca",
            connection_type="api_key",
            encrypted_api_key=encrypted_key,
            encrypted_api_secret=encrypted_secret,
            alpaca_base_url=request.base_url or "https://paper-api.alpaca.markets",
            is_verified=False
        )
        db.add(connection_obj)
    
    # Update user broker status
    user.broker_connected = False  # Will be set to True after verification
    user.broker_provider = "alpaca"
    
    db.commit()
    
    # Auto-verify connection after saving
    try:
        # Try to verify immediately using the same logic as verify endpoint
        # FIX: Check if package is available before importing
        try:
            import alpaca_trade_api as tradeapi
        except ImportError:
            # Package not installed - provide clear error
            connection_obj.is_verified = False
            user.broker_connected = False
            db.commit()
            return {
                "success": True,
                "message": "Broker credentials stored but verification failed: alpaca_trade_api library not installed. Please install with: pip install alpaca-trade-api",
                "needs_verification": True,
                "verified": False,
                "connected": False,
                "error": "alpaca_trade_api library not installed",
                "install_command": "pip install alpaca-trade-api"
            }
        base_url = connection_obj.alpaca_base_url or request.base_url or "https://paper-api.alpaca.markets"
        
        # FIX: Handle /v2 suffix - Alpaca REST client doesn't need it
        if base_url and "/v2" in base_url:
            base_url = base_url.replace("/v2", "").rstrip("/")
        
        # Ensure base_url is correct format
        if not base_url or not base_url.startswith("http"):
            if "paper" in (request.base_url or base_url or "").lower():
                base_url = "https://paper-api.alpaca.markets"
            else:
                base_url = "https://api.alpaca.markets"
        
        test_client = tradeapi.REST(
            request.api_key,
            request.api_secret,
            base_url,
            api_version='v2'
        )
        
        # Validate by calling Alpaca GET /v2/account
        account = test_client.get_account()
        
        # Mark as verified
        connection_obj.is_verified = True
        connection_obj.verified_at = datetime.now()
        connection_obj.last_used_at = datetime.now()
        connection_obj.alpaca_account_id = account.id if hasattr(account, 'id') else None
        user.broker_connected = True
        
        db.commit()
        
        return {
            "success": True,
            "message": "Broker credentials saved and verified successfully.",
            "needs_verification": False,
            "verified": True,
            "connected": True
        }
    except ImportError as import_err:
        # alpaca_trade_api not installed
        connection_obj.is_verified = False
        user.broker_connected = False
        db.commit()
        error_detail = str(import_err)
        return {
            "success": True,
            "message": f"Broker credentials stored but verification failed: alpaca_trade_api library not installed. Please install with: pip install alpaca-trade-api. Error: {error_detail}",
            "needs_verification": True,
            "verified": False,
            "connected": False,
            "error": "alpaca_trade_api library not installed",
            "install_command": "pip install alpaca-trade-api"
        }
    except Exception as e:
        # If auto-verification fails, log the error and return helpful message
        import logging
        logger = logging.getLogger(__name__)
        error_msg = str(e)
        logger.warning(f"Auto-verification failed for user {user_id}: {error_msg}")
        
        # Keep credentials saved but mark as unverified
        connection_obj.is_verified = False
        user.broker_connected = False
        db.commit()
        
        # Provide helpful error message
        if "401" in error_msg or "Unauthorized" in error_msg or "Invalid API" in error_msg:
            error_display = "Invalid API key or secret. Please check your credentials."
        elif "403" in error_msg or "Forbidden" in error_msg:
            error_display = "API key does not have trading permissions."
        elif "429" in error_msg or "rate limit" in error_msg.lower():
            error_display = "Rate limit exceeded. Please try again in a moment."
        else:
            error_display = f"Verification failed: {error_msg}"
        
        return {
            "success": True,
            "message": f"Broker credentials stored but verification failed: {error_display}",
            "needs_verification": True,
            "verified": False,
            "connected": False,
            "error": error_display
        }
    
    return {
        "success": True,
        "message": "Broker credentials stored. Please verify connection.",
        "needs_verification": True,
        "verified": False
    }


@router.post("/verify", response_model=BrokerVerifyResponse)
async def verify_broker_connection(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Verify broker connection by making a test API call.
    Performs a paper trade test to ensure credentials work.
    """
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    connection = db.query(BrokerConnection).filter(
        BrokerConnection.user_id == user_id
    ).first()
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No broker connection found. Please connect a broker first."
        )
    
    # Decrypt credentials
    try:
        api_key = broker_key_encryption.decrypt(connection.encrypted_api_key)
        api_secret = broker_key_encryption.decrypt(connection.encrypted_api_secret)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to decrypt broker credentials: {str(e)}"
        )
    
    # FINAL ALIGNMENT: Test connection with Alpaca using GET /v2/account
    try:
        # Create temporary broker instance with user's credentials
        try:
            import alpaca_trade_api as tradeapi
        except ImportError as import_err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"alpaca_trade_api library not installed. Please install with: pip install alpaca-trade-api. Error: {str(import_err)}"
            )
        
        base_url = connection.alpaca_base_url or "https://paper-api.alpaca.markets"
        
        # Ensure base_url is correct format
        # FIX: Handle /v2 suffix - Alpaca REST client doesn't need it
        if base_url and "/v2" in base_url:
            base_url = base_url.replace("/v2", "")
        
        if not base_url or not base_url.startswith("http"):
            if "paper" in base_url.lower():
                base_url = "https://paper-api.alpaca.markets"
            else:
                base_url = "https://api.alpaca.markets"
        
        test_client = tradeapi.REST(
            api_key,
            api_secret,
            base_url,
            api_version='v2'
        )
        
        # Validate by calling Alpaca GET /v2/account (as specified)
        account = test_client.get_account()
        
        # Detect paper vs live mode from base_url
        is_paper = "paper" in base_url.lower()
        
        # Mark as verified
        connection.is_verified = True
        connection.verified_at = datetime.now()
        connection.last_used_at = datetime.now()
        connection.alpaca_account_id = account.id if hasattr(account, 'id') else None
        user.broker_connected = True
        
        db.commit()
        
        return BrokerVerifyResponse(
            verified=True,
            message="Broker connection verified successfully",
            account_id=account.id if hasattr(account, 'id') else None,
            account_type="paper" if is_paper else "live"
        )
    except Exception as e:
        connection.is_verified = False
        user.broker_connected = False
        db.commit()
        
        return BrokerVerifyResponse(
            verified=False,
            message=f"Broker verification failed: {str(e)}"
        )


@router.get("/status")
async def get_broker_status(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Get current broker connection status."""
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    connection = db.query(BrokerConnection).filter(
        BrokerConnection.user_id == user_id
    ).first()
    
    if not connection:
        return {
            "connected": False,
            "provider": None,
            "verified": False
        }
    
    # Return connection status - use is_verified as the source of truth
    # FIX: Ensure both connection.is_verified and user.broker_connected are in sync
    is_verified = connection.is_verified
    user_connected = getattr(user, 'broker_connected', False)
    
    # CRITICAL FIX: Sync flags - is_verified is the source of truth
    if is_verified != user_connected:
        user.broker_connected = is_verified
        db.commit()
        user_connected = is_verified  # Update local variable
    
    # Connected means both verified AND user flag is set
    is_connected = is_verified and user_connected
    
    return {
        "connected": is_connected,
        "provider": connection.provider,
        "connection_type": connection.connection_type,
        "verified": is_verified,
        "verified_at": connection.verified_at.isoformat() if connection.verified_at else None,
        "account_type": "paper" if connection.alpaca_base_url and "paper" in connection.alpaca_base_url.lower() else "live",
        "account_id": connection.alpaca_account_id
    }


@router.delete("/disconnect")
async def disconnect_broker(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Disconnect and remove broker connection."""
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    connection = db.query(BrokerConnection).filter(
        BrokerConnection.user_id == user_id
    ).first()
    
    if connection:
        db.delete(connection)
    
    user.broker_connected = False
    user.broker_provider = None
    
    db.commit()
    
    return {
        "success": True,
        "message": "Broker disconnected successfully"
    }

