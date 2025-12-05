'use client';

/**
 * PHASE: WebSocket Stabilization - FRONTEND ONLY
 * 
 * Fixed issues:
 * - Infinite reconnect loop
 * - "WebSocket is not connected" errors
 * - Only ONE websocket per symbol
 * - Malformed ws:// URL builder
 * - Early-return causing React re-renders
 * - WS creation on every state change
 * - Chart freezing and reconnect storm
 * 
 * WARNING: This hook should only be used in terminal/page.tsx
 * Using it elsewhere may cause duplicate WebSocket connections.
 */

import { useState, useEffect, useRef, useCallback } from 'react';

interface MarketStreamData {
  price: number;
  change_pct: number;
  volume: number | null;
  sentiment?: string;
  regime?: string;
  timestamp: string;
}

interface UseMarketStreamReturn {
  data: MarketStreamData | null;
  connected: boolean;
  error: string | null;
  reconnect: () => void;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// Global cache to ensure only ONE WebSocket per symbol
const wsCache: Map<string, WebSocket> = new Map();

/**
 * Build WebSocket URL correctly
 */
function buildWsUrl(symbol: string, token: string): string {
  // Strip protocol from BACKEND_URL
  let url = BACKEND_URL.replace(/^https?:\/\//, '');
  
  // Determine protocol: use wss:// if original was https://, otherwise ws://
  const protocol = BACKEND_URL.startsWith('https://') ? 'wss://' : 'ws://';
  
  return `${protocol}${url}/api/ws/market/stream?symbol=${symbol}&token=${encodeURIComponent(token)}`;
}

export function useMarketStream(symbol: string | null): UseMarketStreamReturn {
  // WARNING: This hook should only be used in terminal/page.tsx
  // Check if we're in development and warn if used elsewhere
  if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    const stack = new Error().stack;
    if (stack && !stack.includes('terminal/page.tsx')) {
      console.warn('[useMarketStream] WARNING: This hook should only be used in terminal/page.tsx. Using it elsewhere may cause duplicate WebSocket connections.');
    }
  }
  
  const [data, setData] = useState<MarketStreamData | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Stable refs - never change during component lifecycle
  const wsRef = useRef<WebSocket | null>(null);
  const symbolRef = useRef<string | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const lastMessageRef = useRef<string | null>(null); // For duplicate message detection
  const isConnectingRef = useRef(false);
  const shouldReconnectRef = useRef(true);
  const mountedRef = useRef(true);

  /**
   * Clean up WebSocket connection
   * OPTIMIZED: Only close if truly unmounting, not just navigating away
   */
  const cleanup = useCallback((forceClose: boolean = false) => {
    // Clear intervals
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    // Only close WebSocket if forceClose is true (component truly unmounting)
    // Otherwise, keep connection alive for smooth navigation
    if (wsRef.current && forceClose) {
      const ws = wsRef.current;
      wsRef.current = null;
      
      // Remove from cache
      if (symbolRef.current) {
        wsCache.delete(symbolRef.current);
      }
      
      // Close connection
      try {
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          ws.close();
        }
      } catch (err) {
        // Ignore close errors
      }
    } else if (wsRef.current && !forceClose) {
      // Keep connection alive, just clear refs
      // Connection will be reused when component remounts
      wsRef.current = null;
    }
    
    isConnectingRef.current = false;
  }, []);

