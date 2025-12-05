'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Zap, TrendingUp, TrendingDown, AlertTriangle, CheckCircle } from 'lucide-react';
import { useStore, useTradingMode } from '@/lib/store';
import { toast } from 'sonner';

interface Signal {
  id: string;
  symbol: string;
  side: 'buy' | 'sell';
  confidence: number;
  entry: number;
  stopLoss: number;
  takeProfit: number;
  reasoning: string;
  timestamp: Date;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export default function AISignalsPage() {
  const user = useStore((state) => state.user);
  const router = useRouter();
  const tradingModeHook = useTradingMode();
  const tradingMode = tradingModeHook?.tradingMode || 'paper';

  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [approvedSignals, setApprovedSignals] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!user?.id) {
      router.push('/login');
      return;
    }
    // Signals would come from Brain API - for now show empty state
    setLoading(false);
  }, [user?.id, router]);

  const handleApproveSignal = async (signal: Signal) => {
    if (!user?.id) {
      toast.error('Please log in to execute trades');
      return;
    }

    try {
      const response = await fetch(`${BACKEND_URL}/api/broker/place-order`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': user.id,
        },
        body: JSON.stringify({
          symbol: signal.symbol,
          side: signal.side.toUpperCase(),
          quantity: 1, // Default quantity
          mode: tradingMode.toUpperCase() === 'REAL' ? 'REAL' : 'PAPER',
          source: 'BRAIN',
          stop_loss: signal.stopLoss,
          take_profit: signal.takeProfit,
        }),
      });

      if (response.ok) {
        setApprovedSignals(prev => new Set(prev).add(signal.id));
        toast.success(`Trade executed for ${signal.symbol} (${signal.side.toUpperCase()})`);
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to execute trade');
      }
    } catch (error: any) {
      console.error('Error executing trade:', error);
      toast.error(error.message || 'Failed to execute trade');
    }
  };

  const handleDismissSignal = (signalId: string) => {
    setSignals(prev => prev.filter(s => s.id !== signalId));
  };

  if (!user?.id) {
    return null;
  }

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white text-lg">Loading signals...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6" suppressHydrationWarning>
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-bold text-white">AI Trading Signals</h1>
            <Zap className="w-8 h-8 text-yellow-400" />
          </div>
          <p className="text-gray-400">
            GSIN Brain analyzes market data and generates high-confidence trade signals
          </p>
        </div>
        <Badge
          className={
            tradingMode === 'paper'
              ? 'bg-blue-500/20 text-blue-400 border-blue-500/30 px-4 py-2'
              : 'bg-red-500/20 text-red-400 border-red-500/30 px-4 py-2'
          }
        >
          {tradingMode === 'paper' ? 'Paper Mode - Simulated signals' : 'Real Mode - Live signals'}
        </Badge>
      </div>

      {signals.length === 0 ? (
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardContent className="p-12 text-center">
            <Zap className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-white mb-2">No Active Signals</h3>
            <p className="text-gray-400 mb-2">
              Brain is still learning and evolving strategies. Signals will appear here once strategies become proposable.
            </p>
            <p className="text-xs text-gray-500">
              Strategies need to meet strict criteria (90%+ win rate, 50+ trades, score ≥ 0.70) before Brain will generate signals.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {signals.map((signal) => {
            const isApproved = approvedSignals.has(signal.id);

            return (
              <Card
                key={signal.id}
                className="bg-black/60 backdrop-blur-xl border-blue-500/20 hover:border-blue-500/40 transition-all"
              >
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <CardTitle className="text-white text-2xl">{signal.symbol}</CardTitle>
                        <Badge
                          className={
                            signal.side === 'buy'
                              ? 'bg-green-500/20 text-green-400 border-green-500/30'
                              : 'bg-red-500/20 text-red-400 border-red-500/30'
                          }
                        >
                          {signal.side === 'buy' ? (
                            <TrendingUp className="w-3 h-3 mr-1" />
                          ) : (
                            <TrendingDown className="w-3 h-3 mr-1" />
                          )}
                          {signal.side.toUpperCase()}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-400">Confidence:</span>
                        <div className="flex items-center gap-1">
                          <div className="h-2 w-24 bg-gray-700 rounded-full overflow-hidden">
                            <div
                              className={`h-full ${
                                signal.confidence >= 80
                                  ? 'bg-green-500'
                                  : signal.confidence >= 70
                                  ? 'bg-yellow-500'
                                  : 'bg-red-500'
                              }`}
                              style={{ width: `${signal.confidence}%` }}
                            />
                          </div>
                          <span className="text-sm font-semibold text-white">{signal.confidence}%</span>
                        </div>
                      </div>
                    </div>
                    {isApproved && (
                      <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                        <CheckCircle className="w-3 h-3 mr-1" />
                        Approved
                      </Badge>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-3 gap-3">
                    <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                      <div className="text-xs text-gray-400 mb-1">Entry</div>
                      <div className="text-sm font-bold text-white">${signal.entry.toFixed(2)}</div>
                    </div>
                    <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                      <div className="text-xs text-gray-400 mb-1">Stop Loss</div>
                      <div className="text-sm font-bold text-red-400">${signal.stopLoss.toFixed(2)}</div>
                    </div>
                    <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg">
                      <div className="text-xs text-gray-400 mb-1">Take Profit</div>
                      <div className="text-sm font-bold text-green-400">
                        ${signal.takeProfit.toFixed(2)}
                      </div>
                    </div>
                  </div>

                  <div className="p-3 bg-white/5 border border-blue-500/20 rounded-lg">
                    <div className="text-xs text-gray-400 mb-1">AI Analysis</div>
                    <p className="text-sm text-gray-300">{signal.reasoning}</p>
                  </div>

                  <div className="text-xs text-gray-500">
                    Generated by GSIN Brain · {new Date(signal.timestamp).toLocaleString()}
                  </div>

                  {!isApproved ? (
                    <div className="flex gap-2">
                      <Button
                        onClick={() => handleApproveSignal(signal)}
                        className="flex-1 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700"
                      >
                        <CheckCircle className="w-4 h-4 mr-2" />
                        Approve & Execute
                      </Button>
                      <Button
                        onClick={() => handleDismissSignal(signal.id)}
                        variant="outline"
                        className="border-gray-500/30 text-gray-400 hover:bg-gray-500/10"
                      >
                        Dismiss
                      </Button>
                    </div>
                  ) : (
                    <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg">
                      <p className="text-sm text-green-200 text-center">
                        Trade executed successfully
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
