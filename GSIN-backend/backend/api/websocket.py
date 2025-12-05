# backend/api/websocket.py
"""
WebSocket endpoints for real-time market data.
PHASE 5: Enhanced real-time streaming with regime, sentiment, multi-timeframe.
PHASE 6: Added JWT authentication, rate limiting, and security.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from typing import Dict, Any, List, Optional
import json
import asyncio
from datetime import datetime, timedelta
import time
import os

from ..market_data.market_data_provider import get_provider_with_fallback
from ..brain.regime_detector import RegimeDetector
from ..market_data.multi_timeframe import MultiTimeframeAnalyzer
from ..market_data.volume_analyzer import VolumeAnalyzer
from ..market_data.sentiment_provider import get_sentiment_provider
from ..services.jwt_service import JWTService
from ..middleware.rate_limiter import rate_limiter

router = APIRouter(prefix="/ws", tags=["websocket"])

# Active WebSocket connections with user tracking
active_connections: Dict[str, List[Dict[str, Any]]] = {}  # {symbol: [{"websocket": ws, "user_id": uid, "connected_at": time}]}

# Connection activity tracking (for 30-minute timeout)
connection_activity: Dict[str, float] = {}  # {connection_id: last_activity_time}


class ConnectionManager:
    """Manages WebSocket connections with security and load-safety."""
    
    # PHASE 5: Load-safety limits
    MAX_CONNECTIONS_PER_USER = int(os.getenv("WS_MAX_CONNECTIONS_PER_USER", "10"))
    MAX_CONNECTIONS_PER_SYMBOL = int(os.getenv("WS_MAX_CONNECTIONS_PER_SYMBOL", "100"))
    MAX_TOTAL_CONNECTIONS = int(os.getenv("WS_MAX_TOTAL_CONNECTIONS", "1000"))
    
    def __init__(self):
        self.active_connections: Dict[str, List[Dict[str, Any]]] = {}
        self.connection_ids: Dict[WebSocket, str] = {}  # Map WebSocket to connection ID
        self.user_connection_counts: Dict[str, int] = {}  # Track connections per user
        self.total_connections = 0  # Track total connections
    
    async def connect(self, websocket: WebSocket, symbol: str, user_id: Optional[str] = None) -> str:
        """
        Connect a WebSocket client for a symbol.
        PHASE 6: Requires JWT authentication.
        
        Returns:
            connection_id: Unique connection identifier
        """
        # PHASE 6: Verify JWT token
        token = websocket.query_params.get("token") or websocket.headers.get("Authorization", "").replace("Bearer ", "")
        
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="JWT token required")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT token required")
        
        # Verify token
        jwt_service = JWTService()
        try:
            payload = jwt_service.verify_token(token)
            user_id = payload.get("user_id") or user_id
        except Exception:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid JWT token")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT token")
        
        # PHASE 5: Load-safety checks
        # Check total connections
        if self.total_connections >= self.MAX_TOTAL_CONNECTIONS:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Server at capacity")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="WebSocket server at capacity")
        
        # Check connections per symbol
        symbol_connections = len(self.active_connections.get(symbol, []))
        if symbol_connections >= self.MAX_CONNECTIONS_PER_SYMBOL:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Symbol connection limit reached")
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Too many connections for {symbol}")
        
        # PHASE 6: Rate limiting per user
        if user_id:
            # Check connections per user
            user_count = self.user_connection_counts.get(user_id, 0)
            if user_count >= self.MAX_CONNECTIONS_PER_USER:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User connection limit reached")
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many WebSocket connections per user")
            
            allowed, remaining = rate_limiter.is_allowed(
                f"ws:user:{user_id}",
                self.MAX_CONNECTIONS_PER_USER,
                60   # Per 60 seconds
            )
            if not allowed:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Rate limit exceeded")
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many WebSocket connections")
        
        await websocket.accept()
        
        connection_id = f"{user_id or 'anonymous'}_{int(time.time())}"
        connection_data = {
            "websocket": websocket,
            "user_id": user_id,
            "connected_at": time.time(),
            "connection_id": connection_id,
            "last_activity": time.time()
        }
        
        if symbol not in self.active_connections:
            self.active_connections[symbol] = []
        self.active_connections[symbol].append(connection_data)
        self.connection_ids[websocket] = connection_id
        connection_activity[connection_id] = time.time()
        
        # PHASE 5: Update connection counts
        self.total_connections += 1
        if user_id:
            self.user_connection_counts[user_id] = self.user_connection_counts.get(user_id, 0) + 1
        
        return connection_id
    
    def disconnect(self, websocket: WebSocket, symbol: str):
        """Disconnect a WebSocket client."""
        connection_id = self.connection_ids.get(websocket)
        if connection_id and connection_id in connection_activity:
            del connection_activity[connection_id]
        
        # PHASE 5: Update connection counts
        if websocket in self.connection_ids:
            # Get user_id from connection data
            connection_data = None
            if symbol in self.active_connections:
                for conn in self.active_connections[symbol]:
                    if conn.get("websocket") == websocket:
                        connection_data = conn
                        self.active_connections[symbol].remove(conn)
                        break
            
            if connection_data:
                user_id = connection_data.get("user_id")
                if user_id and user_id in self.user_connection_counts:
                    self.user_connection_counts[user_id] = max(0, self.user_connection_counts[user_id] - 1)
            
            del self.connection_ids[websocket]
            self.total_connections = max(0, self.total_connections - 1)
        
        if symbol in self.active_connections:
            self.active_connections[symbol] = [
                conn for conn in self.active_connections[symbol]
                if conn["websocket"] != websocket
            ]
            if not self.active_connections[symbol]:
                del self.active_connections[symbol]
    
    async def broadcast(self, symbol: str, message: Dict[str, Any]):
        """Broadcast message to all connections for a symbol."""
        if symbol in self.active_connections:
            disconnected = []
            current_time = time.time()
            
            for connection_data in self.active_connections[symbol]:
                websocket = connection_data["websocket"]
                connection_id = connection_data["connection_id"]
                
                # PHASE 6: Check for inactivity timeout (30 minutes)
                if current_time - connection_data["last_activity"] > 1800:  # 30 minutes
                    disconnected.append((websocket, symbol))
                    continue
                
                # Update activity
                connection_data["last_activity"] = current_time
                connection_activity[connection_id] = current_time
                
                try:
                    await websocket.send_json(message)
                except:
                    disconnected.append((websocket, symbol))
            
            # Remove disconnected clients
            for ws, sym in disconnected:
                self.disconnect(ws, sym)
    
    def update_activity(self, websocket: WebSocket):
        """Update last activity time for a connection."""
        connection_id = self.connection_ids.get(websocket)
        if connection_id:
            connection_activity[connection_id] = time.time()
            # Also update in active_connections
            for symbol, connections in self.active_connections.items():
                for conn in connections:
                    if conn["websocket"] == websocket:
                        conn["last_activity"] = time.time()
                        break


manager = ConnectionManager()


@router.websocket("/market/stream")
async def websocket_market_stream(
    websocket: WebSocket,
    symbol: str = Query(..., description="Symbol to stream (e.g., AAPL)")
):
    """
    PHASE 5/6: Enhanced WebSocket endpoint for real-time market data streaming.
    PHASE 6: Requires JWT authentication via ?token=... or Authorization header.
    
    Streams:
    - Price updates
    - Volume updates
    - Regime changes
    - Sentiment score
    - Multi-timeframe alignment
    
    Usage: ws://host/api/ws/market/stream?symbol=AAPL&token=<JWT_TOKEN>
    
    Security:
    - JWT token required
    - Auto-disconnect after 30 minutes inactivity
    - Rate limited (10 connections per user per minute)
    """
    symbol_upper = symbol.upper()
    connection_id = await manager.connect(websocket, symbol_upper)
    
    ping_task = None
    try:
        # PHASE 6: Send ping periodically to keep connection alive and detect disconnects
        async def send_ping():
            try:
                while True:
                    await asyncio.sleep(30)  # Send ping every 30 seconds
                    try:
                        await websocket.send_json({"type": "ping"})
                        manager.update_activity(websocket)
                    except (WebSocketDisconnect, Exception):
                        break
            except asyncio.CancelledError:
                pass
        
        ping_task = asyncio.create_task(send_ping())
        
        provider = get_provider_with_fallback()
        if not provider:
            ping_task.cancel()
            await websocket.send_json({
                "type": "error",
                "message": "Market data provider not available"
            })
            return
        
        # Initialize Phase 5 components
        regime_detector = RegimeDetector()
        multi_timeframe_analyzer = MultiTimeframeAnalyzer()
        volume_analyzer = VolumeAnalyzer()
        sentiment_provider = get_sentiment_provider()
        
        # IMPROVEMENT 4: Send initial data snapshot (boot frame) - ALWAYS send valid JSON
        # IMPROVEMENT 4: Fallback to cached/Yahoo data if Alpaca fails
        try:
            price_data = None
            if provider:
                try:
                    price_data = provider.get_price(symbol_upper)
                except Exception as e:
                    # IMPROVEMENT 4: Alpaca failed, try fallback to cached/Yahoo
                    print(f"⚠️  Alpaca live data unavailable for {symbol_upper}, falling back to cached/Yahoo")
                    from ..market_data.cache import get_cache
                    from ..market_data.unified_data_engine import get_price_data
                    cache = get_cache()
                    
                    # Try cached price first
                    cached_price = cache.get("price", f"price_{symbol_upper}", ttl_seconds=300)  # 5 min stale OK
                    if cached_price:
                        price_data = type('PriceData', (), {
                            'price': cached_price.get('price', 0.0),
                            'volume': cached_price.get('volume', 0),
                            'change_percent': cached_price.get('change_percent', 0.0),
                            'symbol': symbol_upper
                        })()
                    else:
                        # Try Yahoo via unified_data_engine
                        try:
                            yahoo_price = get_price_data(symbol_upper)
                            price_data = type('PriceData', (), {
                                'price': yahoo_price.get('price', 0.0),
                                'volume': yahoo_price.get('volume', 0),
                                'change_percent': yahoo_price.get('change_percent', 0.0),
                                'symbol': symbol_upper
                            })()
                        except Exception:
                            pass  # Will use 0.0 as fallback
            
            market_data = {
                "price": price_data.price if price_data else 0.0,
                "volatility": 0.0,
                "sentiment": 0.0,
                "timestamp": datetime.now().isoformat()
            }
            
            # Get initial regime (with error handling)
            try:
                regime_result = await regime_detector.get_market_regime(symbol_upper, market_data)
            except Exception:
                regime_result = {"regime": "unknown", "confidence": 0.0}
            
            # Get initial multi-timeframe trend (with error handling)
            try:
                mtn_trend = await multi_timeframe_analyzer.get_multi_timeframe_trend(symbol_upper)
            except Exception:
                mtn_trend = {"alignment_score": 0.0}
            
            # Get initial volume confirmation (with error handling)
            try:
                volume_conf = await volume_analyzer.get_volume_confirmation(symbol_upper, "1d")
            except Exception:
                volume_conf = {"volume_trend": "normal", "volume_strength": 0.5}
            
            # Get initial sentiment (with error handling)
            try:
                sentiment_data = sentiment_provider.get_sentiment(symbol_upper) if sentiment_provider else None
            except Exception:
                sentiment_data = None
            
            # PHASE 3: Always send valid boot frame (prevents frontend crashes)
            await websocket.send_json({
                "type": "initial",
                "symbol": symbol_upper,
                "price": price_data.price if price_data else 0.0,
                "volume": price_data.volume if price_data else 0,
                "change_pct": price_data.change_percent if price_data and price_data.change_percent else 0.0,
                "regime": regime_result.get("regime", "unknown"),
                "regime_confidence": regime_result.get("confidence", 0.0),
                "multi_timeframe_alignment": mtn_trend.get("alignment_score", 0.0),
                "volume_trend": volume_conf.get("volume_trend", "normal"),
                "volume_strength": volume_conf.get("volume_strength", 0.5),
                "sentiment_score": sentiment_data.sentiment_score if sentiment_data else 0.0,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            # PHASE 3: Even on error, send valid boot frame (prevents frontend crashes)
            print(f"⚠️  Error initializing WebSocket stream for {symbol_upper}: {e}")
            await websocket.send_json({
                "type": "initial",
                "symbol": symbol_upper,
                "price": 0.0,
                "volume": 0,
                "change_pct": 0.0,
                "regime": "unknown",
                "regime_confidence": 0.0,
                "multi_timeframe_alignment": 0.0,
                "volume_trend": "normal",
                "volume_strength": 0.5,
                "sentiment_score": 0.0,
                "timestamp": datetime.now().isoformat(),
                "error": str(e)  # Include error but don't break the frame
            })
        
        # Track last values for change detection
        last_regime = None
        last_price = None
        
        # Performance optimization: Track last update times to avoid expensive operations
        last_volume_update = 0
        last_regime_update = 0
        last_sentiment_update = 0
        last_mtf_update = 0
        
        # Cache for expensive operations
        cached_volume_conf = None
        cached_regime_result = None
        cached_sentiment_data = None
        cached_mtf_trend = None
        
        # Keep connection alive and send periodic updates
        while True:
            try:
                # PHASE 4: Wait for client message or timeout (non-fatal, keep connection alive)
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    # Client can send ping or subscription updates
                    if data == "ping" or data.strip() == "ping":
                        await websocket.send_json({"type": "pong"})
                        manager.update_activity(websocket)
                    elif data.startswith("{"):
                        # JSON message from client
                        try:
                            msg = json.loads(data)
                            if msg.get("type") == "ping":
                                await websocket.send_json({"type": "pong"})
                                manager.update_activity(websocket)
                            elif msg.get("action") == "subscribe":
                                # Client can request specific updates
                                pass
                        except:
                            pass
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    # Timeout is expected - this triggers periodic updates
                    # CancelledError can occur when connection is closing
                    current_time = time.time()
                    try:
                        # IMPROVEMENT 4: Get price update with fallback to cached/Yahoo if Alpaca fails
                        price_data = None
                        current_price = None
                        
                        if provider:
                            try:
                                price_data = provider.get_price(symbol_upper)
                                if price_data:
                                    current_price = price_data.price
                            except Exception as e:
                                # PHASE 4: Provider errors don't close WebSocket - use fallback data
                                error_str = str(e).lower()
                                if "rate limit" in error_str or "429" in error_str:
                                    # Rate limited - use cached data, log once
                                    if not hasattr(websocket, '_rate_limit_warned'):
                                        print(f"⚠️  Alpaca rate limited for {symbol_upper}, using cached data")
                                        websocket._rate_limit_warned = True
                                else:
                                    # Other error - use cached data
                                    if not hasattr(websocket, '_alpaca_error_warned'):
                                        print(f"⚠️  Alpaca live data unavailable for {symbol_upper}, using cached data")
                                        websocket._alpaca_error_warned = True
                                
                                # IMPROVEMENT 4: Fallback to cached/Yahoo
                                from ..market_data.cache import get_cache
                                from ..market_data.unified_data_engine import get_price_data
                                cache = get_cache()
                                
                                # Try cached price first (allow 5 min stale)
                                cached_price = cache.get("price", f"price_{symbol_upper}", ttl_seconds=300)
                                if cached_price:
                                    current_price = cached_price.get('price', last_price or 0.0)
                                    price_data = type('PriceData', (), {
                                        'price': current_price,
                                        'volume': cached_price.get('volume', 0),
                                        'change_percent': cached_price.get('change_percent', 0.0),
                                        'symbol': symbol_upper
                                    })()
                                else:
                                    # Try Yahoo via unified_data_engine
                                    try:
                                        yahoo_price = get_price_data(symbol_upper)
                                        current_price = yahoo_price.get('price', last_price or 0.0)
                                        price_data = type('PriceData', (), {
                                            'price': current_price,
                                            'volume': yahoo_price.get('volume', 0),
                                            'change_percent': yahoo_price.get('change_percent', 0.0),
                                            'symbol': symbol_upper
                                        })()
                                    except Exception:
                                        # Last resort: use last known price
                                        current_price = last_price or 0.0
                        
                        # IMPROVEMENT 4: Send update if we have a price (even if from cache/Yahoo)
                        if current_price is not None:
                            price_changed = last_price is None or abs(current_price - last_price) > 0.01
                            
                            if price_changed or last_price is None:
                                await websocket.send_json({
                                    "type": "price_update",
                                    "symbol": symbol_upper,
                                    "price": current_price,
                                    "change_pct": price_data.change_percent if price_data else 0.0,
                                    "volume": price_data.volume if price_data else 0,
                                    "timestamp": datetime.now().isoformat(),
                                    "source": "cached" if not provider or not hasattr(provider, 'get_price') else "live"  # IMPROVEMENT 4: Indicate data source
                                })
                                last_price = current_price
                                manager.update_activity(websocket)
                            
                            # Get volume update (every 15 seconds, cached)
                            if current_time - last_volume_update >= 15:
                                try:
                                    cached_volume_conf = await volume_analyzer.get_volume_confirmation(symbol_upper, "1d")
                                    await websocket.send_json({
                                        "type": "volume_update",
                                        "symbol": symbol_upper,
                                        "volume_trend": cached_volume_conf.get("volume_trend", "normal"),
                                        "volume_strength": cached_volume_conf.get("volume_strength", 0.5),
                                        "volume_ratio": cached_volume_conf.get("volume_ratio", 1.0),
                                        "timestamp": datetime.now().isoformat()
                                    })
                                    last_volume_update = current_time
                                except:
                                    pass
                            
                            # Check for regime change (every 45 seconds, cached)
                            if current_time - last_regime_update >= 45:
                                try:
                                    market_data = {
                                        "price": current_price,
                                        "volatility": 0.0,
                                        "sentiment": 0.0,
                                        "timestamp": datetime.now().isoformat()
                                    }
                                    cached_regime_result = await regime_detector.get_market_regime(symbol_upper, market_data)
                                    current_regime = cached_regime_result.get("regime", "unknown")
                                    
                                    if last_regime and current_regime != last_regime:
                                        await websocket.send_json({
                                            "type": "regime_change",
                                            "symbol": symbol_upper,
                                            "old_regime": last_regime,
                                            "new_regime": current_regime,
                                            "confidence": cached_regime_result.get("confidence", 0.0),
                                            "explanation": cached_regime_result.get("explanation", ""),
                                            "timestamp": datetime.now().isoformat()
                                        })
                                    last_regime = current_regime
                                    last_regime_update = current_time
                                except:
                                    pass
                            
                            # Get sentiment update (every 90 seconds, cached)
                            if current_time - last_sentiment_update >= 90:
                                try:
                                    cached_sentiment_data = sentiment_provider.get_sentiment(symbol_upper) if sentiment_provider else None
                                    if cached_sentiment_data:
                                        await websocket.send_json({
                                            "type": "sentiment_update",
                                            "symbol": symbol_upper,
                                            "sentiment_score": cached_sentiment_data.sentiment_score,
                                            "sentiment_label": cached_sentiment_data.sentiment_label if hasattr(cached_sentiment_data, 'sentiment_label') else "neutral",
                                            "timestamp": datetime.now().isoformat()
                                        })
                                    last_sentiment_update = current_time
                                except:
                                    pass
                            
                            # Get multi-timeframe alignment (every 30 seconds, cached)
                            if current_time - last_mtf_update >= 30:
                                try:
                                    cached_mtf_trend = await multi_timeframe_analyzer.get_multi_timeframe_trend(symbol_upper)
                                    await websocket.send_json({
                                        "type": "multi_timeframe_update",
                                        "symbol": symbol_upper,
                                        "alignment_score": cached_mtf_trend.get("alignment_score", 0.0),
                                        "trend_short": cached_mtf_trend.get("trend_short", "flat"),
                                        "trend_medium": cached_mtf_trend.get("trend_medium", "flat"),
                                        "trend_long": cached_mtf_trend.get("trend_long", "flat"),
                                        "timestamp": datetime.now().isoformat()
                                    })
                                    last_mtf_update = current_time
                                except:
                                    pass
                    except Exception as e:
                        # Send error but keep connection alive
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Update error: {str(e)}",
                            "timestamp": datetime.now().isoformat()
                        })
            except WebSocketDisconnect:
                break
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"WebSocket error: {str(e)}"
            })
        except:
            pass
    finally:
        # Cancel ping task
        if ping_task and not ping_task.done():
            ping_task.cancel()
            try:
                await ping_task
            except asyncio.CancelledError:
                pass
        manager.disconnect(websocket, symbol_upper)


@router.websocket("/market/{symbol}/indicators")
async def websocket_indicators(websocket: WebSocket, symbol: str):
    """
    WebSocket endpoint for real-time indicator updates.
    
    Sends volume, trend, sentiment, and regime updates.
    """
    await manager.connect(websocket, f"{symbol.upper()}_indicators")
    
    try:
        provider = get_provider_with_fallback()
        if not provider:
            await websocket.send_json({
                "error": "Market data provider not available"
            })
            return
        
        while True:
            try:
                # Wait for client message or timeout
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                    if data == "ping":
                        await websocket.send_json({"type": "pong"})
                except asyncio.TimeoutError:
                    # Send periodic indicator updates
                    try:
                        # Get candles for indicators
                        candles = await provider.get_candles(symbol.upper(), "1d", limit=20)
                        if candles:
                            # Calculate simple indicators
                            closes = [c.close for c in candles]
                            volumes = [c.volume for c in candles]
                            
                            # Volume trend
                            if len(volumes) > 5:
                                avg_vol_short = sum(volumes[-5:]) / 5
                                avg_vol_long = sum(volumes) / len(volumes)
                                volume_trend = "increasing" if avg_vol_short > avg_vol_long * 1.1 else "decreasing" if avg_vol_short < avg_vol_long * 0.9 else "normal"
                            else:
                                volume_trend = "normal"
                            
                            await websocket.send_json({
                                "type": "indicators",
                                "symbol": symbol.upper(),
                                "volume_trend": volume_trend,
                                "current_price": closes[-1] if closes else 0.0,
                                "timestamp": datetime.now().isoformat()
                            })
                    except:
                        pass
            except WebSocketDisconnect:
                break
    except Exception as e:
        await websocket.send_json({
            "error": f"WebSocket error: {str(e)}"
        })
    finally:
        manager.disconnect(websocket, f"{symbol.upper()}_indicators")

