'use client';

import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import { 
  TrendingUp, TrendingDown, Activity, Brain, Zap, Shield, AlertTriangle,
  Play, Pause, RefreshCw, BarChart3, Search, Check, ChevronsUpDown, StopCircle
} from 'lucide-react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ComposedChart, Bar
} from 'recharts';
import { toast } from 'sonner';
import { useStore, useTradingMode } from '@/lib/store';
import { cn } from '@/lib/utils';
import { useMarketStream } from '@/hooks/useMarketStream';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface PriceData {
  symbol: string;
  price: number;
  last_price: number;
  change_pct?: number;
  change_percent?: number;
  change?: number;
  volume?: number;
  timestamp: string;
}

interface CandleData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface AssetOverview {
  symbol: string;
  last_price: number;
  change_pct?: number;
  volume?: number;
  volatility?: number;
  sentiment_score?: number;
  sentiment_label?: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
}

interface BrainSignal {
  strategy_id: string;
  symbol: string;
  side: string;
  entry: number;
  exit?: number;
  stop_loss?: number;
  take_profit?: number;
  confidence: number;
  position_size?: number;
  volatility?: number;
  sentiment?: string;
  reasoning?: string;
  explanation?: string;
  market_regime?: string;
  volatility_context?: number;
  sentiment_context?: number;
  mode_recommendation?: string;
}

