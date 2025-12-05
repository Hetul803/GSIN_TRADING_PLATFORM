'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Play, Download } from 'lucide-react';
import Link from 'next/link';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { useStore } from '@/lib/store';
import { toast } from 'sonner';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export default function BacktestPage({ params }: { params: { strategyId: string } }) {
  const router = useRouter();
  const user = useStore((state) => state.user);
  const [strategy, setStrategy] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [backtestResults, setBacktestResults] = useState<any>(null);

  useEffect(() => {
    if (!user?.id) {
      router.push('/login');
      return;
    }
    loadStrategy();
  }, [params.strategyId, user?.id, router]);

  async function loadStrategy() {
    if (!user?.id) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/strategies/${params.strategyId}`, {
        headers: { 'X-User-Id': user.id },
      });
      if (response.ok) {
        const data = await response.json();
        setStrategy(data);
      } else {
        toast.error('Strategy not found');
        router.push('/strategies');
      }
    } catch (error) {
      console.error('Error loading strategy:', error);
      toast.error('Failed to load strategy');
    } finally {
      setLoading(false);
    }
  }

  if (!user?.id) {
    return null;
  }

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white text-lg">Loading...</div>
      </div>
    );
  }

  if (!strategy) {
    return (
      <div className="p-6 space-y-6">
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardContent className="p-12 text-center">
            <p className="text-gray-400 text-lg mb-2">Strategy not found</p>
            <Link href="/strategies">
              <Button variant="outline" className="mt-4">Back to Strategies</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Use backtest results if available, otherwise show empty state
  const drawdownData = backtestResults?.equity_curve?.map((point: any, idx: number) => ({
    day: idx + 1,
    drawdown: point.drawdown || 0,
  })) || [];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <Link href="/strategies">
          <Button variant="ghost" className="gap-2 text-gray-400 hover:text-white">
            <ArrowLeft className="w-4 h-4" />
            Back to Strategies
          </Button>
        </Link>
        <div className="flex gap-3">
          <Button variant="outline" className="gap-2 bg-white/5 border-blue-500/20 text-white">
            <Download className="w-4 h-4" />
            Export Report
          </Button>
          <Button className="gap-2 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700">
            <Play className="w-4 h-4" />
            Run New Backtest
          </Button>
        </div>
      </div>

      <div>
        <h1 className="text-3xl font-bold text-white">{strategy.name} - Backtest Results</h1>
        <p className="text-gray-400">Comprehensive backtesting analysis and performance metrics</p>
      </div>

      {backtestResults && backtestResults.equity_curve ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Total Return</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-400">+{backtestResults.total_return || strategy.train_metrics?.total_return || strategy.test_metrics?.total_return || 0}%</div>
            <div className="text-xs text-gray-400 mt-1">Over {backtestResults.equity_curve?.length || 0} days</div>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Max Drawdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-400">{backtestResults.max_drawdown || strategy.train_metrics?.max_drawdown || strategy.test_metrics?.max_drawdown || 0}%</div>
            <div className="text-xs text-gray-400 mt-1">Peak to trough</div>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Sharpe Ratio</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-white">{backtestResults.sharpe_ratio || strategy.train_metrics?.sharpe_ratio || strategy.test_metrics?.sharpe_ratio || 0}</div>
            <div className="text-xs text-gray-400 mt-1">Risk-adjusted return</div>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Win Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-white">{backtestResults.win_rate || strategy.train_metrics?.win_rate || strategy.test_metrics?.win_rate || 0}%</div>
            <div className="text-xs text-gray-400 mt-1">{Math.round((backtestResults.total_trades || strategy.train_metrics?.total_trades || strategy.test_metrics?.total_trades || 0) * ((backtestResults.win_rate || strategy.train_metrics?.win_rate || strategy.test_metrics?.win_rate || 0) / 100))} winners</div>
          </CardContent>
        </Card>
      </div>

      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardHeader>
          <CardTitle className="text-white">Equity Curve</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={400}>
            <AreaChart data={backtestResults.equity_curve || []}>
              <defs>
                <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="day" stroke="#64748b" />
              <YAxis stroke="#64748b" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid #1e293b',
                  borderRadius: '8px',
                }}
              />
              <Area
                type="monotone"
                dataKey="equity"
                stroke="#3b82f6"
                strokeWidth={2}
                fill="url(#colorEquity)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardHeader>
          <CardTitle className="text-white">Drawdown Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={drawdownData}>
              <defs>
                <linearGradient id="colorDrawdown" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="day" stroke="#64748b" />
              <YAxis stroke="#64748b" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid #1e293b',
                  borderRadius: '8px',
                }}
              />
              <Area
                type="monotone"
                dataKey="drawdown"
                stroke="#ef4444"
                strokeWidth={2}
                fill="url(#colorDrawdown)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white">Performance Metrics</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {[
              { label: 'Total Trades', value: backtestResults.total_trades || strategy.train_metrics?.total_trades || strategy.test_metrics?.total_trades || 0 },
              { label: 'Winning Trades', value: Math.round((backtestResults.total_trades || strategy.train_metrics?.total_trades || strategy.test_metrics?.total_trades || 0) * ((backtestResults.win_rate || strategy.train_metrics?.win_rate || strategy.test_metrics?.win_rate || 0) / 100)), color: 'text-green-400' },
              { label: 'Losing Trades', value: Math.round((backtestResults.total_trades || strategy.train_metrics?.total_trades || strategy.test_metrics?.total_trades || 0) * ((100 - (backtestResults.win_rate || strategy.train_metrics?.win_rate || strategy.test_metrics?.win_rate || 0)) / 100)), color: 'text-red-400' },
              { label: 'Average Win', value: '$1,245', color: 'text-green-400' },
              { label: 'Average Loss', value: '$523', color: 'text-red-400' },
              { label: 'Largest Win', value: '$5,430', color: 'text-green-400' },
              { label: 'Largest Loss', value: '$1,890', color: 'text-red-400' },
              { label: 'Profit Factor', value: '2.38' },
              { label: 'Recovery Factor', value: '6.45' },
              { label: 'Calmar Ratio', value: '4.12' },
            ].map((metric, idx) => (
              <div key={idx} className="flex justify-between items-center p-2 hover:bg-white/5 rounded">
                <span className="text-gray-400">{metric.label}</span>
                <span className={`font-semibold ${metric.color || 'text-white'}`}>{metric.value}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white">Risk Metrics</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {[
              { label: 'Standard Deviation', value: '8.4%' },
              { label: 'Downside Deviation', value: '5.2%' },
              { label: 'Sortino Ratio', value: '3.89' },
              { label: 'Max Consecutive Wins', value: '12' },
              { label: 'Max Consecutive Losses', value: '5' },
              { label: 'Average Trade Duration', value: '4.2 hours' },
              { label: 'Exposure Time', value: '67.5%' },
              { label: 'System Quality Number', value: '3.2' },
              { label: 'Ulcer Index', value: '4.8' },
              { label: 'Serenity Index', value: '92.3%' },
            ].map((metric, idx) => (
              <div key={idx} className="flex justify-between items-center p-2 hover:bg-white/5 rounded">
                <span className="text-gray-400">{metric.label}</span>
                <span className="font-semibold text-white">{metric.value}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
        </>
      ) : (
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardContent className="p-12 text-center">
            <p className="text-gray-400 text-lg mb-4">No backtest results available</p>
            <p className="text-gray-500 text-sm mb-6">Run a backtest to see performance metrics and charts</p>
            <Button 
              className="gap-2 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700"
              onClick={() => router.push(`/strategies/${params.strategyId}`)}
            >
              <Play className="w-4 h-4" />
              Run Backtest
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
