# backend/brain/__init__.py
"""
Brain Layer (L3) - Full MCN Integration
Combines Strategy Engine (L2) + Market Data (L1) + MemoryClusterNetworks
"""

from .brain_router import router

__all__ = ["router"]

