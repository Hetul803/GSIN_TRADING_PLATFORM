# backend/broker/router.py
"""
Broker API Router - Unified endpoint for PAPER and REAL trading.

RISK & SAFETY CONSTRAINTS:
- Validates user trading settings (max_auto_trade_amount, capital_range)
- Enforces global safety caps for REAL trading (MAX_REAL_NOTIONAL, MAX_REAL_QUANTITY)
- Rejects orders that violate constraints with clear error messages
"""
import os
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from sqlalchemy.orm import Session

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..db import crud
from .types import PlaceOrderRequest, OrderResponse, PositionResponse, AccountBalanceResponse, TradeMode
from .paper_broker import PaperBroker
from .alpaca_broker import AlpacaBroker

router = APIRouter(prefix="/broker", tags=["broker"])


# PHASE 4: JWT-only authentication - use dependency directly


def get_broker(mode: TradeMode, db: Session, user_id: str = None):
    """
    FINAL ALIGNMENT: Get the appropriate broker based on mode.
    
    IMPORTANT:
    - PAPER mode: Uses PaperBroker (internal simulation)
    - REAL mode: Uses AlpacaBroker with USER-LEVEL keys (from BrokerConnection)
    - Platform keys (from .env) are NEVER used for trading
    
    Args:
        mode: PAPER or REAL
        db: Database session
        user_id: User ID (required for REAL mode to load user's encrypted keys)
    
    Returns:
        Broker instance
    """
    if mode == TradeMode.PAPER:
        return PaperBroker(db)
    elif mode == TradeMode.REAL:
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID required for REAL trading mode"
            )
        
        # Load user's encrypted broker connection
        broker = AlpacaBroker.from_user_connection(user_id, db)
        if not broker or not broker.is_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Real trading is not available. Please connect and verify your Alpaca account in Settings."
            )
        return broker
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid trade mode: {mode}"
        )


