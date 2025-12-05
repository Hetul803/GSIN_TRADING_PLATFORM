# backend/broker/base.py
"""
Abstract base class for brokers.
Defines the interface that all brokers (Paper, Alpaca) must implement.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime

from .types import TradeMode, TradeSide, TradeSource


class BrokerBase(ABC):
    """Abstract base class for all brokers."""
    
    @abstractmethod
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
        Place a market order.
        
        Returns:
            Dictionary with:
            - order_id: Order identifier
            - trade_id: Trade identifier (for tracking)
            - symbol: Symbol traded
            - side: BUY or SELL
            - quantity: Quantity traded
            - price: Execution price
            - mode: PAPER or REAL
            - status: Order status
            - timestamp: Execution timestamp
        """
        pass
    
    @abstractmethod
    def close_position(
        self,
        *,
        user_id: str,
        symbol: str,
        quantity: Optional[float] = None,  # If None, close entire position
    ) -> Dict[str, Any]:
        """
        Close an existing position.
        
        Args:
            user_id: User ID
            symbol: Symbol to close
            quantity: Quantity to close (None = close all)
        
        Returns:
            Dictionary with close order details
        """
        pass
    
    @abstractmethod
    def get_account_balance(self, user_id: str) -> Dict[str, Any]:
        """
        Get account balance for a user.
        
        Returns:
            Dictionary with balance information
        """
        pass
    
    @abstractmethod
    def get_positions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all open positions for a user.
        
        Returns:
            List of position dictionaries
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if broker is available/configured.
        
        Returns:
            True if broker can be used, False otherwise
        """
        pass

