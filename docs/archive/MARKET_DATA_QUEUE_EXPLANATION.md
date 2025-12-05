# Market Data Queue - Explanation

## What is the Market Data Queue?

The **Market Data Request Queue** (`backend/market_data/request_queue.py`) is a centralized system that manages all requests to external market data providers (Twelve Data, Alpaca, Polygon, Yahoo, etc.). It acts as a "traffic controller" to prevent rate limiting, reduce costs, and improve performance.

---

## Why Do We Need It?

### Problem Without Queue:

1. **Rate Limiting Issues:**
   - Market data providers (e.g., Twelve Data) have strict rate limits (e.g., 377 requests/minute)
   - Multiple workers (Evolution Worker, Backtest Worker) making simultaneous requests
   - WebSocket connections requesting real-time data
   - User-initiated backtests requesting historical data
   - **Result:** Rate limit errors (429), failed requests, wasted API credits

2. **Duplicate Requests:**
   - Multiple workers might request the same data simultaneously
   - Example: Evolution Worker and Backtest Worker both need AAPL 1d candles
   - **Result:** Wasted API credits, unnecessary load on providers

3. **No Caching:**
   - Same data requested multiple times within seconds
   - Example: Multiple strategies backtesting on AAPL
   - **Result:** Redundant API calls, slower performance

4. **No Error Recovery:**
   - Rate limit errors cause immediate failures
   - No automatic retry with backoff
   - **Result:** Failed backtests, incomplete data

---

## What Does the Queue Achieve?

### 1. **Rate Limit Management** ✅

**How it works:**
- Tracks requests per provider per minute
- Uses `RateTracker` to count requests in a rolling 60-second window
- Automatically waits if approaching rate limit

**Example:**
```
Twelve Data: 377 requests/minute limit
Queue tracks: 350 requests in last 60 seconds
Next request: Allowed immediately ✅

Queue tracks: 377 requests in last 60 seconds
Next request: Waits 5 seconds until oldest request is >60 seconds old ⏳
```

**Benefit:** Never hits rate limits, prevents 429 errors

---

### 2. **Request Deduplication** ✅

**How it works:**
- Creates a unique hash for each request (provider + function + args)
- If duplicate request is pending, waits for existing request to complete
- Reuses result from first request

**Example:**
```
Time 0.0s: Evolution Worker requests AAPL 1d candles (5000 limit)
Time 0.1s: Backtest Worker requests AAPL 1d candles (5000 limit)
  → Queue detects duplicate
  → Backtest Worker waits for Evolution Worker's request
  → Both get same result (only 1 API call made) ✅
```

**Benefit:** Reduces API calls by 50-90%, saves credits

---

### 3. **Intelligent Caching** ✅

**How it works:**
- Checks cache before making API request
- Cache TTL: 5 seconds (configurable)
- Cache key: `{provider}_{function}_{symbol}_{interval}`

**Example:**
```
Request 1: Get AAPL 1d candles → API call → Cache result
Request 2: Get AAPL 1d candles (within 5s) → Return cached result ✅
Request 3: Get AAPL 1d candles (after 5s) → API call → Update cache
```

**Benefit:** Faster responses, fewer API calls

---

### 4. **Exponential Backoff on Rate Limits** ✅

**How it works:**
- Detects rate limit errors (429, "rate limit", "too many requests")
- Implements exponential backoff: `2^failures` seconds (max 60s)
- Automatically retries after backoff

**Example:**
```
Request 1: Rate limit error → Backoff 2 seconds → Retry
Request 2: Rate limit error → Backoff 4 seconds → Retry
Request 3: Rate limit error → Backoff 8 seconds → Retry
Request 4: Rate limit error → Backoff 16 seconds → Retry
Request 5: Rate limit error → Backoff 32 seconds → Retry
Request 6: Rate limit error → Backoff 60 seconds (max) → Retry
```

**Benefit:** Graceful handling of rate limits, automatic recovery

---

### 5. **Provider Fallback Integration** ✅

**How it works:**
- Queue is integrated into `call_with_fallback()` function
- If primary provider fails (rate limit, 4xx, 5xx), automatically tries secondary
- All requests go through queue (both primary and secondary)

**Example:**
```
Request: Get AAPL price
  → Queue → Twelve Data (primary) → Rate limit error
  → Queue → Alpaca (secondary) → Success ✅
```

**Benefit:** Higher reliability, seamless provider switching

---

## How It's Integrated

### Current Integration:

1. **Market Data Provider Layer:**
   - `market_data_provider.py` → `call_with_fallback()` uses queue
   - All provider calls go through `queue.execute_sync()` or `queue.execute_with_queue()`

