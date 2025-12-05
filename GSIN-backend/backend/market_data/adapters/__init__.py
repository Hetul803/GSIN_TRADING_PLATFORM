# backend/market_data/adapters/__init__.py
"""
Market data provider adapters.
Each adapter implements the BaseMarketDataProvider interface.
"""
from .polygon_adapter import PolygonDataProvider
from .alpaca_adapter import AlpacaDataProvider

__all__ = ["PolygonDataProvider", "AlpacaDataProvider"]
