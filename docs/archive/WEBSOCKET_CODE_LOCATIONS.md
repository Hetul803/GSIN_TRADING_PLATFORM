# WebSocket Code Locations

## 1. Where WebSocket is Created (Backend)

**File:** `GSIN-backend/backend/api/websocket_rewrite.py`

```python
@router.websocket("/market/stream")
async def websocket_market_stream(
    websocket: WebSocket,
    symbol: str = Query(..., description="Symbol to stream (e.g., AAPL)"),
    token: str = Query(None, description="JWT token for authentication (optional)")
):
    """
    PHASE 2: Stable WebSocket handler for market data streaming.
    """
    symbol_upper = symbol.upper()
    
    # PHASE 2: Make sure only one active connection per symbol
    existing = manager.get(symbol_upper)
    if existing:
        await manager.disconnect(symbol_upper)
    
    # PHASE 2: Connect (accepts WebSocket)
    await manager.connect(websocket, symbol_upper)
    
    try:
        # Send initial connection status
        await websocket.send_json({
            "type": "status",
            "status": "connected",
            "symbol": symbol_upper
        })
        
        # Main loop
        while True:
            # Try receiving a client message with timeout
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                # Handle ping if needed
                if msg.strip().lower() == "ping":
                    try:
                        await websocket.send_json({"type": "pong"})
                    except:
                        break  # client disconnected
            except asyncio.TimeoutError:
                msg = None  # Expected - client is idle
            except (WebSocketDisconnect, Exception):
                break  # client disconnected or error
            
            # Fetch latest live data
            try:
                snapshot = await get_live_snapshot(symbol_upper)
                if snapshot:
                    await websocket.send_json({
                        "type": "tick",
                        "symbol": symbol_upper,
                        "data": snapshot
                    })
                else:
                    # Send no-data status
                    await websocket.send_json({
                        "type": "status",
                        "status": "no-data",
                        "symbol": symbol_upper
                    })
            except (WebSocketDisconnect, Exception) as e:
                # If sending fails, try to send error status
                try:
                    await websocket.send_json({
                        "type": "tick",
                        "symbol": symbol_upper,
                        "data": None,
                        "error": str(e) if isinstance(e, Exception) else "Unknown error"
                    })
                except:
                    break  # connection closed
            
            # Small sleep to avoid hammering providers
            await asyncio.sleep(0.8)
    
    except (WebSocketDisconnect, Exception):
        # Client disconnected or error - silently exit
        pass
    finally:
        # PHASE 2: Always disconnect in finally
        await manager.disconnect(symbol_upper)
```

---

## 2. Market Chart Uses for Live Price Updates

**File:** `GSIN.fin/app/terminal/page.tsx`

The terminal page uses `useMarketStream` hook for live price updates:

```typescript
const { data: streamData, connected: wsConnected, error: wsError, reconnect: wsReconnect } = useMarketStream(symbol);
```

**File:** `GSIN.fin/components/market-data-widget.tsx`

The MarketDataWidget component uses REST API polling (not WebSocket):
- Fetches from `/api/market/price?symbol=${symbol}` every 30 seconds
- Does NOT use WebSocket for live updates

---

## 3. Components Listening to Price Updates

**File:** `GSIN.fin/hooks/useMarketStream.ts`

The hook listens to WebSocket messages and updates state:

```typescript
ws.onmessage = (event) => {
  try {
    const message = JSON.parse(event.data);
    
    // Handle new WebSocket message format: {"type": "status|tick", ...}
    if (message.type === 'status') {
      if (message.status === 'connected') {
        setConnected(true);
        setError(null);
      } else if (message.status === 'no-data') {
        setConnected(true);
        setError(null);
      }
    } else if (message.type === 'tick') {
      // New tick data received
      if (message.data) {
        const newPrice = message.data.price;
        if (newPrice !== null && newPrice !== undefined) {
          lastPriceRef.current = newPrice;
          
          setData({
            price: newPrice,
            change_pct: message.data.change_pct || 0,
            volume: message.data.volume ?? null,
            sentiment: message.data.sentiment || null,
            regime: message.data.regime || null,
            timestamp: message.data.timestamp || new Date().toISOString(),
          });
          setConnected(true);
          setError(null);
        }
      }
    }
  } catch (err) {
    console.error('Error parsing WebSocket message:', err);
  }
};
```

**Components using this hook:**
- `GSIN.fin/app/terminal/page.tsx` - Uses `useMarketStream(symbol)` for live price updates

---

## 4. State Management: Zustand (NOT Context)

**File:** `GSIN.fin/lib/store.ts`

```typescript
import { create } from 'zustand';

export type TradingMode = 'paper' | 'real';
export type SubscriptionTier = 'user' | 'pro' | 'creator';

interface User {
  id: string;
  email: string;
  name: string;
  role?: string;
  subscriptionTier: SubscriptionTier;
  equity: number;
  paperEquity: number;
  realEquity: number;
  // ...
}

// Zustand store is used for global state management
// WebSocket hook uses local React state (useState), not Zustand
```

**Note:** The WebSocket hook (`useMarketStream`) uses **local React state** (`useState`), not Zustand. Zustand is used for other global app state (user, trades, strategies, etc.).

---

## 5. WebSocket URL Builder

**File:** `GSIN.fin/hooks/useMarketStream.ts`

```typescript
// Get JWT token for WebSocket authentication
const token = typeof window !== 'undefined' ? localStorage.getItem('gsin_token') : null;
if (!token) {
  setError('No authentication token');
  setConnected(false);
  return;
}

// Convert http:// to ws:// or https:// to wss://
let wsUrl = BACKEND_URL.replace(/^http/, 'ws');
// Ensure proper WebSocket protocol
if (wsUrl.startsWith('ws://') || wsUrl.startsWith('wss://')) {
  wsUrl = wsUrl + `/api/ws/market/stream?symbol=${symbolUpper}&token=${encodeURIComponent(token)}`;
} else {
  // Fallback: assume http and convert to ws
  wsUrl = `ws://${wsUrl.replace(/^https?:\/\//, '')}/api/ws/market/stream?symbol=${symbolUpper}&token=${encodeURIComponent(token)}`;
}

const ws = new WebSocket(wsUrl);
```

**URL Format:**
- Development: `ws://localhost:8000/api/ws/market/stream?symbol=AAPL&token=...`
- Production: `wss://your-domain.com/api/ws/market/stream?symbol=AAPL&token=...`

---

## Summary

1. **WebSocket Created:** `GSIN-backend/backend/api/websocket_rewrite.py` - `websocket_market_stream()` function
2. **Market Chart:** `GSIN.fin/app/terminal/page.tsx` - Uses `useMarketStream(symbol)` hook
3. **Price Updates Listener:** `GSIN.fin/hooks/useMarketStream.ts` - `ws.onmessage` handler
4. **State Management:** **Zustand** for global state, **React useState** for WebSocket hook state
5. **URL Builder:** `GSIN.fin/hooks/useMarketStream.ts` lines 89-97 - Converts `http://` to `ws://` and builds full URL

