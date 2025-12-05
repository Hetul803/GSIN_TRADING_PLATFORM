# backend/strategy_engine/transaction_costs.py
"""
Transaction Cost Modeler - Hedge Fund Grade

Models realistic transaction costs including:
- Commissions (fixed per trade)
- Slippage (market impact, bid-ask spread)
- Market impact (price movement from large orders)

This is critical for realistic backtesting and live trading.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class TransactionCostModel:
    """Configuration for transaction cost modeling."""
    commission_per_share: float = 0.0  # Commission per share (e.g., $0.005)
    commission_per_trade: float = 0.0  # Fixed commission per trade (e.g., $1.00)
    slippage_bps: float = 5.0  # Slippage in basis points (5 bps = 0.05%)
    market_impact_bps: float = 2.0  # Market impact in basis points (2 bps = 0.02%)
    bid_ask_spread_bps: float = 3.0  # Bid-ask spread in basis points (3 bps = 0.03%)


class TransactionCostCalculator:
    """
    Calculates transaction costs for trades.
    """
    
    def __init__(self, model: Optional[TransactionCostModel] = None):
        """
        Initialize transaction cost calculator.
        
        Args:
            model: Transaction cost model configuration (None = use defaults)
        """
        self.model = model or TransactionCostModel()
    
    def calculate_entry_cost(
        self,
        price: float,
        shares: float,
        order_type: str = "market"
    ) -> float:
        """
        Calculate total cost for entering a trade.
        
        Args:
            price: Entry price per share
            shares: Number of shares
            order_type: "market" or "limit"
        
        Returns:
            Total transaction cost in dollars
        """
        notional = price * shares
        
        # Commission
        commission = (
            self.model.commission_per_share * shares +
            self.model.commission_per_trade
        )
        
        # Slippage (only for market orders)
        slippage = 0.0
        if order_type == "market":
            slippage = notional * (self.model.slippage_bps / 10000)
        
        # Market impact (scales with order size)
        market_impact = notional * (self.model.market_impact_bps / 10000)
        
        # Bid-ask spread (always applies)
        spread_cost = notional * (self.model.bid_ask_spread_bps / 10000)
        
        total_cost = commission + slippage + market_impact + spread_cost
        
        return total_cost
    
    def calculate_exit_cost(
        self,
        price: float,
        shares: float,
        order_type: str = "market"
    ) -> float:
        """
        Calculate total cost for exiting a trade.
        
        Args:
            price: Exit price per share
            shares: Number of shares
            order_type: "market" or "limit"
        
        Returns:
            Total transaction cost in dollars
        """
        # Same calculation as entry
        return self.calculate_entry_cost(price, shares, order_type)
    
    def calculate_round_trip_cost(
        self,
        entry_price: float,
        exit_price: float,
        shares: float,
        entry_order_type: str = "market",
        exit_order_type: str = "market"
    ) -> float:
        """
        Calculate total round-trip transaction cost.
        
        Args:
            entry_price: Entry price per share
            exit_price: Exit price per share
            shares: Number of shares
            entry_order_type: "market" or "limit"
            exit_order_type: "market" or "limit"
        
        Returns:
            Total round-trip transaction cost in dollars
        """
        entry_cost = self.calculate_entry_cost(
            entry_price,
            shares,
            entry_order_type
        )
        exit_cost = self.calculate_exit_cost(
            exit_price,
            shares,
            exit_order_type
        )
        
        return entry_cost + exit_cost
    
    def apply_to_trade(
        self,
        entry_price: float,
        exit_price: float,
        shares: float,
        pnl: float,
        entry_order_type: str = "market",
        exit_order_type: str = "market"
    ) -> Dict[str, Any]:
        """
        Apply transaction costs to a trade and return adjusted PnL.
        
        Args:
            entry_price: Entry price per share
            exit_price: Exit price per share
            shares: Number of shares
            pnl: Gross PnL before costs
            entry_order_type: "market" or "limit"
            exit_order_type: "market" or "limit"
        
        Returns:
            Dictionary with:
            - gross_pnl: Original PnL
            - transaction_costs: Total costs
            - net_pnl: PnL after costs
            - cost_breakdown: Detailed cost breakdown
        """
        round_trip_cost = self.calculate_round_trip_cost(
            entry_price,
            exit_price,
            shares,
            entry_order_type,
            exit_order_type
        )
        
        entry_cost = self.calculate_entry_cost(
            entry_price,
            shares,
            entry_order_type
        )
        exit_cost = self.calculate_exit_cost(
            exit_price,
            shares,
            exit_order_type
        )
        
        net_pnl = pnl - round_trip_cost
        
        return {
            "gross_pnl": pnl,
            "transaction_costs": round_trip_cost,
            "net_pnl": net_pnl,
            "cost_breakdown": {
                "entry_cost": entry_cost,
                "exit_cost": exit_cost,
                "total_cost": round_trip_cost
            },
            "cost_percentage": (round_trip_cost / (entry_price * shares)) * 100
        }
    
    def estimate_annual_cost(
        self,
        avg_trade_size: float,
        trades_per_year: int,
        avg_price: float
    ) -> float:
        """
        Estimate annual transaction costs.
        
        Args:
            avg_trade_size: Average number of shares per trade
            trades_per_year: Expected number of trades per year
            avg_price: Average price per share
        
        Returns:
            Estimated annual transaction costs in dollars
        """
        avg_notional = avg_trade_size * avg_price
        cost_per_trade = self.calculate_round_trip_cost(
            avg_price,
            avg_price,
            avg_trade_size
        )
        
        annual_cost = cost_per_trade * trades_per_year
        
        return annual_cost


# Pre-configured models for different broker types
COMMISSION_FREE_MODEL = TransactionCostModel(
    commission_per_share=0.0,
    commission_per_trade=0.0,
    slippage_bps=5.0,
    market_impact_bps=2.0,
    bid_ask_spread_bps=3.0
)

TRADITIONAL_BROKER_MODEL = TransactionCostModel(
    commission_per_share=0.005,
    commission_per_trade=1.0,
    slippage_bps=5.0,
    market_impact_bps=2.0,
    bid_ask_spread_bps=3.0
)

INSTITUTIONAL_MODEL = TransactionCostModel(
    commission_per_share=0.001,
    commission_per_trade=0.0,
    slippage_bps=3.0,  # Better execution
    market_impact_bps=1.0,  # Better execution
    bid_ask_spread_bps=2.0  # Tighter spreads
)