@router.post("/place-order", response_model=OrderResponse)
async def place_order(
    order_data: PlaceOrderRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Place a market order (PAPER or REAL).
    
    Routes to:
    - PaperBroker if mode="PAPER"
    - AlpacaBroker if mode="REAL"
    """
    # Get appropriate broker (pass user_id for REAL mode)
    broker = get_broker(order_data.mode, db, user_id=user_id)
    
    # STRICT RISK & SAFETY CONSTRAINTS
    # Load user trading settings
    user_settings = crud.get_user_trading_settings(db, user_id)
    
    # Get current price for notional calculation through request queue
    try:
        from ..market_data.market_data_provider import call_with_fallback
        price_data = call_with_fallback("get_price", order_data.symbol)
        current_price = price_data.price if price_data and hasattr(price_data, 'price') else 0.0
    except:
        current_price = 0.0
    
    # Estimate notional (will be validated more precisely after order execution)
    estimated_notional = order_data.quantity * current_price if current_price > 0 else 0.0
    
    if user_settings and current_price > 0:
        # Check max auto trade amount
        if estimated_notional > user_settings.max_auto_trade_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Estimated order notional (${estimated_notional:.2f}) exceeds max auto trade amount (${user_settings.max_auto_trade_amount:.2f})"
            )
        
        # Check capital range
        if estimated_notional < user_settings.capital_range_min or estimated_notional > user_settings.capital_range_max:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Estimated order notional (${estimated_notional:.2f}) outside allowed range (${user_settings.capital_range_min:.2f} - ${user_settings.capital_range_max:.2f})"
            )
    
    # ENHANCED RISK MANAGEMENT FOR REAL TRADING
    # Uses portfolio risk manager for proper position sizing
    if order_data.mode == TradeMode.REAL:
        # Validate buying power
        try:
            if broker and broker.is_available():
                balance_info = broker.get_account_balance(user_id)
                buying_power = balance_info.get("buying_power_real", 0.0) if balance_info else 0.0
                account_balance = balance_info.get("equity", buying_power) if balance_info else buying_power
                
                if current_price > 0 and estimated_notional > buying_power:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Insufficient buying power. Need ${estimated_notional:.2f}, have ${buying_power:.2f}"
                    )
                
                # Use portfolio risk manager for position sizing
                from ..strategy_engine.portfolio_risk_manager import PortfolioRiskManager
                from ..strategy_engine.portfolio_risk_manager import PortfolioPosition
                
                # Get current positions
                positions_data = broker.get_open_positions(user_id) if hasattr(broker, 'get_open_positions') else []
                portfolio_positions = []
                for pos in positions_data:
                    portfolio_positions.append(
                        PortfolioPosition(
                            symbol=pos.get("symbol", ""),
                            quantity=pos.get("qty", 0),
                            entry_price=pos.get("avg_entry_price", 0),
                            current_price=pos.get("current_price", 0),
                            notional=pos.get("market_value", 0),
                            strategy_id=pos.get("strategy_id")
                        )
                    )
                
                # Calculate optimal position size
                risk_manager = PortfolioRiskManager()
                strategy_risk = 0.02  # Default 2% risk per trade
                max_risk_per_trade = user_settings.max_risk_per_trade_percent / 100.0 if user_settings else 0.02
                
                optimal_shares = risk_manager.calculate_position_size(
                    account_balance=account_balance,
                    strategy_risk=strategy_risk,
                    symbol=order_data.symbol,
                    entry_price=current_price,
                    portfolio_positions=portfolio_positions,
                    max_risk_per_trade=max_risk_per_trade
                )
                
                # Validate new position
                is_valid, error_msg = risk_manager.validate_new_position(
                    symbol=order_data.symbol,
                    quantity=order_data.quantity,
                    entry_price=current_price,
                    account_balance=account_balance,
                    portfolio_positions=portfolio_positions,
                    strategy_id=order_data.strategy_id
                )
                
                if not is_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Portfolio risk limit exceeded: {error_msg}. Optimal size: {optimal_shares:.2f} shares"
                    )
                
                # Warn if quantity differs significantly from optimal
                if optimal_shares > 0 and abs(order_data.quantity - optimal_shares) / optimal_shares > 0.2:
                    # Allow but log warning
                    print(f"⚠️  Position size ({order_data.quantity}) differs from optimal ({optimal_shares:.2f})")
                
        except HTTPException:
            raise
        except Exception as e:
            print(f"⚠️  Risk management error: {e}")
            # Fall back to basic validation
            if current_price > 0 and estimated_notional > buying_power:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient buying power. Need ${estimated_notional:.2f}, have ${buying_power:.2f}"
                )
        
        # Configurable safety caps (now much higher defaults for production use)
        MAX_REAL_QUANTITY = float(os.environ.get("MAX_REAL_QUANTITY", "10000.0"))  # Increased from 1.0
        if order_data.quantity > MAX_REAL_QUANTITY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"REAL trade quantity ({order_data.quantity}) exceeds safety cap ({MAX_REAL_QUANTITY}). "
                       f"This is a safety measure. To increase, set MAX_REAL_QUANTITY env var."
            )
        
        # Also cap estimated notional for REAL trades (increased default)
        MAX_REAL_NOTIONAL = float(os.environ.get("MAX_REAL_NOTIONAL", "100000.0"))  # Increased from $1000 to $100k
        if current_price > 0 and estimated_notional > MAX_REAL_NOTIONAL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Estimated REAL trade notional (${estimated_notional:.2f}) exceeds safety cap (${MAX_REAL_NOTIONAL:.2f}). "
                       f"This is a safety measure. To increase, set MAX_REAL_NOTIONAL env var."
            )
    
    try:
        result = broker.place_market_order(
            user_id=user_id,
            symbol=order_data.symbol,
            side=order_data.side,
            quantity=order_data.quantity,
            mode=order_data.mode,
            source=order_data.source,
            group_id=order_data.group_id,
            strategy_id=order_data.strategy_id,
            stop_loss=order_data.stop_loss,
            take_profit=order_data.take_profit,
        )
        
        # Record trade event in MCN
        from ..brain.mcn_adapter import get_mcn_adapter
        from datetime import datetime
        
        mcn_adapter = get_mcn_adapter()
        mcn_adapter.record_event(
            event_type="trade_executed",
            payload={
                "user_id": user_id,
                "symbol": order_data.symbol,
                "side": order_data.side.value if hasattr(order_data.side, 'value') else str(order_data.side),
                "quantity": order_data.quantity,
                "entry_price": result.get("price", 0.0),
                "exit_price": None,  # Will be updated when trade is closed
                "pnl": None,  # Will be updated when trade is closed
                "mode": order_data.mode.value if hasattr(order_data.mode, 'value') else str(order_data.mode),
                "strategy_id": order_data.strategy_id,
                "group_id": order_data.group_id,
                "source": order_data.source.value if hasattr(order_data.source, 'value') else str(order_data.source),
                "timestamp": datetime.now().isoformat(),
            },
            user_id=user_id,
            strategy_id=order_data.strategy_id,
        )
        
        return OrderResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Order placement failed: {str(e)}"
        )


@router.post("/close-position")
async def close_position(
    symbol: str,
    quantity: Optional[float] = None,
    mode: TradeMode = TradeMode.PAPER,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Close an existing position."""
    broker = get_broker(mode, db, user_id=user_id)
    
    try:
        result = broker.close_position(
            user_id=user_id,
            symbol=symbol,
            quantity=quantity,
        )
        
        # Record trade closure event in MCN
        from ..brain.mcn_adapter import get_mcn_adapter
        from datetime import datetime
        
        mcn_adapter = get_mcn_adapter()
        mcn_adapter.record_event(
            event_type="trade_closed",
            payload={
                "user_id": user_id,
                "symbol": symbol,
                "quantity": result.get("quantity", quantity),
                "exit_price": result.get("exit_price", 0.0),
                "pnl": result.get("realized_pnl", 0.0),
                "mode": mode.value if hasattr(mode, 'value') else str(mode),
                "timestamp": datetime.now().isoformat(),
            },
            user_id=user_id,
            strategy_id=None,  # Could be retrieved from the trade record
        )
        
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Close position failed: {str(e)}"
        )