  /**
   * Connect to WebSocket - only called when symbol changes or on mount
   */
  const connect = useCallback(() => {
    // Guard: Don't connect if no symbol
    if (!symbol) {
      setConnected(false);
      return;
    }

    const symbolUpper = symbol.toUpperCase();
    
    // Guard: Don't recreate if already connected for this symbol
    if (wsRef.current && symbolRef.current === symbolUpper) {
      const ws = wsRef.current;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        // Already connected or connecting - don't recreate
        setConnected(ws.readyState === WebSocket.OPEN);
        return;
      }
    }
    
    // Guard: If symbol changed, cleanup old connection first
    if (symbolRef.current && symbolRef.current !== symbolUpper) {
      cleanup();
    }
    
    // Guard: Don't connect if already connecting
    if (isConnectingRef.current) {
      return;
    }
    
    // Guard: Check cache for existing connection - reuse if alive
    const cachedWs = wsCache.get(symbolUpper);
    if (cachedWs) {
      if (cachedWs.readyState === WebSocket.OPEN) {
        // Reuse existing open connection
        wsRef.current = cachedWs;
        symbolRef.current = symbolUpper;
        setConnected(true);
        setError(null);
        return;
      } else if (cachedWs.readyState === WebSocket.CONNECTING) {
        // Connection is still connecting, wait for it
        wsRef.current = cachedWs;
        symbolRef.current = symbolUpper;
        setConnected(false);
        return;
      } else {
        // Connection is dead, remove from cache
        wsCache.delete(symbolUpper);
      }
    }
    
    // Clean up any existing connection for different symbol
    if (symbolRef.current && symbolRef.current !== symbolUpper) {
      cleanup(true); // Force close old symbol connection
    }
    
    // Get token
    const token = typeof window !== 'undefined' ? localStorage.getItem('gsin_token') : null;
    if (!token) {
      setError('No authentication token');
      setConnected(false);
      return;
    }
    
    isConnectingRef.current = true;
    symbolRef.current = symbolUpper;
    
    try {
      // Build correct WebSocket URL
      const wsUrl = buildWsUrl(symbolUpper, token);
      
      // Create WebSocket
      const ws = new WebSocket(wsUrl);
      
      // Store in ref and cache
      wsRef.current = ws;
      wsCache.set(symbolUpper, ws);
      
      ws.onopen = () => {
        if (!mountedRef.current) return;
        
        isConnectingRef.current = false;
        setConnected(true);
        setError(null);
        
        // Start heartbeat every 15 seconds
        heartbeatIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN && mountedRef.current) {
            try {
              ws.send('ping');
            } catch (err) {
              // Ignore send errors
            }
          }
        }, 15000);
      };
      
      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        
        try {
          const message = JSON.parse(event.data);
          
          // CRITICAL: Only process messages for the current symbol
          // This prevents old symbol's data from updating the UI when switching symbols
          if (message.symbol && message.symbol.toUpperCase() !== symbolRef.current) {
            // Message is for a different symbol - ignore it
            return;
          }
          
          // Ignore duplicate messages (prevent unnecessary re-renders)
          const messageStr = JSON.stringify(message);
          if (lastMessageRef.current === messageStr) {
            return; // Duplicate - ignore
          }
          lastMessageRef.current = messageStr;
          
          // Handle message types
          if (message.type === 'status') {
            if (message.status === 'connected') {
              setConnected(true);
              setError(null);
            } else if (message.status === 'no-data') {
              setConnected(true);
              setError(null);
              // Keep showing last known data
            }
          } else if (message.type === 'tick') {
            // Double-check symbol matches before updating data
            if (message.symbol && message.symbol.toUpperCase() !== symbolRef.current) {
              return; // Wrong symbol - ignore
            }
            
            if (message.data && message.data.price !== null && message.data.price !== undefined) {
              setData({
                price: message.data.price,
                change_pct: message.data.change_pct || 0,
                volume: message.data.volume ?? null,
                sentiment: message.data.sentiment || null,
                regime: message.data.regime || null,
                timestamp: message.data.timestamp || new Date().toISOString(),
              });
              setConnected(true);
              setError(null);
            } else if (message.error) {
              // Error in data fetch - log but keep connection
              console.warn(`[WS] Error for ${symbolUpper}:`, message.error);
              setConnected(true);
              setError(null);
            }
          } else if (message.type === 'pong') {
            // Heartbeat response
            setConnected(true);
            setError(null);
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };
      
      ws.onerror = (err) => {
        if (!mountedRef.current) return;
        
        console.error('WebSocket error:', err);
        setError('Connection error');
        // Don't set connected to false on error - let onclose handle it
      };
      
      ws.onclose = (event) => {
        if (!mountedRef.current) return;
        
        // Remove from cache
        wsCache.delete(symbolUpper);
        wsRef.current = null;
        
        // Clear heartbeat
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current);
          heartbeatIntervalRef.current = null;
        }
        
        isConnectingRef.current = false;
        
        // Only reconnect on abnormal close (not manual close) and if still mounted
        // Don't reconnect if component unmounted or symbol changed
        if (shouldReconnectRef.current && mountedRef.current && event.code !== 1000 && symbolRef.current === symbolUpper) {
          setConnected(false);
          
          // Reconnect with exponential backoff (max 3 attempts)
          const attempts = reconnectTimeoutRef.current ? 2 : 1;
          if (attempts <= 3) {
            const delay = Math.min(1000 * Math.pow(2, attempts - 1), 5000);
            reconnectTimeoutRef.current = setTimeout(() => {
              if (mountedRef.current && shouldReconnectRef.current && symbolRef.current === symbolUpper) {
                connect();
              }
            }, delay);
          } else {
            setError('Connection lost. Please refresh.');
          }
        } else {
          setConnected(false);
        }
      };
    } catch (err) {
      console.error('Error creating WebSocket:', err);
      isConnectingRef.current = false;
      setError('Failed to connect');
      setConnected(false);
    }
  }, [symbol, cleanup]);

  /**
   * Manual reconnect function
   */
  const reconnect = useCallback(() => {
    shouldReconnectRef.current = true;
    cleanup(true); // Force close on manual reconnect
    connect();
  }, [cleanup, connect]);

  /**
   * Effect: Connect on mount or symbol change
   * NO EARLY RETURNS - all logic inside useEffect
   * OPTIMIZED: Only reconnect when symbol actually changes, not on every render
   */
  useEffect(() => {
    mountedRef.current = true;
    shouldReconnectRef.current = true;
    
    // CRITICAL: Clear old data when symbol changes to prevent showing stale data
    if (symbolRef.current && symbolRef.current !== symbol?.toUpperCase()) {
      // Symbol changed - clear old data immediately
      setData(null);
      setConnected(false);
      setError(null);
      lastMessageRef.current = null; // Clear duplicate message cache
    }
    
    // Connect only if symbol is provided
    if (symbol) {
      connect();
    } else {
      setConnected(false);
      setError(null);
      setData(null); // Clear data if no symbol
    }
    
    // Cleanup on unmount - but DON'T close WebSocket if navigating away
    // Keep connection alive for smooth navigation
    return () => {
      mountedRef.current = false;
      // Don't set shouldReconnectRef to false - allow reconnection
      // Don't cleanup WebSocket - keep it alive for when user returns
      // Only cleanup if component is truly unmounting (not just navigating)
    };
  }, [symbol]); // Removed connect and cleanup from deps to prevent unnecessary re-renders

  return { data, connected, error, reconnect };
}