export default function TradingTerminalPage() {
  const user = useStore((state) => state.user);
  const { tradingMode } = useTradingMode();
  
  const [mounted, setMounted] = useState(false);
  const [symbol, setSymbol] = useState('AAPL');
  const [overview, setOverview] = useState<AssetOverview | null>(null);
  const [candles, setCandles] = useState<CandleData[]>([]);
  const [price, setPrice] = useState<PriceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [pricePolling, setPricePolling] = useState(true);
  const [interval, setInterval] = useState('1d');
  const [todayHigh, setTodayHigh] = useState<number | null>(null);
  const [todayLow, setTodayLow] = useState<number | null>(null);
  
  // WebSocket real-time market data (Phase 5)
  const { data: streamData, connected: wsConnected, error: wsError, reconnect: wsReconnect } = useMarketStream(symbol);
  
  // AI Mode state
  const [aiModeActive, setAiModeActive] = useState(false);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string>('');
  const [strategies, setStrategies] = useState<any[]>([]);
  const [brainSignal, setBrainSignal] = useState<BrainSignal | null>(null);
  const [loadingSignal, setLoadingSignal] = useState(false);
  const [executingTrade, setExecutingTrade] = useState(false);
  const [symbolOpen, setSymbolOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [symbolSearch, setSymbolSearch] = useState('');
  
  // Manual trade state
  const [manualQuantity, setManualQuantity] = useState('');
  const [manualSide, setManualSide] = useState<'BUY' | 'SELL'>('BUY');
  const [manualOrderType, setManualOrderType] = useState<'market' | 'limit'>('market');
  const [manualLimitPrice, setManualLimitPrice] = useState('');
  const [placingOrder, setPlacingOrder] = useState(false);
  const [emergencyStopActive, setEmergencyStopActive] = useState(false);

  const priceIntervalRef = useRef<number | null>(null);

  // Popular stock symbols list
  const popularSymbols = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM', 'V', 'JNJ',
    'WMT', 'PG', 'MA', 'UNH', 'HD', 'DIS', 'BAC', 'PYPL', 'ADBE', 'NFLX',
    'CRM', 'INTC', 'CMCSA', 'PFE', 'T', 'XOM', 'ABBV', 'CSCO', 'AVGO', 'COST',
    'CVX', 'MRK', 'PEP', 'TMO', 'ABT', 'ACN', 'DHR', 'VZ', 'ADP', 'LIN',
    'NKE', 'BMY', 'PM', 'TXN', 'RTX', 'HON', 'UPS', 'QCOM', 'AMGN', 'SPY',
    'QQQ', 'IWM', 'DIA', 'BTC-USD', 'ETH-USD', 'SOL-USD'
  ];

  // Fix hydration error
  useEffect(() => {
    setMounted(true);
  }, []);

  // Load strategies for AI Mode
  useEffect(() => {
    if (user?.id && mounted) {
      loadStrategies();
    }
  }, [user?.id, mounted]);

  // Clear state when symbol changes to prevent showing old data
  useEffect(() => {
    if (symbol && mounted) {
      // Clear old data immediately when symbol changes
      setPrice(null);
      setOverview(null);
      setCandles([]);
      setTodayHigh(null);
      setTodayLow(null);
      setLoading(true);
      // Then load new data
      loadData();
    }
  }, [symbol, interval, mounted]);

  // Track current symbol to prevent stale WebSocket data from updating state
  const currentSymbolRef = useRef(symbol);
  useEffect(() => {
    currentSymbolRef.current = symbol;
  }, [symbol]);

  // Update price from WebSocket stream (Phase 5)
  // OPTIMIZED: Only update when streamData actually changes and matches current symbol
  useEffect(() => {
    // Only update if streamData exists, has price, and matches current symbol
    // This prevents old symbol's data from updating the UI
    if (streamData && streamData.price && currentSymbolRef.current === symbol) {
      setPrice(prev => {
        // Only update if price actually changed to prevent unnecessary re-renders
        if (prev && prev.price === streamData.price && prev.symbol === symbol) {
          return prev;
        }
        return {
          symbol: symbol,
          price: streamData.price,
          last_price: streamData.price,
          change_pct: streamData.change_pct,
          volume: streamData.volume,
          timestamp: streamData.timestamp,
        };
      });
      
      // Update overview with stream data (only if it exists and symbol matches)
      if (overview && currentSymbolRef.current === symbol) {
        setOverview(prev => {
          if (!prev || prev.symbol !== symbol) return prev;
          // Only update if values actually changed
          if (prev.last_price === streamData.price && 
              prev.change_pct === streamData.change_pct &&
              prev.volume === streamData.volume) {
            return prev;
          }
          return {
            ...prev,
            last_price: streamData.price,
            change_pct: streamData.change_pct,
            volume: streamData.volume,
            sentiment_score: streamData.sentiment_score,
          };
        });
      }
    }
  }, [streamData?.price, streamData?.change_pct, streamData?.volume, symbol, overview?.symbol]); // Only depend on actual data values

  // Price polling - fallback if WebSocket not connected (reduced to prevent rate limits)
  useEffect(() => {
    if (pricePolling && symbol && !wsConnected) {
      priceIntervalRef.current = window.setInterval(() => {
        fetchPrice();
      }, 8000) as unknown as number; // Poll every 8 seconds (safe for rate limits with caching)
    } else {
      if (priceIntervalRef.current) {
        window.clearInterval(priceIntervalRef.current);
      }
    }
    
    return () => {
      if (priceIntervalRef.current) {
        window.clearInterval(priceIntervalRef.current);
      }
    };
  }, [pricePolling, symbol, wsConnected]);

  async function loadStrategies() {
    try {
      const response = await fetch(`${BACKEND_URL}/api/strategies`, {
        headers: {
          'X-User-Id': user?.id || '',
        },
      });
      if (response.ok) {
        const data = await response.json();
        setStrategies(data);
        if (data.length > 0 && !selectedStrategyId) {
          setSelectedStrategyId(data[0].id);
        }
      }
    } catch (error) {
      console.error('Failed to load strategies:', error);
    }
  }

  async function loadData() {
    setLoading(true);
    try {
      await Promise.all([
        fetchOverview(),
        fetchCandles(),
        fetchPrice(),
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function fetchOverview() {
    try {
      setError(null);
      const currentSymbol = symbol; // Capture current symbol
      const response = await fetch(`${BACKEND_URL}/api/asset/overview?symbol=${currentSymbol}`);
      if (response.ok) {
        const data = await response.json();
        // Only update if symbol hasn't changed (prevent race conditions)
        if (currentSymbol === symbol) {
          // Transform response to match expected shape with null checks
          setOverview({
            symbol: data.symbol || currentSymbol,
            last_price: data.last_price ?? null,
            change_pct: data.change_pct ?? null,
            volume: data.volume ?? null,
            volatility: data.volatility ?? null,
            sentiment_score: data.sentiment?.score ?? null,
            sentiment_label: data.sentiment?.label ?? null,
            open: data.ohlc?.open ?? null,
            high: data.ohlc?.high ?? null,
            low: data.ohlc?.low ?? null,
            close: data.ohlc?.close ?? null,
          });
        }
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch overview' }));
        // Handle rate limiting specifically
        if (response.status === 429 || errorData.detail?.includes('429') || errorData.detail?.includes('rate limit')) {
          setError('Rate limit exceeded. Please wait a moment before trying again.');
        } else {
          setError(errorData.detail || 'Failed to fetch asset overview');
        }
        console.error('Failed to fetch overview:', errorData);
      }
    } catch (error: any) {
      const errorMsg = error.message || 'Failed to fetch overview';
      if (errorMsg.includes('429') || errorMsg.includes('rate limit')) {
        setError('Rate limit exceeded. Please wait a moment before trying again.');
      } else {
        setError(errorMsg);
      }
      console.error('Failed to fetch overview:', error);
    }
  }

  async function fetchCandles() {
    try {
      setError(null);
      const currentSymbol = symbol; // Capture current symbol
      // Calculate appropriate limit based on timeframe to get today's data
      // For intraday: get enough candles to cover today (e.g., 1m = 390 for full trading day, 5m = 78, 15m = 26, 1h = 6.5)
      // For daily: get last 30 days to show recent trend
      let limit = 100;
      const today = new Date();
      const isWeekend = today.getDay() === 0 || today.getDay() === 6;
      
      if (interval === '1m') {
        limit = 390; // Full trading day (6.5 hours * 60 minutes)
      } else if (interval === '5m') {
        limit = 78; // Full trading day
      } else if (interval === '15m') {
        limit = 26; // Full trading day
      } else if (interval === '1h') {
        limit = 7; // Full trading day + buffer
      } else if (interval === '1d') {
        limit = 30; // Last 30 days
      }
      
      const response = await fetch(`${BACKEND_URL}/api/market/candle?symbol=${currentSymbol}&interval=${interval}&limit=${limit}`);
      if (response.ok) {
        const data = await response.json();
        // Only update if symbol hasn't changed (prevent race conditions)
        if (currentSymbol === symbol) {
          // Response can be array or object with candles property
          let candleArray = Array.isArray(data) ? data : (data.candles || []);
          
          // Filter out very old data (older than 1 year) to prevent showing 2020/2023 data
          const oneYearAgo = new Date();
          oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
          candleArray = candleArray.filter((c: CandleData) => {
            const candleDate = new Date(c.timestamp);
            return candleDate >= oneYearAgo;
          });
          
          // Sort by timestamp to ensure chronological order
          candleArray.sort((a: CandleData, b: CandleData) => 
            new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
          );
          
          setCandles(candleArray);
        
          // Calculate today's high/low from candles
          if (candleArray.length > 0 && currentSymbol === symbol) {
            const todayStr = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
            const todayCandles = candleArray.filter((c: CandleData) => {
              const candleDate = new Date(c.timestamp).toISOString().split('T')[0];
              return candleDate === todayStr;
            });
            
            if (todayCandles.length > 0) {
              const highs = todayCandles.map((c: CandleData) => c.high);
              const lows = todayCandles.map((c: CandleData) => c.low);
              setTodayHigh(Math.max(...highs));
              setTodayLow(Math.min(...lows));
            } else {
              // If no today's candles (market closed or no data yet), use most recent candle
              const latest = candleArray[candleArray.length - 1];
              if (latest) {
                setTodayHigh(latest.high);
                setTodayLow(latest.low);
              }
            }
          }
        }
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch candles' }));
        console.error('Failed to fetch candles:', errorData);
      }
    } catch (error: any) {
      console.error('Failed to fetch candles:', error);
    }
  }

  async function fetchPrice() {
    try {
      const currentSymbol = symbol; // Capture current symbol
      const response = await fetch(`${BACKEND_URL}/api/market/price?symbol=${currentSymbol}`);
      if (response.ok) {
        const data = await response.json();
        // Only update if symbol hasn't changed (prevent race conditions)
        if (currentSymbol === symbol) {
          setPrice({
            ...data,
            symbol: currentSymbol, // Ensure symbol is set
          });
          // Update overview price if available and symbol matches
          if (overview && overview.symbol === currentSymbol && data.last_price !== undefined && data.last_price !== null) {
            setOverview({ 
              ...overview, 
              last_price: data.last_price, 
              change_pct: data.change_pct ?? overview.change_pct 
            });
          }
        }
      } else if (response.status === 429) {
        // Don't show error for rate limits on price polling, just skip this update
        console.warn('Rate limit on price fetch, skipping update');
      }
    } catch (error: any) {
      // Don't show error for rate limits on price polling
      if (!error.message?.includes('429')) {
        console.error('Failed to fetch price:', error);
      }
    }
  }

  async function generateBrainSignal() {
    if (!selectedStrategyId) {
      toast.error('Please select a strategy');
      return;
    }
    
    if (!symbol) {
      toast.error('Please select a symbol');
      return;
    }
    
    setLoadingSignal(true);
    try {
      const response = await fetch(
        `${BACKEND_URL}/api/brain/signal/${selectedStrategyId}?symbol=${symbol}`,
        {
          headers: {
            'X-User-Id': user?.id || '',
          },
        }
      );
      
      if (response.ok) {
        const signal = await response.json();
        setBrainSignal(signal);
        toast.success('Brain signal generated');
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to generate signal' }));
        toast.error(errorData.detail || 'Failed to generate signal');
        console.error('Brain signal error:', errorData);
      }
    } catch (error: any) {
      const errorMsg = error.message || 'Failed to generate signal';
      toast.error(errorMsg);
      console.error('Brain signal exception:', error);
    } finally {
      setLoadingSignal(false);
    }
  }

  async function executeAITrade(mode: 'PAPER' | 'REAL') {
    if (!brainSignal) {
      toast.error('No signal available. Generate a signal first.');
      return;
    }

    if (emergencyStopActive) {
      toast.error('Emergency stop is active. Please disable it first.');
      return;
    }

    if (mode === 'REAL' && tradingMode !== 'real') {
      toast.error('Please switch to Real Mode first');
      return;
    }

    setExecutingTrade(true);
    try {
      // Use position_size from signal, or fallback to confidence-based heuristic
      const quantity = brainSignal.position_size || (brainSignal.confidence > 0.7 ? 10 : 5);
      
      const response = await fetch(`${BACKEND_URL}/api/broker/place-order`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': user?.id || '',
        },
        body: JSON.stringify({
          symbol: brainSignal.symbol,
          side: brainSignal.side,
          quantity: quantity,
          mode: mode,
          source: 'BRAIN',
          strategy_id: brainSignal.strategy_id,
          stop_loss: brainSignal.stop_loss,
          take_profit: brainSignal.take_profit,
        }),
      });

      if (response.ok) {
        toast.success(`${mode} trade executed successfully!`);
        setBrainSignal(null); // Clear signal after execution
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to execute trade');
      }
    } catch (error: any) {
      toast.error('Failed to execute trade: ' + error.message);
    } finally {
      setExecutingTrade(false);
    }
  }

  // Format candles for chart - show proper timestamps based on interval
  // Only show recent data (last 30 days for daily, last 7 days for hourly, today for intraday)
  const now = new Date();
  const filteredCandles = candles.filter(c => {
    const candleDate = new Date(c.timestamp);
    const daysDiff = (now.getTime() - candleDate.getTime()) / (1000 * 60 * 60 * 24);
    
    if (interval === '1d') {
      return daysDiff <= 30; // Last 30 days
    } else if (interval === '1h') {
      return daysDiff <= 7; // Last 7 days
    } else {
      // For intraday (1m, 5m, 15m), only show today's data
      const todayStr = now.toISOString().split('T')[0];
      const candleDateStr = candleDate.toISOString().split('T')[0];
      return candleDateStr === todayStr || daysDiff <= 1; // Today or yesterday (in case of timezone issues)
    }
  });
  
  const chartData = filteredCandles.map(c => {
    const date = new Date(c.timestamp);
    let timeLabel: string;
    
    // Format timestamp based on interval
    if (interval === '1m' || interval === '5m' || interval === '15m') {
      // For intraday: show time (HH:MM)
      timeLabel = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    } else if (interval === '1h') {
      // For hourly: show date and time
      timeLabel = date.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
    } else {
      // For daily: show date
      timeLabel = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined });
    }
    
    return {
      time: timeLabel,
      timestamp: c.timestamp, // Keep original for sorting
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
      volume: c.volume,
    };
  }).sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()); // Sort by timestamp

  const changePct = overview?.change_pct ?? price?.change_pct ?? price?.change_percent ?? 0;
  const isPositive = (changePct ?? 0) >= 0;

  async function placeManualOrder() {
    if (!symbol || !manualQuantity) {
      toast.error('Please enter symbol and quantity');
      return;
    }

    if (emergencyStopActive) {
      toast.error('Emergency stop is active. Please disable it first.');
      return;
    }

    setPlacingOrder(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/broker/place-order`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': user?.id || '',
        },
        body: JSON.stringify({
          symbol: symbol,
          side: manualSide,
          quantity: parseFloat(manualQuantity),
          mode: tradingMode === 'paper' ? 'PAPER' : 'REAL',
          source: 'MANUAL',
          order_type: manualOrderType,
          limit_price: manualOrderType === 'limit' ? parseFloat(manualLimitPrice) : undefined,
        }),
      });

      if (response.ok) {
        toast.success(`${manualSide} order for ${manualQuantity} ${symbol} placed successfully`);
        setManualQuantity('');
        setManualLimitPrice('');
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to place order');
      }
    } catch (error: any) {
      toast.error('Failed to place order: ' + error.message);
    } finally {
      setPlacingOrder(false);
    }
  }

  async function handleEmergencyStop() {
    if (!emergencyStopActive) {
      // Activate emergency stop
      setEmergencyStopActive(true);
      toast.warning('Emergency stop activated. All trading is disabled.', { duration: 5000 });
    } else {
      // Deactivate emergency stop
      setEmergencyStopActive(false);
      toast.success('Emergency stop deactivated. Trading is now enabled.');
    }
  }

  // Prevent hydration error
  if (!mounted) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-center h-screen">
          <RefreshCw className="w-6 h-6 animate-spin text-blue-400" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">Trading Terminal</h1>
          <p className="text-gray-400">Real-time charts and AI-powered trading</p>
        </div>
      </div>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Badge
            className={
              tradingMode === 'paper'
                ? 'bg-blue-500/20 text-blue-400 border-blue-500/30 px-4 py-2'
                : 'bg-red-500/20 text-red-400 border-red-500/30 px-4 py-2'
            }
          >
            {tradingMode === 'paper' ? (
              <>
                <Shield className="w-4 h-4 mr-2" />
                Paper Mode
              </>
            ) : (
              <>
                <AlertTriangle className="w-4 h-4 mr-2" />
                Real Mode
              </>
            )}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPricePolling(!pricePolling)}
            className="border-blue-500/30 text-blue-400"
          >
            {pricePolling ? (
              <>
                <Pause className="w-4 h-4 mr-2" />
                Pause
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Resume
              </>
            )}
          </Button>
          <Button
            variant={emergencyStopActive ? "destructive" : "outline"}
            size="sm"
            onClick={handleEmergencyStop}
            className={emergencyStopActive 
              ? "bg-red-600 hover:bg-red-700 text-white" 
              : "border-red-500/30 text-red-400 hover:bg-red-500/10"
            }
          >
            <StopCircle className="w-4 h-4 mr-2" />
            {emergencyStopActive ? 'Emergency Stop Active' : 'Emergency Stop'}
          </Button>
        </div>
      </div>

      {/* Symbol Selector & Market Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white text-sm">Symbol & Interval</CardTitle>
          </CardHeader>
          <CardContent>
            <Popover open={symbolOpen} onOpenChange={setSymbolOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  role="combobox"
                  aria-expanded={symbolOpen}
                  className="w-full justify-between bg-white/5 border-blue-500/20 text-white hover:bg-white/10"
                >
                  {symbol || 'Select symbol...'}
                  <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[300px] p-0 bg-black/95 border-blue-500/20" align="start">
                <Command className="bg-black/95">
                  <CommandInput 
                    placeholder="Search symbols..." 
                    className="text-white border-blue-500/20"
                    value={symbolSearch}
                    onValueChange={setSymbolSearch}
                  />
                  <CommandList>
                    <CommandEmpty>No symbol found.</CommandEmpty>
                    <CommandGroup>
                      {popularSymbols
                        .filter((s) => 
                          symbolSearch ? s.toLowerCase().includes(symbolSearch.toLowerCase()) : true
                        )
                        .map((sym) => (
                          <CommandItem
                            key={sym}
                            value={sym}
                            onSelect={() => {
                              setSymbol(sym);
                              setSymbolOpen(false);
                              setSymbolSearch('');
                            }}
                            className="text-white hover:bg-blue-500/20 cursor-pointer"
                          >
                            <Check
                              className={cn(
                                "mr-2 h-4 w-4",
                                symbol === sym ? "opacity-100" : "opacity-0"
                              )}
                            />
                            {sym}
                          </CommandItem>
                        ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
            {error && (
              <p className="text-red-400 text-xs mt-2">{error}</p>
            )}
            <div className="mt-4 space-y-2">
              <Label className="text-gray-400 text-xs">Interval</Label>
              <Select value={interval} onValueChange={setInterval}>
                <SelectTrigger className="bg-white/5 border-blue-500/20 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1m">1m</SelectItem>
                  <SelectItem value="5m">5m</SelectItem>
                  <SelectItem value="15m">15m</SelectItem>
                  <SelectItem value="1h">1h</SelectItem>
                  <SelectItem value="1d">1d</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Consolidated Market Information */}
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20 lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-white">{symbol} - Market Overview</CardTitle>
              <div className="flex items-center gap-2">
                {wsConnected ? (
                  <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                    <Activity className="w-3 h-3 mr-1" />
                    Live
                  </Badge>
                ) : wsError ? (
                  <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
                    <AlertTriangle className="w-3 h-3 mr-1" />
                    Offline
                  </Badge>
                ) : (
                  <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                    Connecting...
                  </Badge>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="w-6 h-6 animate-spin text-blue-400" />
                <span className="ml-2 text-gray-400">Loading market data...</span>
              </div>
            ) : error ? (
              <div className="py-4">
                <p className="text-red-400 text-sm mb-2">⚠️ {error}</p>
                <p className="text-gray-500 text-xs">
                  Rate limit exceeded. Please wait a moment and try again, or select a different symbol.
                </p>
              </div>
            ) : overview ? (
              <>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  {/* Price */}
                  <div>
                    <Label className="text-gray-400 text-xs mb-1 block">Price</Label>
                    <div className="text-2xl font-bold text-white">
                      {/* Only show price if it matches current symbol */}
                      {price?.symbol === symbol && price?.price ? price.price.toFixed(2) : 
                       (overview?.symbol === symbol && overview.last_price ? overview.last_price.toFixed(2) : 
                        loading ? 'Loading...' : 'N/A')}
                    </div>
                    {changePct !== null && changePct !== undefined && (
                      <div className={`flex items-center gap-1 mt-1 ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                        {isPositive ? (
                          <TrendingUp className="w-3 h-3" />
                        ) : (
                          <TrendingDown className="w-3 h-3" />
                        )}
                        <span className="text-xs font-semibold">
                          {isPositive ? '+' : ''}{changePct.toFixed(2)}%
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Today's High */}
                  <div>
                    <Label className="text-gray-400 text-xs mb-1 block">Today's High</Label>
                    <div className="text-2xl font-bold text-green-400">
                      ${todayHigh ? todayHigh.toFixed(2) : (overview.high ? overview.high.toFixed(2) : 'N/A')}
                    </div>
                    {overview.open !== null && overview.open !== undefined && (
                      <div className="text-xs text-gray-500 mt-1">
                        Open: ${overview.open.toFixed(2)}
                      </div>
                    )}
                  </div>

                  {/* Today's Low */}
                  <div>
                    <Label className="text-gray-400 text-xs mb-1 block">Today's Low</Label>
                    <div className="text-2xl font-bold text-red-400">
                      ${todayLow ? todayLow.toFixed(2) : (overview.low ? overview.low.toFixed(2) : 'N/A')}
                    </div>
                    {overview.close !== null && overview.close !== undefined && (
                      <div className="text-xs text-gray-500 mt-1">
                        Close: ${overview.close.toFixed(2)}
                      </div>
                    )}
                  </div>

                  {/* Volume */}
                  <div>
                    <Label className="text-gray-400 text-xs mb-1 block">Volume</Label>
                    <div className="text-2xl font-bold text-white">
                      {/* Only show volume if overview matches current symbol */}
                      {overview?.symbol === symbol && overview.volume ? (overview.volume / 1000000).toFixed(2) + 'M' : 
                       loading ? 'Loading...' : 'N/A'}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {/* Only show stream volume if we have stream data and it's for current symbol */}
                      {streamData && currentSymbolRef.current === symbol && streamData.volume ? 
                        `Live: ${(streamData.volume / 1000000).toFixed(2)}M` : 
                        wsConnected ? 'Real-time' : 'Connecting...'}
                    </div>
                  </div>

                  {/* Volatility */}
                  <div>
                    <Label className="text-gray-400 text-xs mb-1 block">Volatility</Label>
                    {overview.volatility !== undefined && overview.volatility !== null ? (
                      <>
                        <div className="text-2xl font-bold text-purple-400">
                          {(overview.volatility * 100).toFixed(1)}%
                        </div>
                        <Badge className="bg-purple-500/20 text-purple-400 text-xs mt-1">
                          Annualized
                        </Badge>
                      </>
                    ) : (
                      <div className="text-gray-500">N/A</div>
                    )}
                  </div>

                  {/* Sentiment */}
                  <div>
                    <Label className="text-gray-400 text-xs mb-1 block">Sentiment</Label>
                    {overview.sentiment_label || streamData?.sentiment_score !== undefined ? (
                      <>
                        <Badge
                          className={
                            (overview.sentiment_label === 'bullish' || (streamData?.sentiment_score && streamData.sentiment_score > 0.2))
                              ? 'bg-green-500/20 text-green-400 text-lg px-3 py-1'
                              : (overview.sentiment_label === 'bearish' || (streamData?.sentiment_score && streamData.sentiment_score < -0.2))
                              ? 'bg-red-500/20 text-red-400 text-lg px-3 py-1'
                              : 'bg-gray-500/20 text-gray-400 text-lg px-3 py-1'
                          }
                        >
                          {(overview.sentiment_label || (streamData?.sentiment_score && streamData.sentiment_score > 0.2 ? 'BULLISH' : streamData?.sentiment_score && streamData.sentiment_score < -0.2 ? 'BEARISH' : 'NEUTRAL')).toUpperCase()}
                        </Badge>
                        {(overview.sentiment_score !== undefined && overview.sentiment_score !== null) || streamData?.sentiment_score !== undefined ? (
                          <div className="text-xs text-gray-500 mt-1">
                            Score: {((streamData?.sentiment_score ?? overview.sentiment_score ?? 0) * 100).toFixed(0)}%
                          </div>
                        ) : null}
                      </>
                    ) : (
                      <div className="text-gray-500">N/A</div>
                    )}
                  </div>
                </div>
                
                {/* Phase 5: Real-time indicators from WebSocket */}
                {streamData && (streamData.regime || streamData.multi_timeframe_alignment !== undefined) && (
                  <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-blue-500/20">
                    {streamData.regime && (
                      <div>
                        <Label className="text-gray-400 text-xs mb-1 block">Market Regime</Label>
                        <Badge className="bg-purple-500/20 text-purple-400">
                          {streamData.regime.toUpperCase()}
                        </Badge>
                      </div>
                    )}
                    {streamData.multi_timeframe_alignment !== undefined && (
                      <div>
                        <Label className="text-gray-400 text-xs mb-1 block">Trend Alignment</Label>
                        <div className="text-lg font-bold text-blue-400">
                          {(streamData.multi_timeframe_alignment * 100).toFixed(0)}%
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-8 text-gray-400">
                <p>No market data available</p>
                <p className="text-xs mt-1">Select a symbol to load data</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Chart */}
      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardHeader>
          <CardTitle className="text-white">{symbol} - {interval} Chart</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="h-96 flex items-center justify-center text-gray-400">
              <RefreshCw className="w-8 h-8 animate-spin" />
            </div>
          ) : chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time" stroke="#64748b" />
                <YAxis stroke="#64748b" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    border: '1px solid #1e293b',
                    borderRadius: '8px',
                    color: '#fff',
                  }}
                  formatter={(value: any, name: string) => {
                    if (name === 'close') return [`$${value.toFixed(2)}`, 'Close'];
                    if (name === 'open') return [`$${value.toFixed(2)}`, 'Open'];
                    if (name === 'high') return [`$${value.toFixed(2)}`, 'High'];
                    if (name === 'low') return [`$${value.toFixed(2)}`, 'Low'];
                    if (name === 'volume') return [value.toLocaleString(), 'Volume'];
                    return [value, name];
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="close"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  name="Close Price"
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-96 flex items-center justify-center text-gray-400">
              No chart data available
            </div>
          )}
        </CardContent>
      </Card>

      {/* AI Mode Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-black/60 backdrop-blur-xl border-purple-500/20">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-white flex items-center gap-2">
                <Brain className="w-5 h-5 text-purple-400" />
                AI Mode
              </CardTitle>
              <Button
                variant={aiModeActive ? "default" : "outline"}
                size="sm"
                onClick={() => {
                  setAiModeActive(!aiModeActive);
                  if (!aiModeActive && selectedStrategyId) {
                    generateBrainSignal();
                  }
                }}
                className={aiModeActive ? "bg-purple-600 hover:bg-purple-700" : ""}
              >
                {aiModeActive ? 'Active' : 'Activate'}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-gray-300">Strategy</Label>
              <Select
                value={selectedStrategyId}
                onValueChange={setSelectedStrategyId}
                disabled={aiModeActive}
              >
                <SelectTrigger className="mt-2 bg-white/5 border-blue-500/20 text-white">
                  <SelectValue placeholder="Select strategy" />
                </SelectTrigger>
                <SelectContent>
                  {strategies.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {aiModeActive && (
              <Button
                onClick={generateBrainSignal}
                disabled={loadingSignal || !selectedStrategyId}
                className="w-full bg-gradient-to-r from-purple-500 to-pink-600"
              >
                {loadingSignal ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Zap className="w-4 h-4 mr-2" />
                    Generate Signal
                  </>
                )}
              </Button>
            )}

            {brainSignal && (
              <div className="space-y-3 pt-3 border-t border-purple-500/20">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-gray-400 text-xs">Side</Label>
                    <div className={`text-lg font-bold ${brainSignal.side === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                      {brainSignal.side}
                    </div>
                  </div>
                  <div>
                    <Label className="text-gray-400 text-xs">Confidence</Label>
                    <div className="text-lg font-bold text-purple-400">
                      {(brainSignal.confidence * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-gray-400 text-xs">Entry</Label>
                    <div className="text-white font-semibold">
                      ${brainSignal.entry ? brainSignal.entry.toFixed(2) : 'N/A'}
                    </div>
                  </div>
                  {brainSignal.stop_loss && (
                    <div>
                      <Label className="text-gray-400 text-xs">Stop Loss</Label>
                      <div className="text-red-400 font-semibold">
                        ${brainSignal.stop_loss ? brainSignal.stop_loss.toFixed(2) : 'N/A'}
                      </div>
                    </div>
                  )}
                </div>

                {brainSignal.take_profit && (
                  <div>
                    <Label className="text-gray-400 text-xs">Take Profit</Label>
                    <div className="text-green-400 font-semibold">
                      ${brainSignal.take_profit ? brainSignal.take_profit.toFixed(2) : 'N/A'}
                    </div>
                  </div>
                )}

                {brainSignal.position_size && (
                  <div>
                    <Label className="text-gray-400 text-xs">Position Size</Label>
                    <div className="text-white font-semibold">
                      {brainSignal.position_size ? brainSignal.position_size.toFixed(2) : 'N/A'} shares
                    </div>
                  </div>
                )}

                {(brainSignal.volatility !== undefined || brainSignal.sentiment) && (
                  <div className="grid grid-cols-2 gap-3 pt-2 border-t border-purple-500/20">
                    {brainSignal.volatility !== undefined && (
                      <div>
                        <Label className="text-gray-400 text-xs">Volatility</Label>
                        <div className="text-purple-400 font-semibold">{(brainSignal.volatility * 100).toFixed(1)}%</div>
                      </div>
                    )}
                    {brainSignal.sentiment && (
                      <div>
                        <Label className="text-gray-400 text-xs">Sentiment</Label>
                        <Badge
                          className={
                            brainSignal.sentiment === 'bullish'
                              ? 'bg-green-500/20 text-green-400'
                              : brainSignal.sentiment === 'bearish'
                              ? 'bg-red-500/20 text-red-400'
                              : 'bg-gray-500/20 text-gray-400'
                          }
                        >
                          {brainSignal.sentiment.toUpperCase()}
                        </Badge>
                      </div>
                    )}
                  </div>
                )}

                {/* PHASE 6: Enhanced Brain Explanation */}
                {(brainSignal.reasoning || brainSignal.explanation || (brainSignal as any).mcn_adjustments) && (
                  <div className="pt-2 border-t border-purple-500/20 space-y-3">
                    <Label className="text-gray-400 text-xs">AI Analysis</Label>
                    {(brainSignal.reasoning || brainSignal.explanation) && (
                      <p className="text-sm text-gray-300">{brainSignal.reasoning || brainSignal.explanation}</p>
                    )}
                    
                    {/* PHASE 6: Detailed confidence breakdown */}
                    {(brainSignal as any).mcn_adjustments?.confidence_calibration && (
                      <div className="p-3 bg-purple-500/10 border border-purple-500/20 rounded-lg space-y-2">
                        <Label className="text-gray-400 text-xs">Confidence Breakdown</Label>
                        {Object.entries((brainSignal as any).mcn_adjustments.confidence_calibration.contributions || {}).map(([factor, data]: [string, any]) => (
                          <div key={factor} className="flex justify-between items-center text-xs">
                            <span className="text-gray-400 capitalize">{factor.replace(/_/g, ' ')}:</span>
                            <div className="flex items-center gap-2">
                              <div className="w-20 bg-gray-700 rounded-full h-1.5">
                                <div
                                  className="bg-purple-400 h-1.5 rounded-full"
                                  style={{ width: `${(data.contribution || 0) * 100}%` }}
                                />
                              </div>
                              <span className="text-purple-400 font-semibold">
                                {((data.contribution || 0) * 100).toFixed(1)}%
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {/* PHASE 6: MCN similarity matches */}
                    {(brainSignal as any).mcn_adjustments?.similar_patterns && (
                      <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                        <Label className="text-gray-400 text-xs mb-2 block">Similar Historical Patterns</Label>
                        <p className="text-xs text-gray-300">
                          Found {((brainSignal as any).mcn_adjustments.similar_patterns?.length || 0)} similar patterns in MCN memory
                        </p>
                      </div>
                    )}
                  </div>
                )}

                <div className="flex gap-2 pt-2">
                  <Button
                    onClick={() => executeAITrade('PAPER')}
                    disabled={executingTrade}
                    className="flex-1 bg-blue-600 hover:bg-blue-700"
                  >
                    {executingTrade ? (
                      <>
                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        Executing...
                      </>
                    ) : (
                      <>
                        <Shield className="w-4 h-4 mr-2" />
                        Execute (PAPER)
                      </>
                    )}
                  </Button>
                  <Button
                    onClick={() => executeAITrade('REAL')}
                    disabled={executingTrade || tradingMode !== 'real'}
                    className="flex-1 bg-red-600 hover:bg-red-700"
                  >
                    {executingTrade ? (
                      <>
                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        Executing...
                      </>
                    ) : (
                      <>
                        <AlertTriangle className="w-4 h-4 mr-2" />
                        Execute (REAL)
                      </>
                    )}
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Manual Trading Panel */}
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white">Manual Trade</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
              <div>
                <Label className="text-gray-300 text-sm">Side</Label>
                <div className="flex gap-2 mt-2">
                  <Button
                    variant={manualSide === 'BUY' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setManualSide('BUY')}
                    disabled={emergencyStopActive}
                    className={manualSide === 'BUY' 
                      ? 'bg-green-600 hover:bg-green-700' 
                      : 'border-green-500/30 text-green-400 hover:bg-green-500/10'
                    }
                  >
                    BUY
                  </Button>
                  <Button
                    variant={manualSide === 'SELL' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setManualSide('SELL')}
                    disabled={emergencyStopActive}
                    className={manualSide === 'SELL' 
                      ? 'bg-red-600 hover:bg-red-700' 
                      : 'border-red-500/30 text-red-400 hover:bg-red-500/10'
                    }
                  >
                    SELL
                  </Button>
                </div>
              </div>

              <div>
                <Label className="text-gray-300 text-sm">Quantity</Label>
                <Input
                  type="number"
                  value={manualQuantity}
                  onChange={(e) => setManualQuantity(e.target.value)}
                  placeholder="10"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  disabled={emergencyStopActive}
                />
              </div>

              <div>
                <Label className="text-gray-300 text-sm">Order Type</Label>
                <Select 
                  value={manualOrderType} 
                  onValueChange={(v: 'market' | 'limit') => setManualOrderType(v)}
                  disabled={emergencyStopActive}
                >
                  <SelectTrigger className="mt-2 bg-white/5 border-blue-500/20 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="market">Market</SelectItem>
                    <SelectItem value="limit">Limit</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {manualOrderType === 'limit' && (
                <div>
                  <Label className="text-gray-300 text-sm">Limit Price</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={manualLimitPrice}
                    onChange={(e) => setManualLimitPrice(e.target.value)}
                    placeholder={overview?.last_price?.toFixed(2) || "0.00"}
                    className="mt-2 bg-white/5 border-blue-500/20 text-white"
                    disabled={emergencyStopActive}
                  />
                </div>
              )}

              <Button
                onClick={placeManualOrder}
                disabled={placingOrder || emergencyStopActive || !symbol || !manualQuantity}
                className={`w-full ${
                  manualSide === 'BUY' 
                    ? 'bg-green-600 hover:bg-green-700' 
                    : 'bg-red-600 hover:bg-red-700'
                }`}
              >
                {placingOrder ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    Placing Order...
                  </>
                ) : emergencyStopActive ? (
                  'Emergency Stop Active'
                ) : (
                  `Place ${manualSide} Order`
                )}
              </Button>

              {emergencyStopActive && (
                <p className="text-red-400 text-xs text-center">
                  Emergency stop is active. Trading is disabled.
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

