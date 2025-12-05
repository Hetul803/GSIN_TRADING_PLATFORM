# backend/broker/__init__.py
"""
Broker Layer - Unified interface for PAPER and REAL trading.
Supports Alpaca (real) and Paper (simulated) trading.
"""

from .router import router

__all__ = ["router"]