@router.get("/balance", response_model=AccountBalanceResponse)
def get_balance(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Get account balance (combines PAPER and REAL if available)."""
    # Get paper balance
    paper_broker = PaperBroker(db)
    paper_balance_info = paper_broker.get_account_balance(user_id)
    
    # Try to get real balance (using user's keys)
    real_balance_info = {}
    try:
        real_broker = AlpacaBroker.from_user_connection(user_id, db)
        if real_broker and real_broker.is_available():
            real_balance_info = real_broker.get_account_balance(user_id)
    except:
        pass  # Real trading not available
    
    return AccountBalanceResponse(
        user_id=user_id,
        paper_balance=paper_balance_info.get("paper_balance", 0.0),
        real_balance=real_balance_info.get("real_balance"),
        paper_equity=paper_balance_info.get("paper_equity", 0.0),
        real_equity=real_balance_info.get("real_equity"),
        buying_power_paper=paper_balance_info.get("buying_power_paper", 0.0),
        buying_power_real=real_balance_info.get("buying_power_real"),
    )


@router.get("/positions", response_model=list[PositionResponse])
async def get_positions(
    mode: Optional[TradeMode] = None,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Get all positions (PAPER, REAL, or both)."""
    positions = []
    
    # Get paper positions
    if mode is None or mode == TradeMode.PAPER:
        paper_broker = PaperBroker(db)
        paper_positions = paper_broker.get_positions(user_id)
        positions.extend(paper_positions)
    
    # Get real positions (using user's keys)
    if mode is None or mode == TradeMode.REAL:
        try:
            real_broker = AlpacaBroker.from_user_connection(user_id, db)
            if real_broker and real_broker.is_available():
                real_positions = real_broker.get_positions(user_id)
                positions.extend(real_positions)
        except:
            pass  # Real trading not available
    
    return [PositionResponse(**pos) for pos in positions]

