'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ArrowLeft, TrendingUp, TrendingDown, BarChart3, AlertTriangle, CheckCircle, XCircle, Brain, Gauge } from 'lucide-react';
import Link from 'next/link';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { toast } from 'sonner';
import { useStore } from '@/lib/store';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface TearSheetData {
  strategyName: string;
  creatorName: string;
  annualizedReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  totalTrades: number;
  totalReturn: number;
  winRate: number;
  profitFactor: number;
  equityCurve: Array<{ date: string; value: number; benchmark: number }>;
  benchmarkSymbol: string;
  sortinoRatio: number;
  maxDrawdownNormalized: number;
  longestDrawdownDuration: string;
  mcnRobustnessScore: number;
  mcnRegimeStability: {
    bull: string;
    bear: string;
    highVol: string;
    lowVol: string;
  };
  mcnOverfittingRisk: string;
  mcnNoveltyScore: number;
  mcnLineage: string;
  tradesPerMonth: number;
  avgTimeInTrade: string;
  avgWin: number;
  avgLoss: number;
}

export default function StrategyDetailPage({ params }: { params: { strategyId: string } }) {
  const router = useRouter();
  const user = useStore((state) => state.user);
  const [tearSheet, setTearSheet] = useState<TearSheetData | null>(null);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  const [showWhyCard, setShowWhyCard] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (!user?.id) {
      router.push('/login');
      return;
    }
    loadTearSheet();
  }, [params?.strategyId, user?.id, router]);

  async function loadTearSheet() {
    if (!user?.id || !params?.strategyId) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/strategies/${params?.strategyId}/tearsheet`, {
        headers: {
          'X-User-Id': user.id,
        },
      });
      
      if (response.ok) {
        const data = await response.json();
        setTearSheet(data);
      } else {
        const error = await response.json().catch(() => ({ detail: 'Strategy not found' }));
        toast.error(error.detail || 'Strategy not found');
        router.push('/strategies');
      }
    } catch (error: any) {
      console.error('Failed to load tear sheet:', error);
      toast.error('Failed to load strategy details: ' + (error.message || 'Network error'));
      router.push('/strategies');
    } finally {
      setLoading(false);
    }
  }

  if (!mounted || loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white text-lg">Loading strategy details...</div>
      </div>
    );
  }

  if (!tearSheet) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white text-lg">Strategy not found</div>
      </div>
    );
  }

  // Format equity curve for chart
  const chartData = tearSheet.equityCurve.map((point) => ({
    date: new Date(point.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    strategy: point.value,
    benchmark: point.benchmark,
  }));

  // Get Sharpe color
  const getSharpeColor = (sharpe: number) => {
    if (sharpe >= 2) return 'text-green-400';
    if (sharpe >= 1) return 'text-yellow-400';
    return 'text-red-400';
  };

  // Get regime status badge
  const getRegimeBadge = (status: string) => {
    if (status === 'pass') {
      return <Badge className="bg-green-500/20 text-green-400 border-green-500/30"><CheckCircle className="w-3 h-3 mr-1" />Pass</Badge>;
    }
    if (status === 'fail') {
      return <Badge className="bg-red-500/20 text-red-400 border-red-500/30"><XCircle className="w-3 h-3 mr-1" />Fail</Badge>;
    }
    return <Badge className="bg-gray-500/20 text-gray-400 border-gray-500/30">Unknown</Badge>;
  };

  // Calculate simple regime stability summary based on pass/fail flags
  const regimeStatuses = tearSheet
    ? [
        { label: 'Bull', value: tearSheet.mcnRegimeStability.bull },
        { label: 'Bear', value: tearSheet.mcnRegimeStability.bear },
        { label: 'High-Vol', value: tearSheet.mcnRegimeStability.highVol },
        { label: 'Low-Vol', value: tearSheet.mcnRegimeStability.lowVol },
      ]
    : [];

  const passedRegimes = regimeStatuses.filter((r) => r.value === 'pass').length;
  const totalRegimes = regimeStatuses.length || 4;

  return (
    <div className="p-6 space-y-6">
      {/* Navigation */}
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <Link href="/dashboard" className="hover:text-white transition-colors">Dashboard</Link>
        <span>/</span>
        <Link href="/strategies" className="hover:text-white transition-colors">Strategy Marketplace</Link>
        <span>/</span>
        <span className="text-white">{tearSheet.strategyName}</span>
        </div>

      {/* Section 1: At-a-Glance Key Metrics */}
                  <div>
        <div className="mb-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                              <div>
            <h1 className="text-3xl font-bold text-white mb-1">{tearSheet.strategyName}</h1>
            <p className="text-gray-400">Created by {tearSheet.creatorName}</p>
                              </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              className="bg-white/5 border-blue-500/40 text-white text-xs md:text-sm flex items-center gap-2"
              onClick={() => setShowWhyCard((prev) => !prev)}
            >
              <Brain className="w-4 h-4 text-purple-400" />
              {showWhyCard ? 'Hide Why' : 'Why this Strategy?'}
            </Button>
          </div>
        </div>

        {showWhyCard && (
          <Card className="mb-4 bg-black/70 border-blue-500/30">
            <CardHeader>
              <CardTitle className="text-white text-sm md:text-base flex items-center gap-2">
                <Brain className="w-4 h-4 text-purple-400" />
                Why GSIN Brain recommends this strategy
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-xs md:text-sm text-gray-200">
              <p>
                We are recommending <span className="font-semibold text-white">{tearSheet.strategyName}</span> because it has been
                backtested and evaluated by our Brain and MCN memory as a robust performer in market conditions similar to today.
              </p>

              <div className="space-y-1">
                <p className="font-semibold text-gray-300">MCN Regime Stability</p>
                <p className="text-gray-300">
                  Passed {passedRegimes}/{totalRegimes} regimes:&nbsp;
                  {regimeStatuses.map((r, idx) => (
                    <span key={r.label}>
                      {r.value === 'pass' ? '✅' : r.value === 'fail' ? '❌' : '❓'} {r.label}
                      {idx < regimeStatuses.length - 1 ? ' | ' : ''}
                    </span>
                  ))}
                </p>
          </div>
          
              <div className="flex flex-wrap gap-4 mt-2">
                <div>
                  <p className="text-xs text-gray-400">Robustness Score</p>
                  <p className="font-semibold text-purple-300">
                    {tearSheet.mcnRobustnessScore}/100
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">Overfitting Risk</p>
                  <p
                    className={`font-semibold ${
                      tearSheet.mcnOverfittingRisk === 'Low'
                        ? 'text-green-400'
                        : tearSheet.mcnOverfittingRisk === 'High'
                        ? 'text-red-400'
                        : 'text-yellow-300'
                    }`}
                  >
                    {tearSheet.mcnOverfittingRisk}
                  </p>
          </div>
                <div>
                  <p className="text-xs text-gray-400">Historical Avg. Annual Return</p>
                  <p
                    className={`font-semibold ${
                      tearSheet.annualizedReturn >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {tearSheet.annualizedReturn >= 0 ? '+' : ''}
                    {tearSheet.annualizedReturn.toFixed(2)}%
                  </p>
          </div>
                <div>
                  <p className="text-xs text-gray-400">Historical Max Drawdown</p>
                  <p className="font-semibold text-red-400">
                    {tearSheet.maxDrawdown.toFixed(2)}%
                  </p>
        </div>
      </div>

              <p className="text-gray-300 mt-1">
                These numbers come directly from this strategy&apos;s historical backtests and MCN lineage memory for this strategy,
                not from generic templates.
              </p>
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardContent className="p-6">
              <div className="text-sm text-gray-400 mb-1">Annualized Return</div>
              <div className={`text-3xl font-bold ${tearSheet.annualizedReturn >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {tearSheet.annualizedReturn >= 0 ? '+' : ''}{tearSheet.annualizedReturn.toFixed(2)}%
              </div>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardContent className="p-6">
              <div className="text-sm text-gray-400 mb-1">Sharpe Ratio</div>
              <div className={`text-3xl font-bold ${getSharpeColor(tearSheet.sharpeRatio)}`}>
                {tearSheet.sharpeRatio.toFixed(2)}
              </div>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardContent className="p-6">
              <div className="text-sm text-gray-400 mb-1">Max Drawdown</div>
              <div className="text-3xl font-bold text-red-400">
                {tearSheet.maxDrawdown.toFixed(2)}%
              </div>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardContent className="p-6">
              <div className="text-sm text-gray-400 mb-1">Total Trades</div>
              <div className="text-3xl font-bold text-white">
                {tearSheet.totalTrades}
              </div>
          </CardContent>
        </Card>
        </div>
      </div>

      {/* Section 2: Performance & Profit */}
      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <TrendingUp className="w-5 h-5" />
            Performance & Profit
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Cumulative Returns Chart */}
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorStrategy" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorBenchmark" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="date" stroke="#9ca3af" />
                <YAxis stroke="#9ca3af" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #3b82f6', borderRadius: '8px' }}
                  labelStyle={{ color: '#fff' }}
                />
                <Legend />
                <Area 
                  type="monotone" 
                  dataKey="strategy" 
                  stroke="#3b82f6" 
                  fillOpacity={1} 
                  fill="url(#colorStrategy)"
                  name="GSIN Strategy"
                />
                <Area 
                  type="monotone" 
                  dataKey="benchmark" 
                  stroke="#8b5cf6" 
                  fillOpacity={1} 
                  fill="url(#colorBenchmark)"
                  name={tearSheet.benchmarkSymbol}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Performance Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-white/5 rounded-lg">
              <div className="text-sm text-gray-400 mb-1">Total Return</div>
              <div className={`text-2xl font-bold ${tearSheet.totalReturn >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {tearSheet.totalReturn >= 0 ? '+' : ''}{tearSheet.totalReturn.toFixed(2)}%
              </div>
            </div>
            <div className="p-4 bg-white/5 rounded-lg">
              <div className="text-sm text-gray-400 mb-1">Win Rate</div>
              <div className="text-2xl font-bold text-blue-400">
                {tearSheet.winRate.toFixed(1)}%
              </div>
            </div>
            <div className="p-4 bg-white/5 rounded-lg">
              <div className="text-sm text-gray-400 mb-1">Profit Factor</div>
              <div className="text-2xl font-bold text-green-400">
                {tearSheet.profitFactor.toFixed(2)}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Section 3: Risk & Drawdown */}
      <Card className="bg-black/60 backdrop-blur-xl border-red-500/20">
                <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-400" />
            Risk & Drawdown
                  </CardTitle>
                </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 bg-white/5 rounded-lg">
              <div className="text-sm text-gray-400 mb-1">Max Drawdown</div>
              <div className="text-2xl font-bold text-red-400">
                {tearSheet.maxDrawdown.toFixed(2)}%
                          </div>
                        </div>
            <div className="p-4 bg-white/5 rounded-lg">
              <div className="text-sm text-gray-400 mb-1 font-semibold">Peak Loss on a $10,000 Account</div>
              <div className="text-2xl font-bold text-red-400">
                -${Math.abs(tearSheet.maxDrawdownNormalized).toFixed(2)}
                          </div>
                        </div>
            <div className="p-4 bg-white/5 rounded-lg">
              <div className="text-sm text-gray-400 mb-1">Longest Drawdown Duration</div>
              <div className="text-2xl font-bold text-yellow-400">
                {tearSheet.longestDrawdownDuration}
                          </div>
                        </div>
            <div className="p-4 bg-white/5 rounded-lg">
              <div className="text-sm text-gray-400 mb-1">Sortino Ratio</div>
              <div className="text-2xl font-bold text-white">
                {tearSheet.sortinoRatio.toFixed(2)}
                        </div>
                      </div>
                    </div>
                </CardContent>
              </Card>

      {/* Section 4: GSIN Brain Analysis (MCN Report Card) */}
      <Card className="bg-black/60 backdrop-blur-xl border-purple-500/20">
                  <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Brain className="w-5 h-5 text-purple-400" />
            GSIN Brain Analysis (MCN Report Card)
                    </CardTitle>
                  </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* MCN Robustness Score */}
            <div className="p-6 bg-white/5 rounded-lg border border-purple-500/20">
              <div className="text-sm text-gray-400 mb-4">MCN Robustness Score</div>
              <div className="flex items-center gap-6">
                <div className="relative w-32 h-32 flex items-center justify-center">
                  <svg className="w-32 h-32 transform -rotate-90">
                    <circle
                      cx="64"
                      cy="64"
                      r="56"
                      stroke="#374151"
                      strokeWidth="8"
                      fill="none"
                    />
                    <circle
                      cx="64"
                      cy="64"
                      r="56"
                      stroke={tearSheet.mcnRobustnessScore >= 70 ? '#10b981' : tearSheet.mcnRobustnessScore >= 50 ? '#f59e0b' : '#ef4444'}
                      strokeWidth="8"
                      fill="none"
                      strokeDasharray={`${2 * Math.PI * 56}`}
                      strokeDashoffset={`${2 * Math.PI * 56 * (1 - tearSheet.mcnRobustnessScore / 100)}`}
                      strokeLinecap="round"
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-center">
                      <div className={`text-2xl font-bold ${
                        tearSheet.mcnRobustnessScore >= 70 ? 'text-green-400' : 
                        tearSheet.mcnRobustnessScore >= 50 ? 'text-yellow-400' : 
                        'text-red-400'
                      }`}>
                        {tearSheet.mcnRobustnessScore}
                          </div>
                      <div className="text-xs text-gray-400">/100</div>
                    </div>
                  </div>
                </div>
                <div className="text-sm text-gray-400">
                  Measures strategy stability across different market conditions based on MCN memory patterns.
                </div>
              </div>
                  </div>

            {/* Cross-Regime Stability */}
            <div className="p-6 bg-white/5 rounded-lg border border-purple-500/20">
              <div className="text-sm text-gray-400 mb-4">Cross-Regime Stability</div>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-gray-300">Bull Market:</span>
                  {getRegimeBadge(tearSheet.mcnRegimeStability.bull)}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-300">Bear Market:</span>
                  {getRegimeBadge(tearSheet.mcnRegimeStability.bear)}
                  </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-300">High Volatility:</span>
                  {getRegimeBadge(tearSheet.mcnRegimeStability.highVol)}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-300">Low Volatility:</span>
                  {getRegimeBadge(tearSheet.mcnRegimeStability.lowVol)}
                </div>
              </div>
                </div>
              </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-white/5 rounded-lg">
              <div className="text-sm text-gray-400 mb-1">Overfitting Risk</div>
              <div className={`text-xl font-bold ${
                tearSheet.mcnOverfittingRisk === 'Low' ? 'text-green-400' : 
                tearSheet.mcnOverfittingRisk === 'High' ? 'text-red-400' : 
                'text-yellow-400'
              }`}>
                {tearSheet.mcnOverfittingRisk}
              </div>
            </div>
            <div className="p-4 bg-white/5 rounded-lg">
              <div className="text-sm text-gray-400 mb-1">Strategy Novelty</div>
              <div className="text-xl font-bold text-purple-400">
                {tearSheet.mcnNoveltyScore}% Unique
              </div>
            </div>
            <div className="p-4 bg-white/5 rounded-lg">
              <div className="text-sm text-gray-400 mb-1">Strategy Lineage</div>
              <div className="text-sm font-semibold text-white">
                {tearSheet.mcnLineage}
                </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Section 5: Trade Behavior & Stats */}
      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5" />
            Trade Behavior & Stats
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 bg-white/5 rounded-lg">
              <div className="text-sm text-gray-400 mb-1">Trades per Month</div>
              <div className="text-2xl font-bold text-white">
                {tearSheet.tradesPerMonth.toFixed(1)}
            </div>
            </div>
            <div className="p-4 bg-white/5 rounded-lg">
              <div className="text-sm text-gray-400 mb-1">Average Time in Trade</div>
              <div className="text-2xl font-bold text-blue-400">
                {tearSheet.avgTimeInTrade}
            </div>
            </div>
            <div className="p-4 bg-white/5 rounded-lg">
              <div className="text-sm text-gray-400 mb-1">Average Win</div>
              <div className="text-2xl font-bold text-green-400">
                ${tearSheet.avgWin.toFixed(2)}
              </div>
            </div>
            <div className="p-4 bg-white/5 rounded-lg">
              <div className="text-sm text-gray-400 mb-1">Average Loss</div>
              <div className="text-2xl font-bold text-red-400">
                -${tearSheet.avgLoss.toFixed(2)}
            </div>
            </div>
            </div>
          </CardContent>
        </Card>

      {/* Back Button */}
      <div className="flex justify-start">
        <Link href="/strategies">
          <Button variant="ghost" className="gap-2 text-gray-400 hover:text-white">
            <ArrowLeft className="w-4 h-4" />
            Back to Marketplace
          </Button>
        </Link>
      </div>
    </div>
  );
}
