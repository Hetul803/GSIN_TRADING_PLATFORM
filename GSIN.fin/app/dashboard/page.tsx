'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useStore, useTradingMode } from '@/lib/store';
import { TrendingUp, TrendingDown, Activity, Zap, Layers, Users, Upload, DollarSign, AlertTriangle, Shield, Brain } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { MarketDataWidget } from '@/components/market-data-widget';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface TradeSummary {
  total_trades: number;
  open_trades: number;
  closed_trades: number;
  win_rate: number;
  total_realized_pnl: number;
  avg_realized_pnl: number;
}

interface Strategy {
  id: string;
  name: string;
  description: string;
  score: number | null;
  status: string;
  is_proposable: boolean;
}

export default function DashboardPage() {
  const router = useRouter();
  const user = useStore((state) => state.user);
  const { tradingMode, setTradingMode, isBrokerConnected } = useTradingMode();
  const [mounted, setMounted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<TradeSummary | null>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [recommendedStrategies, setRecommendedStrategies] = useState<any[]>([]);
  const [marketRegime, setMarketRegime] = useState<string>('neutral');
  const [regimeConfidence, setRegimeConfidence] = useState<number>(0);
  const [volatility, setVolatility] = useState<number>(0);
  const [volume, setVolume] = useState<number>(0);
  const [sentiment, setSentiment] = useState<string>('neutral');
  const [change24h, setChange24h] = useState<number>(0);
  const [change7d, setChange7d] = useState<number>(0);
  const [weeklyPnl, setWeeklyPnl] = useState(0);
  const [todayPnl, setTodayPnl] = useState(0);

  useEffect(() => {
    setMounted(true);
    // Redirect to login if not authenticated
    if (!user?.id) {
      router.push('/login');
      return;
    }
    loadData();
  }, [user?.id, router]);

  async function loadData() {
    if (!user?.id) return;
    
    setLoading(true);
    try {
      // Fetch trade summary - handle errors independently
      try {
        const summaryRes = await fetch(`${BACKEND_URL}/api/trades/summary?mode=PAPER`, {
          headers: { 'X-User-Id': user.id },
        });
        if (summaryRes.ok) {
          const data = await summaryRes.json();
          setSummary(data);
          setTodayPnl(data?.total_realized_pnl || 0);
          setWeeklyPnl(data?.total_realized_pnl || 0); // Simplified - would calculate weekly separately
        } else {
          console.warn('Failed to load trade summary:', summaryRes.status);
          // Set default values instead of crashing
          setSummary({
            total_trades: 0,
            open_trades: 0,
            closed_trades: 0,
            win_rate: 0,
            total_realized_pnl: 0,
            avg_realized_pnl: 0,
          });
        }
      } catch (error) {
        console.error('Error loading trade summary:', error);
        // Set default values instead of crashing
        setSummary({
          total_trades: 0,
          open_trades: 0,
          closed_trades: 0,
          win_rate: 0,
          total_realized_pnl: 0,
          avg_realized_pnl: 0,
        });
      }

      // Fetch user strategies - handle errors independently
      try {
        const strategiesRes = await fetch(`${BACKEND_URL}/api/strategies`, {
          headers: { 'X-User-Id': user.id },
        });
        if (strategiesRes.ok) {
          const data = await strategiesRes.json();
          setStrategies(data || []);
        } else {
          console.warn('Failed to load strategies:', strategiesRes.status);
          setStrategies([]);
        }
      } catch (error) {
        console.error('Error loading strategies:', error);
        setStrategies([]);
      }

      // Fetch recommended strategies from Brain
      try {
        const recRes = await fetch(`${BACKEND_URL}/api/brain/recommended-strategies?limit=3`, {
          headers: { 'X-User-Id': user.id },
        });
        if (recRes.ok) {
          const recData = await recRes.json();
          setRecommendedStrategies(recData.recommendations || []);
        }
      } catch (error) {
        console.error('Error loading recommended strategies:', error);
      }

      // PHASE 1 & 5: Fetch market context (volume, volatility, sentiment, regime, confidence)
      try {
        const marketContextRes = await fetch(`${BACKEND_URL}/api/market/context?symbol=AAPL`, {
          headers: { 'X-User-Id': user.id },
        });
        if (marketContextRes.ok) {
          const marketData = await marketContextRes.json();
          setVolatility(marketData.annualized_volatility || 0);
          setVolume(marketData.volume || 0);
          setSentiment(marketData.sentiment || 'neutral');
          setMarketRegime(marketData.regime || 'neutral');
          setRegimeConfidence(marketData.regime_confidence || 0);
          setChange24h(marketData.change_24h || 0);
          setChange7d(marketData.change_7d || 0);
        }
      } catch (error) {
        console.error('Error loading market context:', error);
      }
    } catch (error) {
      console.error('Error loading dashboard data:', error);
      // Set safe defaults
      setSummary({
        total_trades: 0,
        open_trades: 0,
        closed_trades: 0,
        win_rate: 0,
        total_realized_pnl: 0,
        avg_realized_pnl: 0,
      });
      setStrategies([]);
    } finally {
      setLoading(false);
    }
  }

  // Prevent hydration mismatch
  if (!mounted) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white text-lg">Loading...</div>
      </div>
    );
  }

  // Redirect if not logged in
  if (!user?.id) {
    return null;
  }

  const handleModeToggle = async (checked: boolean) => {
    const newMode = checked ? 'real' : 'paper';

    // PHASE 6: Check broker connection status from backend
    if (newMode === 'real') {
      try {
        const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        const token = typeof window !== 'undefined' ? localStorage.getItem('gsin_token') : null;
        const response = await fetch(`${BACKEND_URL}/api/broker/status`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });
        
        if (response.ok) {
          const status = await response.json();
          if (!status.connected || !status.verified) {
            toast.error('Real Mode requires a verified broker connection. Go to Settings → Broker to connect and verify one first.');
            return;
          }
        } else {
          toast.error('Real Mode requires a broker connection. Go to Settings → Broker to connect one first.');
          return;
        }
      } catch (error) {
        toast.error('Failed to check broker status. Please try again.');
        return;
      }
    }

    if (newMode === 'real') {
      toast.warning('You are now in Real Mode. Trades will be sent to your broker account.', {
        duration: 5000,
      });
    } else {
      toast.success('Switched to Paper Mode. Trades are simulated.');
    }

    setTradingMode(newMode);
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white text-lg">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6" suppressHydrationWarning>
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">
            {user?.name
              ? (user.isNewUser ? `Welcome, ${user.name}` : `Welcome back, ${user.name}`)
              : 'Welcome'}
            {user?.subscriptionTier && (
              <span className="text-lg font-normal text-gray-400 ml-2">
                ({user.subscriptionTier.charAt(0).toUpperCase() + user.subscriptionTier.slice(1)})
              </span>
            )}
          </h1>
          <p className="text-gray-400">Here's your trading overview</p>
        </div>
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3 bg-black/60 backdrop-blur-xl border border-blue-500/20 rounded-lg p-3">
            <span className="text-sm text-gray-400">Paper</span>
            <Switch
              checked={tradingMode === 'real'}
              onCheckedChange={handleModeToggle}
            />
            <span className="text-sm text-white font-medium">Real</span>
          </div>
          <div className="flex items-center gap-2">
            {tradingMode === 'paper' ? (
              <>
                <Shield className="w-4 h-4 text-blue-400" />
                <span className="text-xs text-blue-400">Paper Mode · Simulated trades using real market data</span>
              </>
            ) : (
              <>
                <AlertTriangle className="w-4 h-4 text-red-400" />
                <span className="text-xs text-red-400">Real Mode · Live trades via your broker. High risk</span>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MarketDataWidget symbol="AAPL" showVolatility={true} showSentiment={false} />
        
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Account Equity</CardTitle>
            <DollarSign className="w-4 h-4 text-blue-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-white">
              ${tradingMode === 'paper' 
                ? (user?.paperEquity ?? 0).toLocaleString() 
                : (user?.realEquity ?? 0).toLocaleString()}
            </div>
            <p className="text-xs text-gray-400 mt-1">
              {tradingMode === 'paper' ? 'Paper Trading' : 'Live Trading'}
            </p>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Today's P&L</CardTitle>
            <TrendingUp className="w-4 h-4 text-green-400" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${todayPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {todayPnl >= 0 ? '+' : ''}${todayPnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <p className="text-xs text-gray-400 mt-1">Realized P&L</p>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Total P&L</CardTitle>
            <Activity className="w-4 h-4 text-blue-400" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${(summary?.total_realized_pnl || 0) >= 0 ? 'text-blue-400' : 'text-red-400'}`}>
              {(summary?.total_realized_pnl || 0) >= 0 ? '+' : ''}${(summary?.total_realized_pnl || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <p className="text-xs text-gray-400 mt-1">{summary?.closed_trades || 0} closed trades</p>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Active Strategies</CardTitle>
            <Layers className="w-4 h-4 text-purple-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-white">{strategies.length}</div>
            <p className="text-xs text-gray-400 mt-1">
              {strategies.filter(s => s.is_proposable).length} proposable
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white">Trading Summary</CardTitle>
          </CardHeader>
          <CardContent>
            {summary ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-400">Total Trades</p>
                    <p className="text-2xl font-bold text-white">{summary.total_trades}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-400">Win Rate</p>
                    <p className="text-2xl font-bold text-green-400">
                      {(summary.win_rate * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-400">Open Trades</p>
                    <p className="text-2xl font-bold text-blue-400">{summary.open_trades}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-400">Closed Trades</p>
                    <p className="text-2xl font-bold text-white">{summary.closed_trades}</p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-12">
                <p className="text-gray-400">No trading data yet</p>
                <p className="text-sm text-gray-500 mt-2">Start trading to see your performance</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Zap className="w-5 h-5 text-yellow-400" />
              Quick Actions
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Link href="/terminal">
              <Button className="w-full bg-blue-600 hover:bg-blue-700">
                Trading Terminal
              </Button>
            </Link>
            <Link href="/strategies">
              <Button variant="outline" className="w-full border-blue-500/20 text-white">
                View Strategies
              </Button>
            </Link>
            <Link href="/trading/history">
              <Button variant="outline" className="w-full border-blue-500/20 text-white">
                Trade History
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* Top 3 Recommended Strategies */}
      {recommendedStrategies.length > 0 && (
        <Card className="bg-gradient-to-r from-purple-500/10 to-blue-500/10 border-purple-500/20">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Brain className="w-5 h-5 text-purple-400" />
              Top 3 Recommended Strategies for You
            </CardTitle>
            <p className="text-sm text-gray-400 mt-2">
              Based on current market conditions and your risk profile
            </p>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {recommendedStrategies.map((rec, idx) => (
                <Card key={rec.strategy_id || idx} className="bg-black/60 border-blue-500/20">
                  <CardHeader>
                    <CardTitle className="text-white text-lg">{rec.name}</CardTitle>
                    <p className="text-sm text-gray-400 line-clamp-2">{rec.description || 'No description'}</p>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-400">Confidence</span>
                      <Badge className="bg-purple-500/20 text-purple-400">
                        {(rec.confidence * 100).toFixed(0)}%
                      </Badge>
                    </div>
                    {rec.recent_backtest_metrics && (
                      <div className="space-y-1 text-xs">
                        <div className="flex justify-between">
                          <span className="text-gray-400">Win Rate:</span>
                          <span className="text-white">{(rec.recent_backtest_metrics.winrate * 100).toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-400">Avg RR:</span>
                          <span className="text-white">{rec.recent_backtest_metrics.avg_rr?.toFixed(1) || 'N/A'}</span>
                        </div>
                      </div>
                    )}
                    {rec.why_recommended && (
                      <p className="text-xs text-gray-400 italic">{rec.why_recommended}</p>
                    )}
                    {rec.estimated_profit_range && (
                      <div className="p-2 bg-yellow-500/10 border border-yellow-500/20 rounded text-xs">
                        <div className="text-yellow-400 font-semibold mb-1">Estimated Profit Range</div>
                        <div className="text-gray-300">
                          {rec.estimated_profit_range.min_pct >= 0 ? '+' : ''}
                          {(rec.estimated_profit_range.min_pct * 100).toFixed(1)}% to {' '}
                          {rec.estimated_profit_range.max_pct >= 0 ? '+' : ''}
                          {(rec.estimated_profit_range.max_pct * 100).toFixed(1)}%
                        </div>
                        <div className="text-yellow-400/70 mt-1 text-[10px]">
                          {rec.estimated_profit_range.disclaimer || 'Based on historical backtests. Not guaranteed.'}
                        </div>
                      </div>
                    )}
                    <Link href={rec.strategy_id ? `/strategies/${rec.strategy_id}` : '/strategies'}>
                      <Button variant="outline" className="w-full bg-white/5 border-blue-500/20 text-white text-xs">
                        View Strategy
                      </Button>
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-white">Your Strategies</h2>
          <Link href="/strategies">
            <Button variant="outline" className="bg-white/5 border-blue-500/20 text-white">
              View All
            </Button>
          </Link>
        </div>

        {strategies.length === 0 ? (
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardContent className="p-12 text-center">
              <Layers className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-400 text-lg mb-2">No strategies yet</p>
              <p className="text-gray-500 text-sm mb-4">Create or upload a strategy to get started</p>
              <Link href="/strategies/upload">
                <Button className="bg-gradient-to-r from-blue-500 to-purple-600">
                  Upload Strategy
                </Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {strategies.slice(0, 6).map((strategy) => (
              <Link key={strategy.id} href={`/strategies/${strategy.id}`}>
                <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20 hover:border-blue-500/40 transition-all cursor-pointer">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <CardTitle className="text-white text-lg">{strategy.name}</CardTitle>
                      <Badge className={
                        strategy.status === 'proposable' 
                          ? 'bg-green-500/20 text-green-400' 
                          : strategy.status === 'candidate'
                          ? 'bg-blue-500/20 text-blue-400'
                          : 'bg-gray-500/20 text-gray-400'
                      }>
                        {strategy.status}
                      </Badge>
                    </div>
                    <p className="text-sm text-gray-400 line-clamp-2">{strategy.description || 'No description'}</p>
                    {/* PHASE 1: Show human explanation if available */}
                    {(strategy as any).explanation_human && (
                      <p className="text-xs text-gray-500 mt-2 line-clamp-2">
                        {(strategy as any).explanation_human}
                      </p>
                    )}
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="p-2 bg-blue-500/10 border border-blue-500/20 rounded">
                      <div className="text-xs text-gray-400">Score</div>
                      <div className="text-sm font-bold text-blue-400">
                        {strategy.score ? (strategy.score * 100).toFixed(1) : 'N/A'}%
                      </div>
                    </div>
                    {/* PHASE 1: Show risk note if available */}
                    {(strategy as any).risk_note && (
                      <div className="p-2 bg-yellow-500/10 border border-yellow-500/20 rounded">
                        <div className="text-xs text-yellow-400 font-semibold mb-1">⚠️ Risk Note</div>
                        <div className="text-xs text-yellow-300/80">
                          {(strategy as any).risk_note}
                        </div>
                      </div>
                    )}
                    <Button variant="outline" className="w-full bg-white/5 border-blue-500/20 text-white">
                      View Details
                    </Button>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>

      {user?.subscriptionTier === 'creator' && (
        <Card className="bg-gradient-to-r from-blue-500/10 to-purple-500/10 border-blue-500/20">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-semibold text-white mb-2">Creator Dashboard</h3>
                <p className="text-gray-400 mb-4">
                  Manage your strategies and track performance
                </p>
                <div className="flex items-center gap-6">
                  <div>
                    <div className="text-sm text-gray-400">Your Strategies</div>
                    <div className="text-2xl font-bold text-white">{strategies.length}</div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-400">Proposable</div>
                    <div className="text-2xl font-bold text-green-400">
                      {strategies.filter(s => s.is_proposable).length}
                    </div>
                  </div>
                </div>
              </div>
              <Link href="/strategies/upload">
                <Button className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 gap-2">
                  <Upload className="w-4 h-4" />
                  Upload Strategy
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Link href="/trading/manual">
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20 hover:border-blue-500/40 transition-all cursor-pointer">
            <CardContent className="p-6">
              <Activity className="w-10 h-10 text-blue-400 mb-3" />
              <h3 className="text-lg font-semibold text-white mb-2">Manual Trade</h3>
              <p className="text-sm text-gray-400">Execute trades manually with full control</p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/strategies">
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20 hover:border-blue-500/40 transition-all cursor-pointer">
            <CardContent className="p-6">
              <Layers className="w-10 h-10 text-purple-400 mb-3" />
              <h3 className="text-lg font-semibold text-white mb-2">View Marketplace</h3>
              <p className="text-sm text-gray-400">Browse and deploy trading strategies</p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/groups">
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20 hover:border-blue-500/40 transition-all cursor-pointer">
            <CardContent className="p-6">
              <Users className="w-10 h-10 text-green-400 mb-3" />
              <h3 className="text-lg font-semibold text-white mb-2">Join Groups</h3>
              <p className="text-sm text-gray-400">Collaborate with other traders</p>
            </CardContent>
          </Card>
        </Link>
      </div>

      <Card className={`border ${tradingMode === 'paper' ? 'bg-blue-500/5 border-blue-500/20' : 'bg-red-500/5 border-red-500/20'}`}>
        <CardContent className="p-4">
          <p className="text-sm text-gray-300">
            {tradingMode === 'paper' ? (
              <>
                <Shield className="w-4 h-4 inline mr-2 text-blue-400" />
                This is simulated trading using real market data. No real money is at risk.
              </>
            ) : (
              <>
                <AlertTriangle className="w-4 h-4 inline mr-2 text-red-400" />
                These trades affect your real broker account. Trading involves high risk. We recommend learning in Paper Mode first.
              </>
            )}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
