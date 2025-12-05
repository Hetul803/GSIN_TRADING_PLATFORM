# backend/strategy_engine/__init__.py
"""
Strategy Engine (Brain L2 Logic)
Core AI strategy management, backtesting, mutation, and signal generation.
"""

from .strategy_router import router

__all__ = ["router"]

