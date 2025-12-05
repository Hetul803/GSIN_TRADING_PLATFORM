'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Brain, TrendingUp, Activity, RefreshCw, Sparkles, Clock } from 'lucide-react';
import { useStore } from '@/lib/store';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface BrainSummary {
  total_strategies: number;
  active_strategies: number;
  mutated_strategies: number;
  top_strategies: Array<{
    strategy_id: string;
    name: string;
    score: number;
    win_rate: number;
    avg_return: number;
  }>;
  last_evolution_run_at: string | null;
}

interface TestingStrategy {
  id: string;
  name: string;
  status: string;
  last_backtest_at: string | null;
  evolution_attempts: number;
}

export default function BrainEvolutionPage() {
  const router = useRouter();
  const user = useStore((state) => state.user);
  const [summary, setSummary] = useState<BrainSummary | null>(null);
  const [testingStrategies, setTestingStrategies] = useState<TestingStrategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (!user?.id) {
      router.push('/login');
      return;
    }
    loadSummary();
    loadTestingStrategies();
  }, [user?.id, router]);

  async function loadTestingStrategies() {
    if (!user?.id) return;
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/strategies`, {
        headers: { 'X-User-Id': user.id },
      });
      if (response.ok) {
        const data = await response.json();
        // Filter strategies that are still being tested (experiment status, no backtest yet or recent backtest)
        const testing = (data || []).filter((s: any) => 
          s.status === 'experiment' || (s.status === 'candidate' && !s.is_proposable)
        );
        setTestingStrategies(testing);
      }
    } catch (error) {
      console.error('Error loading testing strategies:', error);
    }
  }

  async function loadSummary() {
    setLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/brain/summary`, {
        headers: {
          'X-User-Id': user?.id || '',
        },
      });
      
      if (response.ok) {
        const data = await response.json();
        setSummary(data);
      } else {
        console.error('Failed to load brain summary');
      }
    } catch (error) {
      console.error('Failed to load brain summary:', error);
    } finally {
      setLoading(false);
    }
  }

  if (!mounted) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white text-lg">Loading...</div>
      </div>
    );
  }

  if (!user?.id) {
    return null;
  }

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-400" />
      </div>
    );
  }

  // Calculate estimated completion time (rough estimate: 5-10 minutes per strategy)
  const estimateCompletionTime = (strategy: TestingStrategy) => {
    const avgTimePerStrategy = 7; // minutes
    return strategy.evolution_attempts * avgTimePerStrategy;
  };

  // Format top strategies for chart
  const topStrategiesChart = (summary?.top_strategies || []).map((s, idx) => ({
    name: s.name.length > 15 ? s.name.substring(0, 15) + '...' : s.name,
    score: s.score * 100,
    win_rate: s.win_rate * 100,
    avg_return: s.avg_return * 100,
  }));

  if (!summary) {
    return (
      <div className="p-6 space-y-6" suppressHydrationWarning>
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
            <Brain className="w-10 h-10 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white">Brain Evolution</h1>
            <p className="text-gray-400">Strategy evolution and performance overview</p>
          </div>
        </div>
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardContent className="p-6 text-center">
            <p className="text-gray-400">No brain evolution data available yet</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6" suppressHydrationWarning>
      <div className="flex items-center gap-4">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
          <Brain className="w-10 h-10 text-white" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-white">Brain Evolution</h1>
          <p className="text-gray-400">Strategy evolution and performance overview</p>
        </div>
      </div>

      {/* Strategies Currently Being Tested */}
      {testingStrategies.length > 0 && (
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Clock className="w-5 h-5 text-yellow-400" />
              Strategies Currently Being Tested
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {testingStrategies.map((strategy) => {
                const estimatedMinutes = estimateCompletionTime(strategy);
                return (
                  <div
                    key={strategy.id}
                    className="p-4 bg-white/5 rounded-lg border border-blue-500/20"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="font-semibold text-white mb-1">{strategy.name}</h3>
                        <div className="flex items-center gap-4 text-sm text-gray-400">
                          <span>Status: <span className="text-blue-400 capitalize">{strategy.status}</span></span>
                          <span>Attempts: {strategy.evolution_attempts}</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm text-gray-400">Estimated Time</div>
                        <div className="text-lg font-bold text-yellow-400">
                          ~{estimatedMinutes} min
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Total Strategies</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-white">{summary.total_strategies}</div>
            <p className="text-xs text-gray-500 mt-1">All strategies created</p>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-green-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Active Strategies</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-green-400">{summary.active_strategies}</div>
            <p className="text-xs text-gray-500 mt-1">Currently active</p>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-purple-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Mutated Strategies</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-purple-400">{summary.mutated_strategies}</div>
            <p className="text-xs text-gray-500 mt-1">Evolved from parents</p>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-pink-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">Last Evolution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm font-bold text-pink-400">
              {summary.last_evolution_run_at
                ? new Date(summary.last_evolution_run_at).toLocaleDateString()
                : 'Never'}
            </div>
            <p className="text-xs text-gray-500 mt-1">Most recent mutation/backtest</p>
          </CardContent>
        </Card>
      </div>

      {/* Top Strategies */}
      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-purple-400" />
            Top Performing Strategies
          </CardTitle>
        </CardHeader>
        <CardContent>
          {summary.top_strategies.length > 0 ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {summary.top_strategies.slice(0, 6).map((strategy) => (
                  <div
                    key={strategy.strategy_id}
                    className="p-4 bg-white/5 rounded-lg border border-blue-500/20 hover:border-blue-500/40 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-semibold text-white">{strategy.name}</h3>
                      <Badge className="bg-purple-500/20 text-purple-400">
                        Score: {(strategy.score * 100).toFixed(1)}%
                      </Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-2 mt-3 text-sm">
                      <div>
                        <span className="text-gray-400">Win Rate:</span>
                        <span className="ml-2 text-green-400 font-semibold">
                          {(strategy.win_rate * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-400">Avg Return:</span>
                        <span
                          className={`ml-2 font-semibold ${
                            strategy.avg_return >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}
                        >
                          {(strategy.avg_return * 100).toFixed(2)}%
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Performance Chart */}
              {topStrategiesChart.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-white font-semibold mb-4">Strategy Performance Comparison</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={topStrategiesChart}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="name" stroke="#64748b" angle={-45} textAnchor="end" height={80} />
                      <YAxis stroke="#64748b" />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#0f172a',
                          border: '1px solid #1e293b',
                          borderRadius: '8px',
                        }}
                      />
                      <Line
                        type="monotone"
                        dataKey="score"
                        stroke="#8b5cf6"
                        strokeWidth={2}
                        name="Score (%)"
                      />
                      <Line
                        type="monotone"
                        dataKey="win_rate"
                        stroke="#10b981"
                        strokeWidth={2}
                        name="Win Rate (%)"
                      />
                      <Line
                        type="monotone"
                        dataKey="avg_return"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        name="Avg Return (%)"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-400">
              <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No strategies available yet</p>
              <p className="text-xs mt-2">Create or run backtests on strategies to see evolution data</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
