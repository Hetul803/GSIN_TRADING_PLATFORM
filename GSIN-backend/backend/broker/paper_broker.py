# backend/broker/paper_broker.py
"""
Paper Trading Broker - Uses existing GSIN trades DB for simulated trading.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from sqlalchemy.orm import Session

from .base import BrokerBase
from .types import TradeMode, TradeSide, TradeSource
from ..db import crud
from ..db.models import Trade, TradeStatus, TradeMode as TradeModeEnum, TradeSide as TradeSideEnum, TradeSource as TradeSourceEnum, UserPaperAccount


class PaperBroker(BrokerBase):
    """
    Paper trading broker using existing GSIN trades system.
    All trades are stored in the trades table with mode="PAPER".
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def is_available(self) -> bool:
        """Paper broker is always available."""
        return True
    
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
        """Place a paper market order."""
        if mode != TradeMode.PAPER:
            raise ValueError("PaperBroker only handles PAPER trades")
        
        # Get current price from market data through request queue
        from ..market_data.market_data_provider import call_with_fallback
        
        price_data = call_with_fallback("get_price", symbol)
        if not price_data:
            raise ValueError(f"Could not fetch price for {symbol}")
        
        entry_price = price_data.price if hasattr(price_data, 'price') else float(price_data)
        
        # Get or create paper account
        import os
        from pathlib import Path
        from dotenv import dotenv_values
        
        CFG_PATH = Path(__file__).resolve().parents[2] / "config" / ".env"
        cfg = dotenv_values(str(CFG_PATH)) if CFG_PATH.exists() else {}
        starting_balance = float(os.environ.get("PAPER_STARTING_BALANCE") or cfg.get("PAPER_STARTING_BALANCE", "100000"))
        
        paper_account = crud.get_or_create_paper_account(self.db, user_id, starting_balance)
        
        # Calculate order cost
        order_cost = entry_price * quantity
        
        # Check if user has enough balance
        if side == TradeSide.BUY and order_cost > paper_account.balance:
            raise ValueError(f"Insufficient paper balance. Need ${order_cost:.2f}, have ${paper_account.balance:.2f}")
        
        # Create trade in DB
        trade = crud.create_trade(
            db=self.db,
            user_id=user_id,
            symbol=symbol,
            side=TradeSideEnum.BUY if side == TradeSide.BUY else TradeSideEnum.SELL,
            quantity=quantity,
            entry_price=entry_price,
            asset_type=crud.AssetType.STOCK,  # Default, can be enhanced
            mode=TradeModeEnum.PAPER,
            source=TradeSourceEnum.MANUAL if source == TradeSource.MANUAL else TradeSourceEnum.BRAIN,
            strategy_id=strategy_id,
            group_id=group_id,
        )
        
        # Update user's paper balance (deduct for BUY, add for SELL)
        if side == TradeSide.BUY:
            paper_account.balance -= order_cost
        else:  # SELL
            paper_account.balance += order_cost
        
        crud.update_user_paper_account(self.db, user_id, balance=paper_account.balance)
        
        return {
            "order_id": str(uuid.uuid4()),
            "trade_id": trade.id,
            "symbol": symbol,
            "side": side.value,
            "quantity": quantity,
            "price": entry_price,
            "mode": mode.value,
            "status": "FILLED",
            "timestamp": trade.opened_at,
        }
    
    def close_position(
        self,
        *,
        user_id: str,
        symbol: str,
        quantity: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Close a paper position."""
        # Find open trades for this user and symbol
        from ..db.models import TradeStatus
        trades = crud.list_user_trades(
            db=self.db,
            user_id=user_id,
            status=TradeStatus.OPEN,
            mode=TradeModeEnum.PAPER,
        )
        
        # Filter by symbol
        open_trades = [t for t in trades if t.symbol.upper() == symbol.upper()]
        
        if not open_trades:
            raise ValueError(f"No open position found for {symbol}")
        
        # Get current price
        from ..market_data.market_data_provider import get_provider
        from ..market_data.market_data_provider import call_with_fallback
        
        price_data = call_with_fallback("get_price", symbol)
        if not price_data:
            raise ValueError(f"Could not fetch price for {symbol}")
        
        exit_price = price_data.price if hasattr(price_data, 'price') else float(price_data)
        
        # Close trades
        closed_trades = []
        remaining_quantity = quantity if quantity else sum(t.quantity for t in open_trades)
        
        for trade in open_trades:
            if remaining_quantity <= 0:
                break
            
            close_qty = min(trade.quantity, remaining_quantity)
            
            # Close the trade (or partial close if needed)
            closed_trade = None
            if close_qty == trade.quantity:
                # Full close
                closed_trade = crud.close_trade(
                    db=self.db,
                    trade_id=trade.id,
                    user_id=user_id,
                    exit_price=exit_price,
                )
            else:
                # Partial close - create new trade for remaining quantity
                # For simplicity, we'll close the full trade and create a new one for remainder
                # In production, implement partial fills
                closed_trade = crud.close_trade(
                    db=self.db,
                    trade_id=trade.id,
                    user_id=user_id,
                    exit_price=exit_price,
                )
            
            # Update paper balance with realized P&L
            if closed_trade and closed_trade.realized_pnl is not None:
                paper_account = crud.get_user_paper_account(self.db, user_id)
                if paper_account:
                    paper_account.balance += closed_trade.realized_pnl
                    crud.update_user_paper_account(self.db, user_id, balance=paper_account.balance)
            
            remaining_quantity -= close_qty
            closed_trades.append(trade.id)
        
        return {
            "order_id": str(uuid.uuid4()),
            "trade_ids": closed_trades,
            "symbol": symbol,
            "quantity": quantity if quantity else sum(t.quantity for t in open_trades),
            "exit_price": exit_price,
            "mode": "PAPER",
            "status": "FILLED",
            "timestamp": datetime.now(),
        }
    
    def get_account_balance(self, user_id: str) -> Dict[str, Any]:
        """Get paper account balance from UserPaperAccount."""
        import os
        from pathlib import Path
        from dotenv import dotenv_values
        
        CFG_PATH = Path(__file__).resolve().parents[2] / "config" / ".env"
        cfg = dotenv_values(str(CFG_PATH)) if CFG_PATH.exists() else {}
        starting_balance = float(os.environ.get("PAPER_STARTING_BALANCE") or cfg.get("PAPER_STARTING_BALANCE", "100000"))
        
        # Get or create paper account
        paper_account = crud.get_or_create_paper_account(self.db, user_id, starting_balance)
        
        # Calculate unrealized P&L from open trades
        from ..market_data.market_data_provider import get_provider
        market_provider = get_provider()
        unrealized_pnl = 0.0
        
        open_trades = crud.list_user_trades(
            db=self.db,
            user_id=user_id,
            status=TradeStatus.OPEN,
            mode=TradeModeEnum.PAPER,
        )
        
        for trade in open_trades:
            try:
                from ..market_data.market_data_provider import call_with_fallback
                price_data = call_with_fallback("get_price", trade.symbol)
                if price_data:
                    current_price = price_data.price if hasattr(price_data, 'price') else float(price_data)
                    if trade.side == TradeSideEnum.BUY:
                        pnl = (current_price - trade.entry_price) * trade.quantity
                    else:
                        pnl = (trade.entry_price - current_price) * trade.quantity
                    unrealized_pnl += pnl
            except:
                pass  # If market data unavailable, skip unrealized P&L for this trade
        
        paper_balance = paper_account.balance
        paper_equity = paper_balance + unrealized_pnl
        
        # Calculate realized P&L from closed trades
        closed_trades = crud.list_user_trades(
            db=self.db,
            user_id=user_id,
            status=TradeStatus.CLOSED,
            mode=TradeModeEnum.PAPER,
        )
        realized_pnl = sum(t.realized_pnl for t in closed_trades if t.realized_pnl is not None)
        
        return {
            "user_id": user_id,
            "paper_balance": paper_balance,
            "paper_equity": paper_equity,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "buying_power_paper": paper_balance,  # For paper, buying power = balance
        }
    
    def get_positions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all open paper positions."""
        trades = crud.list_user_trades(
            db=self.db,
            user_id=user_id,
            status=TradeStatus.OPEN,
            mode=TradeModeEnum.PAPER,
        )
        
        # Group by symbol
        positions = {}
        for trade in trades:
            symbol = trade.symbol
            if symbol not in positions:
                positions[symbol] = {
                    "symbol": symbol,
                    "quantity": 0.0,
                    "avg_entry_price": 0.0,
                    "total_cost": 0.0,
                    "trades": [],
                }
            
            positions[symbol]["quantity"] += trade.quantity if trade.side == TradeSideEnum.BUY else -trade.quantity
            positions[symbol]["total_cost"] += trade.entry_price * trade.quantity
            positions[symbol]["trades"].append(trade)
        
        # Calculate average entry price and get current prices
        from ..market_data.market_data_provider import get_provider
        market_provider = get_provider()
        
        result = []
        for symbol, pos_data in positions.items():
            if pos_data["quantity"] == 0:
                continue
            
            avg_entry = pos_data["total_cost"] / sum(t.quantity for t in pos_data["trades"])
            current_price = avg_entry  # Default
            
            try:
                from ..market_data.market_data_provider import call_with_fallback
                price_data = call_with_fallback("get_price", symbol)
                if price_data:
                    current_price = price_data.price if hasattr(price_data, 'price') else float(price_data)
            except:
                pass  # If market data unavailable, use avg_entry as default
            
            unrealized_pnl = (current_price - avg_entry) * pos_data["quantity"]
            
            result.append({
                "symbol": symbol,
                "quantity": abs(pos_data["quantity"]),
                "side": "LONG" if pos_data["quantity"] > 0 else "SHORT",
                "avg_entry_price": avg_entry,
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl,
                "mode": "PAPER",
            })
        
        return result