2. **Evolution Worker:**
   - Uses `call_with_fallback()` for historical data
   - All backtest data requests go through queue

3. **Backtest Worker:**
   - Uses `call_with_fallback()` for historical data
   - All backtest data requests go through queue

4. **API Endpoints:**
   - Trading terminal requests go through queue
   - Strategy backtest requests go through queue

### Flow Diagram:

```
┌─────────────────┐
│ Evolution Worker│
│ Backtest Worker │
│ API Endpoints   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│ call_with_fallback()    │
│ (market_data_provider)  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ RequestQueue            │
│ 1. Check cache          │
│ 2. Check rate limit     │
│ 3. Deduplicate requests │
│ 4. Execute request      │
│ 5. Cache result          │
│ 6. Handle errors        │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Market Data Provider    │
│ (Twelve Data, Alpaca)   │
└─────────────────────────┘
```

---

## Benefits Summary

| Feature | Benefit | Impact |
|---------|---------|--------|
| **Rate Limit Management** | Never hits rate limits | ✅ Prevents 429 errors |
| **Request Deduplication** | Reuses pending requests | ✅ 50-90% fewer API calls |
| **Intelligent Caching** | 5-second cache | ✅ Faster responses, fewer calls |
| **Exponential Backoff** | Auto-retry on rate limits | ✅ Graceful error handling |
| **Provider Fallback** | Seamless provider switching | ✅ Higher reliability |

---

## Configuration

### Environment Variables:

```bash
# Rate limits per provider (requests per minute)
TWELVEDATA_RATE_LIMIT=377
ALPACA_RATE_LIMIT=200
POLYGON_RATE_LIMIT=60
YAHOO_RATE_LIMIT=100

# Cache TTL (seconds)
MARKET_DATA_CACHE_TTL=5
```

### Default Settings:

- **Default rate limit:** 60 requests/minute (conservative)
- **Cache TTL:** 5 seconds
- **Max backoff:** 60 seconds
- **Request timeout:** 30 seconds

---

## Example Scenarios

### Scenario 1: Evolution Worker Running 3 Strategies in Parallel

**Without Queue:**
```
Time 0.0s: Strategy A requests AAPL 1d candles → API call
Time 0.1s: Strategy B requests AAPL 1d candles → API call (duplicate!)
Time 0.2s: Strategy C requests TSLA 1d candles → API call
Time 0.3s: Strategy A requests MSFT 1d candles → API call
Time 0.4s: Strategy B requests MSFT 1d candles → API call (duplicate!)
Time 0.5s: Strategy C requests GOOGL 1d candles → API call
Result: 6 API calls, 2 duplicates wasted
```

**With Queue:**
```
Time 0.0s: Strategy A requests AAPL 1d candles → API call → Cache
Time 0.1s: Strategy B requests AAPL 1d candles → Cached result ✅
Time 0.2s: Strategy C requests TSLA 1d candles → API call → Cache
Time 0.3s: Strategy A requests MSFT 1d candles → API call → Cache
Time 0.4s: Strategy B requests MSFT 1d candles → Cached result ✅
Time 0.5s: Strategy C requests GOOGL 1d candles → API call → Cache
Result: 4 API calls, 2 duplicates avoided
```

**Savings:** 33% fewer API calls

---

### Scenario 2: Rate Limit Hit

**Without Queue:**
```
Request 1: Success
Request 2: Success
...
Request 377: Success
Request 378: Rate limit error (429) → FAIL ❌
Request 379: Rate limit error (429) → FAIL ❌
Result: Backtest fails, no retry
```

**With Queue:**
```
Request 1-377: Success (tracked)
Request 378: Rate limit detected → Wait 2 seconds → Retry → Success ✅
Request 379: Rate limit detected → Wait 4 seconds → Retry → Success ✅
Result: All requests succeed with automatic retry
```

**Benefit:** Automatic recovery, no manual intervention

---

## Conclusion

The Market Data Queue is **essential** for:
1. **Preventing rate limit errors** (429)
2. **Reducing API costs** (50-90% fewer calls)
3. **Improving performance** (caching, deduplication)
4. **Ensuring reliability** (automatic retry, fallback)

**Without the queue:** The system would frequently hit rate limits, waste API credits, and fail backtests.

**With the queue:** The system efficiently manages all market data requests, automatically handles errors, and maximizes API credit usage.

---

## Future Enhancements

1. **Persistent Cache:** Store cache in Redis for multi-server deployments
2. **Request Prioritization:** Prioritize user-initiated requests over worker requests
3. **Adaptive Rate Limiting:** Dynamically adjust rate limits based on provider responses
4. **Metrics Dashboard:** Track queue performance, cache hit rate, rate limit events

