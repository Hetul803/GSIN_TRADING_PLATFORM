'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp, TrendingDown, Activity, AlertCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

interface PriceData {
  symbol: string;
  price?: number;  // Legacy field
  last_price?: number;  // New field from API
  timestamp: string;
  volume?: number;
  change?: number;
  change_pct?: number;  // New field from API
  change_percent?: number;  // Legacy field
}

interface VolatilityData {
  symbol: string;
  volatility: number;
  timestamp: string;
  period?: string;
}

interface SentimentData {
  symbol: string;
  sentiment_score: number;
  timestamp: string;
  confidence?: number;
}

interface MarketDataWidgetProps {
  symbol: string;
  showVolatility?: boolean;
  showSentiment?: boolean;
}

export function MarketDataWidget({ symbol, showVolatility = true, showSentiment = true }: MarketDataWidgetProps) {
  const [priceData, setPriceData] = useState<PriceData | null>(null);
  const [volatilityData, setVolatilityData] = useState<VolatilityData | null>(null);
  const [sentimentData, setSentimentData] = useState<SentimentData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  useEffect(() => {
    if (!symbol) return;

    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        // Fetch price
        const priceResponse = await fetch(`${BACKEND_URL}/api/market/price?symbol=${symbol}`);
        if (priceResponse.ok) {
          const price = await priceResponse.json();
          // Transform to match expected shape
          setPriceData({
            symbol: price.symbol,
            price: price.last_price ?? price.price,  // Use last_price if available
            last_price: price.last_price,
            timestamp: price.timestamp,
            change: price.change,
            change_percent: price.change_pct ?? price.change_percent,
            change_pct: price.change_pct,
          });
        }

        // Fetch volatility
        if (showVolatility) {
          const volResponse = await fetch(`${BACKEND_URL}/api/market/volatility?symbol=${symbol}`);
          if (volResponse.ok) {
            const vol = await volResponse.json();
            setVolatilityData(vol);
          }
        }

        // Fetch sentiment
        if (showSentiment) {
          const sentResponse = await fetch(`${BACKEND_URL}/api/market/sentiment?symbol=${symbol}`);
          if (sentResponse.ok) {
            const sent = await sentResponse.json();
            setSentimentData(sent);
          }
          // 404 is expected if sentiment not available
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load market data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    // Refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [symbol, showVolatility, showSentiment, BACKEND_URL]);

  if (loading && !priceData) {
    return (
      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardContent className="p-4">
          <div className="text-gray-400 text-sm">Loading market data...</div>
        </CardContent>
      </Card>
    );
  }

  if (error && !priceData) {
    return (
      <Card className="bg-black/60 backdrop-blur-xl border-red-500/20">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 text-red-400 text-sm">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!priceData) return null;

  // Get price value (prefer last_price, fallback to price)
  const currentPrice = priceData.last_price ?? priceData.price;
  const changePct = priceData.change_pct ?? priceData.change_percent;
  
  if (!currentPrice || currentPrice === null || currentPrice === undefined) {
    return (
      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardContent className="p-4">
          <div className="text-gray-400 text-sm">Price data unavailable</div>
        </CardContent>
      </Card>
    );
  }

  const isPositive = (changePct ?? 0) >= 0;
  const ChangeIcon = isPositive ? TrendingUp : TrendingDown;

  return (
    <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-gray-400 flex items-center justify-between">
          <span>{priceData.symbol}</span>
          {priceData.volume && (
            <span className="text-xs text-gray-500">Vol: {priceData.volume.toLocaleString()}</span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <div className="text-2xl font-bold text-white">
            ${currentPrice.toFixed(2)}
          </div>
          {priceData.change !== undefined && priceData.change !== null && changePct !== undefined && changePct !== null && (
            <div className={`flex items-center gap-1 text-sm mt-1 ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
              <ChangeIcon className="w-4 h-4" />
              <span>
                {isPositive ? '+' : ''}{priceData.change.toFixed(2)} ({isPositive ? '+' : ''}{changePct.toFixed(2)}%)
              </span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-blue-500/20">
          {showVolatility && volatilityData && (
            <div>
              <div className="text-xs text-gray-400">Volatility</div>
              <div className="text-sm font-semibold text-white">
                {(volatilityData.volatility * 100).toFixed(1)}%
              </div>
            </div>
          )}
          {showSentiment && sentimentData && (
            <div>
              <div className="text-xs text-gray-400">Sentiment</div>
              <div className="flex items-center gap-2">
                <div className="text-sm font-semibold text-white">
                  {sentimentData.sentiment_score > 0 ? '+' : ''}{sentimentData.sentiment_score.toFixed(2)}
                </div>
                <Badge
                  className={
                    sentimentData.sentiment_score > 0.2
                      ? 'bg-green-500/20 text-green-400'
                      : sentimentData.sentiment_score < -0.2
                      ? 'bg-red-500/20 text-red-400'
                      : 'bg-gray-500/20 text-gray-400'
                  }
                >
                  {sentimentData.sentiment_score > 0.2 ? 'Bullish' : sentimentData.sentiment_score < -0.2 ? 'Bearish' : 'Neutral'}
                </Badge>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

