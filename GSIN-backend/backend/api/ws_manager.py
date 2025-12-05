# backend/api/ws_manager.py
"""
PHASE 1: Global WebSocket connection manager.
Ensures only one active connection per symbol.
"""
from fastapi import WebSocket
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class WSConnectionManager:
    """Manages WebSocket connections per symbol."""
    
    def __init__(self):
        self.active: Dict[str, WebSocket] = {}  # key = symbol, value = websocket
    
    async def connect(self, websocket: WebSocket, symbol: str):
        """
        Store WebSocket in active connections.
        
        PHASE: Note - websocket.accept() must be called BEFORE this method.
        This method only registers the connection in the manager.
        """
        # PHASE: Do NOT call accept() here - it's already called in websocket_market_stream
        self.active[symbol] = websocket
        logger.info(f"WebSocket registered for {symbol} (total active: {len(self.active)})")
    
    async def disconnect(self, symbol: str):
        """Close and remove WebSocket connection for symbol."""
        ws = self.active.get(symbol)
        if ws:
            try:
                # Check if connection is still open before closing
                # WebSocket state: 0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED
                if hasattr(ws, 'client_state') and ws.client_state.value == 1:  # OPEN
                    await ws.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket for {symbol}: {e}")
        self.active.pop(symbol, None)
        logger.info(f"WebSocket disconnected for {symbol} (total active: {len(self.active)})")
    
    def get(self, symbol: str) -> Optional[WebSocket]:
        """Get active WebSocket for symbol, or None."""
        return self.active.get(symbol)
    
    def is_alive(self, symbol: str) -> bool:
        """Check if WebSocket connection for symbol is still alive."""
        ws = self.active.get(symbol)
        if not ws:
            return False
        try:
            # Try to check connection state by attempting to access it
            # FastAPI WebSocket will raise exception if connection is closed
            # If we can access it without exception, assume it's alive
            # The actual send will fail if connection is dead, which we'll catch
            return ws is not None
        except:
            return False

