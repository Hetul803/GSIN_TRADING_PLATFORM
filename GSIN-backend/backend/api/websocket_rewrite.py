# backend/api/websocket_rewrite.py
"""
PHASE 2: Rewritten WebSocket handler - stable and sane.
- Only one connection per symbol
- No heartbeat tasks
- No background tasks
- No infinite reconnect loops
- No parallel handlers per symbol
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, Any, Optional
import asyncio
import logging
from datetime import datetime, timezone

from .ws_manager import WSConnectionManager

logger = logging.getLogger(__name__)
# PHASE 4: Disable WebSocket debug logging spam
logger.setLevel(logging.WARNING)

router = APIRouter(prefix="/ws", tags=["websocket"])

# PHASE 1: Global connection manager
manager = WSConnectionManager()


async def get_live_snapshot(symbol: str) -> Optional[Dict[str, Any]]:
    """
    PHASE 3: Get live market data snapshot with sentiment, volume, regime.
    Returns None on error (caller should handle gracefully).
    """
    try:
        from ..market_data.market_data_provider import get_provider_with_fallback
        from ..market_data.services.twelvedata_context import get_twelvedata_context_service
        from ..brain.regime_detector import RegimeDetector
        
        # Use call_with_fallback for queue integration (adds ~1-5ms latency, cache hit = 0ms)
        from ..market_data.market_data_provider import call_with_fallback
        
        try:
            # Get price data through queue (cache hit = 0ms, cache miss = ~1-5ms overhead)
            price_data = call_with_fallback("get_price", symbol)
            if not price_data or not hasattr(price_data, 'price') or not price_data.price:
                return None
            
            snapshot = {
                "price": price_data.price,
                "change_pct": getattr(price_data, 'change_percent', 0.0),
                "timestamp": price_data.timestamp.isoformat() if hasattr(price_data.timestamp, 'isoformat') else str(price_data.timestamp),
            }
            
            # PHASE: Get volume from OHLCV (if available) - ensure default is 0
            try:
                # Use queue for candles (cache hit = 0ms, cache miss = ~1-5ms overhead)
                candles = call_with_fallback("get_candles", symbol, "1d", limit=1)
                if candles and len(candles) > 0:
                    snapshot["volume"] = candles[0].volume or 0
                else:
                    snapshot["volume"] = 0
            except Exception:
                snapshot["volume"] = getattr(price_data, 'volume', None) or 0
        except Exception:
            return None
        
        # PHASE: Get sentiment from Twelve Data context - ensure default is "neutral"
        try:
            twelve_context = get_twelvedata_context_service()
            sentiment_data = twelve_context.get_symbol_sentiment(symbol)
            if sentiment_data and isinstance(sentiment_data, dict):
                # Extract sentiment string from dict
                score = sentiment_data.get("sentiment_score", 0.0)
                if score > 0.1:
                    snapshot["sentiment"] = "bullish"
                elif score < -0.1:
                    snapshot["sentiment"] = "bearish"
                else:
                    snapshot["sentiment"] = "neutral"
            else:
                snapshot["sentiment"] = "neutral"
        except Exception:
            snapshot["sentiment"] = "neutral"
        
        # STABILITY: Get regime from regime detector - always safe, defaults to "unknown"
        try:
            regime_detector = RegimeDetector()
            regime_result = regime_detector.get_market_regime(symbol)
            if regime_result and isinstance(regime_result, dict):
                snapshot["regime"] = regime_result.get("regime", "unknown")
                snapshot["volatility"] = regime_result.get("volatility")
                snapshot["risk_level"] = regime_result.get("risk_level", "normal")
            else:
                snapshot["regime"] = "unknown"
                snapshot["volatility"] = None
                snapshot["risk_level"] = "normal"
        except Exception:
            snapshot["regime"] = "unknown"
            snapshot["volatility"] = None
            snapshot["risk_level"] = "normal"
        
        return snapshot
    except Exception as e:
        logger.warning(f"Error fetching live snapshot for {symbol}: {e}")
        return None


@router.websocket("/market/stream")
async def websocket_market_stream(
    websocket: WebSocket,
    symbol: str = Query(..., description="Symbol to stream (e.g., AAPL)"),
    token: str = Query(None, description="JWT token for authentication (optional)")
):
    """
    PHASE B: Stable WebSocket handler for market data streaming.
    
    Key rules:
    - websocket.accept() called at the very top
    - Simplified loop: only send ticks, no heartbeat/ping/pong spam
    - No client message timeout logic
    - No status/no-data spam
    """
    symbol_upper = symbol.upper()
    
    # PHASE B: websocket.accept() at the very top before any other operations
    try:
        await websocket.accept()
    except Exception as e:
        logger.warning(f"WebSocket accept() failed for {symbol_upper}: {e}")
        return
    
    # PHASE B: Handle existing connections - only replace if truly dead
    existing = manager.get(symbol_upper)
    if existing:
        # Check if existing connection is still alive by trying to use it
        try:
            # Try to send a ping - if this succeeds, connection is alive
            await existing.send_json({"type": "ping"})
            # Connection is alive - reject new connection to prevent duplicates
            logger.info(f"WebSocket connection for {symbol_upper} already exists and is alive, rejecting duplicate")
            try:
                await websocket.close(code=1008, reason="Connection already exists")
            except:
                pass
            return
        except Exception:
            # Existing connection is dead - clean it up and accept new one
            logger.info(f"Existing WebSocket for {symbol_upper} is dead, cleaning up and accepting new connection")
            try:
                await manager.disconnect(symbol_upper)
            except:
                pass
    
    # PHASE B: Connect (registers with manager - accept already called)
    await manager.connect(websocket, symbol_upper)
    logger.info(f"WebSocket connected for {symbol_upper}")
    
    try:
        # PHASE B: Simplified main loop - only send ticks, no heartbeat/ping/pong
        while True:
            try:
                snapshot = await get_live_snapshot(symbol_upper)
                if snapshot:
                    await websocket.send_json({
                        "type": "tick",
                        "symbol": symbol_upper,
                        "data": snapshot
                    })
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for {symbol_upper}")
                break
            except Exception as e:
                # Log error but keep connection alive
                logger.warning(f"Error sending snapshot for {symbol_upper}: {e}")
            await asyncio.sleep(1.0)
    
    except WebSocketDisconnect:
        # Client disconnected normally
        logger.info(f"WebSocket client disconnected for {symbol_upper}")
    except Exception as e:
        # Unexpected error - log but don't crash
        logger.error(f"WebSocket error for {symbol_upper}: {e}")
    finally:
        # PHASE B: Always disconnect in finally
        await manager.disconnect(symbol_upper)
        logger.info(f"WebSocket cleaned up for {symbol_upper}")
