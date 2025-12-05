# backend/broker/alpaca_broker.py
"""
Alpaca Broker - Real trading via Alpaca API.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import os

from .base import BrokerBase
from .types import TradeMode, TradeSide, TradeSource


class AlpacaBroker(BrokerBase):
    """
    FINAL ALIGNMENT: Alpaca broker for real trading.
    
    IMPORTANT: This broker uses USER-LEVEL keys for trading.
    Platform-level keys (from .env) are ONLY for market data, NOT for trading.
    
    For trading, user-level keys must be provided via user_id.
    """
    
    def __init__(self, user_id: str = None, api_key: str = None, secret_key: str = None, base_url: str = None):
        """
        Initialize Alpaca broker.
        
        Args:
            user_id: User ID to retrieve encrypted keys from database
            api_key: Direct API key (if provided, overrides user_id lookup)
            secret_key: Direct secret key (if provided, overrides user_id lookup)
            base_url: Base URL (paper-api or api)
        
        NOTE: If user_id is provided, keys will be loaded from BrokerConnection.
        If api_key/secret_key are provided directly, those will be used.
        Platform keys from .env are NEVER used for trading.
        """
        self.user_id = user_id
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        
        # Initialize Alpaca client if keys are available
        self.client = None
        if self.api_key and self.secret_key:
            try:
                import alpaca_trade_api as tradeapi
                self.client = tradeapi.REST(
                    self.api_key,
                    self.secret_key,
                    self.base_url or "https://paper-api.alpaca.markets",
                    api_version='v2'
                )
            except ImportError:
                print("WARNING: alpaca_trade_api not installed. Install with: pip install alpaca-trade-api")
                self.client = None
            except Exception as e:
                print(f"WARNING: Failed to initialize Alpaca client: {e}")
                self.client = None
    
    @classmethod
    def from_user_connection(cls, user_id: str, db):
        """
        Create AlpacaBroker instance from user's encrypted broker connection.
        
        This is the CORRECT way to initialize for trading - uses user-level keys.
        """
        from ..db.models import BrokerConnection
        from ..services.broker_key_encryption import broker_key_encryption
        
        connection = db.query(BrokerConnection).filter(
            BrokerConnection.user_id == user_id,
            BrokerConnection.provider == "alpaca",
            BrokerConnection.is_verified == True
        ).first()
        
        if not connection:
            return None
        
        # Decrypt user's keys
        try:
            api_key = broker_key_encryption.decrypt(connection.encrypted_api_key)
            api_secret = broker_key_encryption.decrypt(connection.encrypted_api_secret)
            base_url = connection.alpaca_base_url or "https://paper-api.alpaca.markets"
            
            return cls(
                user_id=user_id,
                api_key=api_key,
                secret_key=api_secret,
                base_url=base_url
            )
        except Exception as e:
            print(f"ERROR: Failed to decrypt user broker keys: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if Alpaca broker is configured and available."""
        return self.client is not None and self.api_key is not None and self.secret_key is not None
    
    def place_market_order(
        self,
        *,
        user_id: str,
        symbol: str,
        side: TradeSide,
        quantity: float,
        mode: TradeMode,
        source: TradeSource,
        group_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Place a real market order via Alpaca.
        
        SAFETY: This method ONLY uses Alpaca order endpoints (submit_order, get_order, list_orders).
        It does NOT call any funding, transfer, deposit, withdraw, ACH, or bank endpoints.
        
        For REAL mode, we enforce safety caps:
        - By default, limit to 1 share for stocks (or very small quantity) unless explicitly overridden
        - This prevents accidental large orders in REAL mode
        - TODO: Remove this cap once we are confident in the system
        """
        if mode != TradeMode.REAL:
            raise ValueError("AlpacaBroker only handles REAL trades")
        
        if not self.is_available():
            raise ValueError("Alpaca broker is not configured. Set ALPACA_API_KEY and ALPACA_SECRET_KEY")
        
        # ENHANCED RISK MANAGEMENT: Use configurable safety cap with portfolio risk management
        # Position sizing is now handled by PortfolioRiskManager in router.py
        # This is a final safety check only
        MAX_SAFE_QUANTITY_REAL = float(os.environ.get("MAX_REAL_QUANTITY", "10000.0"))  # Increased from 1.0
        if quantity > MAX_SAFE_QUANTITY_REAL:
            raise ValueError(
                f"REAL mode safety cap: Maximum quantity is {MAX_SAFE_QUANTITY_REAL} share(s). "
                f"Requested: {quantity}. This is a final safety check. "
                f"Position sizing is managed by PortfolioRiskManager. To increase, set MAX_REAL_QUANTITY env var."
            )
        
        try:
            # Place market order via Alpaca
            # SAFETY: Only using order endpoints - NO funding/transfer endpoints
            order = self.client.submit_order(
                symbol=symbol.upper(),
                qty=int(quantity),  # Alpaca requires integer quantities
                side="buy" if side == TradeSide.BUY else "sell",
                type="market",
                time_in_force="day",
            )
            
            # Wait for order to fill (simplified - in production, use async/await)
            import time
            time.sleep(1)  # Brief wait for order to fill
            
            # Get order status
            order_status = self.client.get_order(order.id)
            
            # Get fill price
            fills = self.client.list_orders(status="filled", limit=1)
            fill_price = float(order_status.filled_avg_price) if order_status.filled_avg_price else 0.0
            
            return {
                "order_id": order.id,
                "trade_id": order.id,  # Use order ID as trade ID
                "symbol": symbol.upper(),
                "side": side.value,
                "quantity": float(order_status.filled_qty),
                "price": fill_price,
                "mode": mode.value,
                "status": order_status.status,
                "timestamp": datetime.now(),
            }
        except Exception as e:
            raise ValueError(f"Alpaca order failed: {str(e)}")
    
    def close_position(
        self,
        *,
        user_id: str,
        symbol: str,
        quantity: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Close a real position via Alpaca."""
        if not self.is_available():
            raise ValueError("Alpaca broker is not configured")
        
        try:
            # Get current position
            position = self.client.get_position(symbol.upper())
            current_qty = float(position.qty)
            
            # Determine close quantity
            close_qty = quantity if quantity else abs(current_qty)
            close_qty = min(close_qty, abs(current_qty))
            
            # Determine side (opposite of current position)
            side = "sell" if current_qty > 0 else "buy"
            
            # Place closing order
            order = self.client.submit_order(
                symbol=symbol.upper(),
                qty=int(close_qty),
                side=side,
                type="market",
                time_in_force="day",
            )
            
            # Get order status
            import time
            time.sleep(1)
            order_status = self.client.get_order(order.id)
            fill_price = float(order_status.filled_avg_price) if order_status.filled_avg_price else 0.0
            
            return {
                "order_id": order.id,
                "symbol": symbol.upper(),
                "quantity": float(order_status.filled_qty),
                "exit_price": fill_price,
                "mode": "REAL",
                "status": order_status.status,
                "timestamp": datetime.now(),
            }
        except Exception as e:
            raise ValueError(f"Alpaca close position failed: {str(e)}")
    
    def get_account_balance(self, user_id: str) -> Dict[str, Any]:
        """Get real account balance from Alpaca."""
        if not self.is_available():
            raise ValueError("Alpaca broker is not configured")
        
        try:
            account = self.client.get_account()
            
            return {
                "user_id": user_id,
                "real_balance": float(account.cash),
                "real_equity": float(account.equity),
                "buying_power_real": float(account.buying_power),
                "portfolio_value": float(account.portfolio_value),
            }
        except Exception as e:
            raise ValueError(f"Failed to get Alpaca account balance: {str(e)}")
    
    def get_positions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all real positions from Alpaca."""
        if not self.is_available():
            raise ValueError("Alpaca broker is not configured")
        
        try:
            positions = self.client.list_positions()
            
            result = []
            for pos in positions:
                result.append({
                    "symbol": pos.symbol,
                    "quantity": float(pos.qty),
                    "side": "LONG" if float(pos.qty) > 0 else "SHORT",
                    "avg_entry_price": float(pos.avg_entry_price),
                    "current_price": float(pos.current_price),
                    "unrealized_pnl": float(pos.unrealized_pl),
                    "mode": "REAL",
                })
            
            return result
        except Exception as e:
            raise ValueError(f"Failed to get Alpaca positions: {str(e)}")

