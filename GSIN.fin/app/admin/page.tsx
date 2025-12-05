'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useStore } from '@/lib/store';
import { Shield, Edit, Save, X, MessageSquare } from 'lucide-react';
import { toast } from 'sonner';
import { apiRequest } from '@/lib/api-client';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface Plan {
  id: string;
  planCode: string;
  name: string;
  priceMonthly: number;
  defaultRoyaltyPercent: number;
  platformFeePercent: number;
  description: string;
  isCreatorPlan: boolean;
  isActive: boolean;
}

interface AdminStats {
  totalUsers: number;
  userTier: number;
  proTier: number;
  creatorTier: number;
  totalStrategies: number;
  totalTrades: number;
  totalPnl: number;
  totalRoyalties: number;
  groupsCreated: number;
  revenue: {
    today: number;
    week: number;
    month: number;
  };
}

interface AdminMetrics {
  users: {
    total_users: number;
    active_users: number;
    current_month_paying_by_tier: { [key: string]: number };
  };
  strategies: {
    total_active: number;
    pending_backtest: number;
    currently_backtesting: number;
    user_generated: {
      total: number;
      active: number;
      pending_backtest: number;
      currently_backtesting: number;
    };
    brain_generated: {
      total: number;
      active: number;
      pending_backtest: number;
      currently_backtesting: number;
    };
  };
  trading: {
    brain_strategies: {
      pnl: number;
      sharpe: number;
      drawdown: number;
    };
    user_strategies: {
      pnl: number;
      sharpe: number;
      drawdown: number;
    };
  };
  revenue: {
    subscriptions: number;
    royalties: number;
    platform_fees: number;
  };
  top_strategies: {
    most_used: Array<{ strategy_id: string; strategy_name: string; trade_count: number }>;
    by_sharpe: Array<{ strategy_id: string; strategy_name: string; sharpe_ratio: number }>;
    by_profit: Array<{ strategy_id: string; strategy_name: string; total_profit: number }>;
    by_drawdown: Array<{ strategy_id: string; strategy_name: string; drawdown: number }>;
  };
  system: {
    market_data_provider_status: string;
    evolution_worker_status: string;
    db_status: string;
    redis_status: string;
    error_count_last_24h: number;
  };
}

export default function AdminPage() {
  const router = useRouter();
  const user = useStore((state) => state.user);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMetrics, setLoadingMetrics] = useState(false);
  const [editingPlan, setEditingPlan] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<{ price?: number; royalty?: number; platformFee?: number }>({});
  const [showMessageModal, setShowMessageModal] = useState(false);
  const [messageTitle, setMessageTitle] = useState('');
  const [messageBody, setMessageBody] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);
  const [adminSettings, setAdminSettings] = useState<any>(null);
  const [editingBacktestConfig, setEditingBacktestConfig] = useState(false);
  const [maxConcurrentBacktests, setMaxConcurrentBacktests] = useState(3);

  useEffect(() => {
    if (!user?.id) {
      router.push('/login');
      return;
    }
    
    // Check if user is admin
    if (user.email?.toLowerCase() !== 'patelhetul803@gmail.com') {
      router.push('/dashboard');
      return;
    }
    
    loadPlans();
    loadStats();
    loadMetrics();
    loadAdminSettings();
    
    // Poll for metrics updates every 5 seconds for real-time feel
    const metricsInterval = setInterval(() => {
      loadMetrics();
    }, 5000);
    
    return () => clearInterval(metricsInterval);
  }, [user, router]);
  
  async function loadAdminSettings() {
    try {
      const data = await apiRequest('/api/admin/settings');
      setAdminSettings(data);
      setMaxConcurrentBacktests(data.max_concurrent_backtests || 3);
    } catch (error) {
      console.error('Error loading admin settings:', error);
    }
  }
  
  async function saveBacktestConfig() {
    try {
      await apiRequest('/api/admin/settings', {
        method: 'PUT',
        body: JSON.stringify({
          max_concurrent_backtests: maxConcurrentBacktests,
        }),
      });
      toast.success('Backtest configuration updated');
      setEditingBacktestConfig(false);
      await loadAdminSettings();
    } catch (error: any) {
      console.error('Error updating backtest config:', error);
      toast.error(error.message || 'Failed to update backtest configuration');
    }
  }

  async function loadPlans() {
    try {
      const data = await apiRequest<{ plans: Plan[] }>('/api/admin/plans');
      setPlans(data.plans || []);
    } catch (error) {
      console.error('Error loading plans:', error);
      toast.error('Failed to load subscription plans');
    } finally {
      setLoading(false);
    }
  }

  async function loadStats() {
    try {
      const data = await apiRequest<AdminStats>('/api/admin/stats');
      setStats(data);
    } catch (error) {
      console.error('Error loading admin stats:', error);
      toast.error('Failed to load admin statistics');
    }
  }

  async function loadMetrics() {
    setLoadingMetrics(true);
    try {
      const data = await apiRequest<AdminMetrics>('/api/admin/metrics/summary');
      setMetrics(data);
    } catch (error) {
      console.error('Error loading admin metrics:', error);
      // Set default metrics with zeros so boxes still show
      setMetrics({
        users: {
          total_users: 0,
          active_users: 0,
          current_month_paying_by_tier: { basic: 0, pro: 0, creator: 0 }
        },
        strategies: {
          total_active: 0,
          pending_backtest: 0,
          currently_backtesting: 0,
          user_generated: {
            total: 0,
            active: 0,
            pending_backtest: 0,
            currently_backtesting: 0
          },
          brain_generated: {
            total: 0,
            active: 0,
            pending_backtest: 0,
            currently_backtesting: 0
          }
        },
        trading: {
          brain_strategies: {
            pnl: 0,
            sharpe: 0,
            drawdown: 0
          },
          user_strategies: {
            pnl: 0,
            sharpe: 0,
            drawdown: 0
          }
        },
        revenue: {
          subscriptions: 0,
          royalties: 0,
          platform_fees: 0
        },
        top_strategies: {
          most_used: [],
          by_sharpe: [],
          by_profit: [],
          by_drawdown: []
        },
        system: {
          market_data_provider_status: "unknown",
          evolution_worker_status: "unknown",
          db_status: "unknown",
          redis_status: "not_configured",
          error_count_last_24h: 0
        }
      });
      // Don't show error toast - just use defaults
    } finally {
      setLoadingMetrics(false);
    }
  }

  function startEdit(plan: Plan) {
    setEditingPlan(plan.id);
    setEditValues({
      price: plan.priceMonthly / 100, // Convert cents to dollars
      royalty: plan.defaultRoyaltyPercent || 0,
      platformFee: plan.platformFeePercent || 0,
    });
  }

  function cancelEdit() {
    setEditingPlan(null);
    setEditValues({});
  }

  async function sendMessageToAllUsers() {
    if (!messageTitle.trim() || !messageBody.trim()) {
      toast.error('Please fill in both title and message');
      return;
    }
    
    setSendingMessage(true);
    try {
      await apiRequest('/api/admin/send-message', {
        method: 'POST',
        body: JSON.stringify({
          title: messageTitle,
          message: messageBody,
        }),
      });
      toast.success('Message sent to all users');
      setShowMessageModal(false);
      setMessageTitle('');
      setMessageBody('');
    } catch (error: any) {
      console.error('Error sending message:', error);
      toast.error(error.message || 'Failed to send message');
    } finally {
      setSendingMessage(false);
    }
  }

  async function savePlan(planId: string) {
    if (!user?.id) return;
    
    try {
      const updates: any = {};
      if (editValues.price !== undefined && editValues.price !== null) {
        updates.priceMonthly = Math.round(editValues.price * 100); // Convert to cents
      }
      if (editValues.royalty !== undefined && editValues.royalty !== null) {
        updates.defaultRoyaltyPercent = parseFloat(editValues.royalty.toString());
      }
      if (editValues.platformFee !== undefined && editValues.platformFee !== null) {
        updates.platformFeePercent = parseFloat(editValues.platformFee.toString());
      }

      // Validate that at least one field is being updated
      if (Object.keys(updates).length === 0) {
        toast.error('Please enter values to update');
        return;
      }

      console.log('Sending update request:', { planId, updates });

      await apiRequest(`/api/admin/plans/${planId}`, {
        method: 'PUT',
        body: JSON.stringify(updates),
      });
      toast.success('Plan updated successfully');
      setEditingPlan(null);
      setEditValues({});
      await loadPlans(); // Reload plans to get updated data
    } catch (error: any) {
      console.error('Error updating plan:', error);
      toast.error(error.message || 'Failed to update plan');
    }
  }

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white text-lg">Loading...</div>
      </div>
    );
  }


  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <Shield className="w-8 h-8 text-red-400" />
            Admin Dashboard
          </h1>
          <p className="text-gray-400">Platform overview and management</p>
        </div>
      </div>

      {/* Admin Statistics */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardContent className="p-6">
              <div className="text-sm text-gray-400 mb-1">Total Users</div>
              <div className="text-3xl font-bold text-white">{stats.totalUsers.toLocaleString()}</div>
              <div className="text-xs text-gray-500 mt-2">
                User: {stats.userTier} • Pro: {stats.proTier} • Creator: {stats.creatorTier}
              </div>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardContent className="p-6">
              <div className="text-sm text-gray-400 mb-1">Total Strategies</div>
              <div className="text-3xl font-bold text-blue-400">{stats.totalStrategies.toLocaleString()}</div>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardContent className="p-6">
              <div className="text-sm text-gray-400 mb-1">Total Trades</div>
              <div className="text-3xl font-bold text-green-400">{stats.totalTrades.toLocaleString()}</div>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardContent className="p-6">
              <div className="text-sm text-gray-400 mb-1">Total P&L</div>
              <div className={`text-3xl font-bold ${stats.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {stats.totalPnl >= 0 ? '+' : ''}${stats.totalPnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardContent className="p-6">
              <div className="text-sm text-gray-400 mb-1">Total Royalties</div>
              <div className="text-3xl font-bold text-purple-400">
                ${stats.totalRoyalties.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardContent className="p-6">
              <div className="text-sm text-gray-400 mb-1">Groups Created</div>
              <div className="text-3xl font-bold text-yellow-400">{stats.groupsCreated.toLocaleString()}</div>
            </CardContent>
          </Card>

          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardContent className="p-6">
              <div className="text-sm text-gray-400 mb-1">Revenue (Today)</div>
              <div className="text-3xl font-bold text-green-400">
                ${stats.revenue.today.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </CardContent>
        </Card>

          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardContent className="p-6">
              <div className="text-sm text-gray-400 mb-1">Revenue (Month)</div>
              <div className="text-3xl font-bold text-blue-400">
                ${stats.revenue.month.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
          </CardContent>
        </Card>
            </div>
      )}

      {/* Comprehensive Admin Metrics Section */}
      <div className="space-y-6 mt-6">
        {/* User Metrics */}
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Shield className="w-5 h-5" />
              User Metrics
              {loadingMetrics && <span className="text-xs text-gray-400 ml-2">(Loading...)</span>}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {metrics ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-1">Total Users</div>
                  <div className="text-2xl font-bold text-white">{metrics.users.total_users || 0}</div>
                </div>
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-1">Active Users (24h)</div>
                  <div className="text-2xl font-bold text-green-400">{metrics.users.active_users || 0}</div>
                </div>
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-1">Current Month Paying Users</div>
                  <div className="text-2xl font-bold text-blue-400">
                    {(metrics.users.current_month_paying_by_tier?.basic || 0) + 
                     (metrics.users.current_month_paying_by_tier?.pro || 0) + 
                     (metrics.users.current_month_paying_by_tier?.creator || 0)}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    Basic: {metrics.users.current_month_paying_by_tier?.basic || 0} • 
                    Pro: {metrics.users.current_month_paying_by_tier?.pro || 0} • 
                    Creator: {metrics.users.current_month_paying_by_tier?.creator || 0}
                  </div>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-1">Total Users</div>
                  <div className="text-2xl font-bold text-white">0</div>
                </div>
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-1">Active Users (24h)</div>
                  <div className="text-2xl font-bold text-green-400">0</div>
                </div>
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-1">Current Month Paying Users</div>
                  <div className="text-2xl font-bold text-blue-400">0</div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Strategy Metrics */}
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white">Strategy Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            {metrics ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 bg-white/5 rounded-lg">
                    <div className="text-sm text-gray-400 mb-1">Total Active Strategies</div>
                    <div className="text-2xl font-bold text-blue-400">{metrics.strategies.total_active || 0}</div>
                  </div>
                  <div className="p-4 bg-white/5 rounded-lg">
                    <div className="text-sm text-gray-400 mb-1">Pending Backtest</div>
                    <div className="text-2xl font-bold text-yellow-400">{metrics.strategies.pending_backtest || 0}</div>
                  </div>
                  <div className="p-4 bg-white/5 rounded-lg">
                    <div className="text-sm text-gray-400 mb-1">Currently Backtesting</div>
                    <div className="text-2xl font-bold text-purple-400">{metrics.strategies.currently_backtesting || 0}</div>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                  <div className="p-4 bg-white/5 rounded-lg border border-blue-500/20">
                    <div className="text-sm text-gray-400 mb-2">User Generated Strategies</div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>Total: <span className="font-bold text-white">{metrics.strategies.user_generated?.total || 0}</span></div>
                      <div>Active: <span className="font-bold text-green-400">{metrics.strategies.user_generated?.active || 0}</span></div>
                      <div>Pending: <span className="font-bold text-yellow-400">{metrics.strategies.user_generated?.pending_backtest || 0}</span></div>
                      <div>Backtesting: <span className="font-bold text-purple-400">{metrics.strategies.user_generated?.currently_backtesting || 0}</span></div>
                    </div>
                  </div>
                  <div className="p-4 bg-white/5 rounded-lg border border-purple-500/20">
                    <div className="text-sm text-gray-400 mb-2">Brain Generated Strategies</div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>Total: <span className="font-bold text-white">{metrics.strategies.brain_generated?.total || 0}</span></div>
                      <div>Active: <span className="font-bold text-green-400">{metrics.strategies.brain_generated?.active || 0}</span></div>
                      <div>Pending: <span className="font-bold text-yellow-400">{metrics.strategies.brain_generated?.pending_backtest || 0}</span></div>
                      <div>Backtesting: <span className="font-bold text-purple-400">{metrics.strategies.brain_generated?.currently_backtesting || 0}</span></div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-gray-400">Loading...</div>
            )}
          </CardContent>
        </Card>

        {/* Trading Metrics */}
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white">Trading Performance</CardTitle>
          </CardHeader>
          <CardContent>
            {metrics ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 bg-white/5 rounded-lg border border-blue-500/20">
                  <div className="text-sm text-gray-400 mb-2">Brain Generated Strategies</div>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-400">PnL:</span>
                      <span className={`font-bold ${metrics.trading.brain_strategies?.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        ${(metrics.trading.brain_strategies?.pnl || 0).toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Sharpe:</span>
                      <span className="font-bold text-white">{(metrics.trading.brain_strategies?.sharpe || 0).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Drawdown:</span>
                      <span className="font-bold text-red-400">${(metrics.trading.brain_strategies?.drawdown || 0).toFixed(2)}</span>
                    </div>
                  </div>
                </div>
                <div className="p-4 bg-white/5 rounded-lg border border-purple-500/20">
                  <div className="text-sm text-gray-400 mb-2">User Generated Strategies</div>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-400">PnL:</span>
                      <span className={`font-bold ${metrics.trading.user_strategies?.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        ${(metrics.trading.user_strategies?.pnl || 0).toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Sharpe:</span>
                      <span className="font-bold text-white">{(metrics.trading.user_strategies?.sharpe || 0).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Drawdown:</span>
                      <span className="font-bold text-red-400">${(metrics.trading.user_strategies?.drawdown || 0).toFixed(2)}</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-gray-400">Loading...</div>
            )}
          </CardContent>
        </Card>

        {/* Revenue Metrics */}
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white">Revenue</CardTitle>
          </CardHeader>
          <CardContent>
            {metrics ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-1">Subscriptions (MRR)</div>
                  <div className="text-2xl font-bold text-green-400">${(metrics.revenue.subscriptions || 0).toFixed(2)}</div>
                </div>
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-1">Royalties</div>
                  <div className="text-2xl font-bold text-purple-400">${(metrics.revenue.royalties || 0).toFixed(2)}</div>
                </div>
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-1">Platform Fees</div>
                  <div className="text-2xl font-bold text-blue-400">${(metrics.revenue.platform_fees || 0).toFixed(2)}</div>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-1">Subscriptions (MRR)</div>
                  <div className="text-2xl font-bold text-green-400">$0.00</div>
                </div>
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-1">Royalties</div>
                  <div className="text-2xl font-bold text-purple-400">$0.00</div>
                </div>
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-1">Platform Fees</div>
                  <div className="text-2xl font-bold text-blue-400">$0.00</div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Strategies */}
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white">Top Strategies</CardTitle>
          </CardHeader>
          <CardContent>
            {metrics ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-2">Most Used</div>
                  <div className="space-y-1 text-xs">
                    {metrics.top_strategies.most_used?.slice(0, 5).map((s, i) => (
                      <div key={s.strategy_id} className="flex justify-between">
                        <span className="text-gray-400">{i + 1}. {s.strategy_name}</span>
                        <span className="text-white">{s.trade_count}</span>
                      </div>
                    )) || <div className="text-gray-500">No data</div>}
                  </div>
                </div>
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-2">By Sharpe</div>
                  <div className="space-y-1 text-xs">
                    {metrics.top_strategies.by_sharpe?.slice(0, 5).map((s, i) => (
                      <div key={s.strategy_id} className="flex justify-between">
                        <span className="text-gray-400">{i + 1}. {s.strategy_name}</span>
                        <span className="text-white">{s.sharpe_ratio.toFixed(2)}</span>
                      </div>
                    )) || <div className="text-gray-500">No data</div>}
                  </div>
                </div>
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-2">By Profit</div>
                  <div className="space-y-1 text-xs">
                    {metrics.top_strategies.by_profit?.slice(0, 5).map((s, i) => (
                      <div key={s.strategy_id} className="flex justify-between">
                        <span className="text-gray-400">{i + 1}. {s.strategy_name}</span>
                        <span className="text-green-400">${s.total_profit.toFixed(2)}</span>
                      </div>
                    )) || <div className="text-gray-500">No data</div>}
                  </div>
                </div>
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="text-sm text-gray-400 mb-2">By Drawdown</div>
                  <div className="space-y-1 text-xs">
                    {metrics.top_strategies.by_drawdown?.slice(0, 5).map((s, i) => (
                      <div key={s.strategy_id} className="flex justify-between">
                        <span className="text-gray-400">{i + 1}. {s.strategy_name}</span>
                        <span className="text-red-400">${s.drawdown.toFixed(2)}</span>
                      </div>
                    )) || <div className="text-gray-500">No data</div>}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-gray-400">Loading...</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Subscription Plans Management */}
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
          <CardTitle className="text-white">Subscription Plans Management</CardTitle>
          </CardHeader>
          <CardContent>
          <div className="space-y-4">
            {plans.map((plan) => (
              <div
                key={plan.id}
                className="p-4 bg-white/5 border border-blue-500/20 rounded-lg"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-white">{plan.name}</h3>
                      <span className="text-xs px-2 py-1 bg-blue-500/20 text-blue-400 rounded">
                        {plan.planCode}
                      </span>
                    </div>
                    <p className="text-sm text-gray-400 mb-3">{plan.description}</p>
                    
                    {editingPlan === plan.id ? (
                      <div className="space-y-3">
                        <div>
                          <Label className="text-gray-300">Monthly Price ($)</Label>
                          <Input
                            type="number"
                            step="0.01"
                            min="0"
                            value={editValues.price}
                            onChange={(e) => {
                              const val = e.target.value === '' ? 0 : parseFloat(e.target.value);
                              setEditValues({ ...editValues, price: isNaN(val) ? 0 : val });
                            }}
                            className="mt-1 bg-white/5 border-blue-500/20 text-white"
                            placeholder="0.00 (Free plan)"
                          />
                        </div>
                        <div>
                          <Label className="text-gray-300">Default Royalty %</Label>
                          <Input
                            type="number"
                            step="0.1"
                            value={editValues.royalty}
                            onChange={(e) => setEditValues({ ...editValues, royalty: parseFloat(e.target.value) })}
                            className="mt-1 bg-white/5 border-blue-500/20 text-white"
                          />
                        </div>
                        <div>
                          <Label className="text-gray-300">Platform Fee %</Label>
                          <Input
                            type="number"
                            step="0.1"
                            value={editValues.platformFee}
                            onChange={(e) => setEditValues({ ...editValues, platformFee: parseFloat(e.target.value) })}
                            className="mt-1 bg-white/5 border-blue-500/20 text-white"
                          />
                        </div>
                        <div className="flex gap-2">
                          <Button
                            onClick={() => savePlan(plan.id)}
                            className="bg-blue-600 hover:bg-blue-700"
                          >
                            <Save className="w-4 h-4 mr-2" />
                            Save
                          </Button>
                          <Button
                            onClick={cancelEdit}
                            variant="outline"
                            className="bg-white/5 border-blue-500/20 text-white"
                          >
                            <X className="w-4 h-4 mr-2" />
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="grid grid-cols-3 gap-4">
                        <div>
                          <div className="text-xs text-gray-400 mb-1">Monthly Price</div>
                          <div className="text-lg font-bold text-white">
                            ${(plan.priceMonthly / 100).toFixed(2)}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs text-gray-400 mb-1">Default Royalty</div>
                          <div className="text-lg font-bold text-blue-400">
                            {plan.defaultRoyaltyPercent}%
                          </div>
                        </div>
                        <div>
                          <div className="text-xs text-gray-400 mb-1">Platform Fee</div>
                          <div className="text-lg font-bold text-purple-400">
                            {plan.platformFeePercent}%
                          </div>
                        </div>
            </div>
                    )}
            </div>
                  {editingPlan !== plan.id && (
                    <Button
                      onClick={() => startEdit(plan)}
                      variant="outline"
                      className="ml-4 bg-white/5 border-blue-500/20 text-white"
                    >
                      <Edit className="w-4 h-4 mr-2" />
                      Edit
                    </Button>
                  )}
            </div>
            </div>
            ))}
            </div>
          </CardContent>
        </Card>

      {/* Backtest Configuration */}
      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20 mt-6">
        <CardHeader>
          <CardTitle className="text-white">Backtest Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-4 bg-white/5 rounded-lg">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-sm text-gray-400 mb-1">Max Concurrent Backtests</div>
                <div className="text-sm text-gray-500">
                  Controls how many backtests can run simultaneously. Higher values increase throughput but may impact system performance.
                </div>
              </div>
              {!editingBacktestConfig && (
                <Button
                  onClick={() => setEditingBacktestConfig(true)}
                  variant="outline"
                  className="bg-white/5 border-blue-500/20 text-white"
                >
                  <Edit className="w-4 h-4 mr-2" />
                  Edit
                </Button>
              )}
            </div>
            {editingBacktestConfig ? (
              <div className="space-y-3">
                <div>
                  <Label className="text-gray-300">Max Concurrent Backtests (1-20)</Label>
                  <Input
                    type="number"
                    min="1"
                    max="20"
                    value={maxConcurrentBacktests}
                    onChange={(e) => setMaxConcurrentBacktests(parseInt(e.target.value) || 3)}
                    className="mt-1 bg-white/5 border-blue-500/20 text-white"
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    onClick={saveBacktestConfig}
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    <Save className="w-4 h-4 mr-2" />
                    Save
                  </Button>
                  <Button
                    onClick={() => {
                      setEditingBacktestConfig(false);
                      setMaxConcurrentBacktests(adminSettings?.max_concurrent_backtests || 3);
                    }}
                    variant="outline"
                    className="bg-white/5 border-blue-500/20 text-white"
                  >
                    <X className="w-4 h-4 mr-2" />
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="text-2xl font-bold text-blue-400">
                {adminSettings?.max_concurrent_backtests || 3}
              </div>
            )}
          </div>
          <div className="p-4 bg-white/5 rounded-lg">
            <div className="text-sm text-gray-400 mb-2">Strategy Selection for Backtesting</div>
            <div className="text-xs text-gray-500 space-y-1">
              <div>Strategies are selected based on priority:</div>
              <div className="ml-4">
                <div>1. <strong>Highest Priority:</strong> Never backtested (last_backtest_at == None)</div>
                <div>2. <strong>Second Priority:</strong> Old backtests (older than 7 days)</div>
                <div>3. <strong>Third Priority:</strong> Experiment status (newly created)</div>
                <div>4. <strong>Lower Priority:</strong> Already evaluated strategies</div>
              </div>
              <div className="mt-2 text-gray-400">
                The evolution worker processes strategies in this order, limited by rate limits to prevent API abuse.
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Send Message to All Users */}
      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20 mt-6">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <MessageSquare className="w-5 h-5" />
            Send Message to All Users
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Button
            onClick={() => setShowMessageModal(true)}
            className="bg-purple-600 hover:bg-purple-700"
          >
            <MessageSquare className="w-4 h-4 mr-2" />
            Send Message
          </Button>
        </CardContent>
      </Card>

      {/* Send Message Modal */}
      {showMessageModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="bg-black/90 backdrop-blur-xl border-blue-500/20 w-full max-w-md">
            <CardHeader>
              <CardTitle className="text-white">Send Message to All Users</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-gray-300">Title</Label>
                <Input
                  value={messageTitle}
                  onChange={(e) => setMessageTitle(e.target.value)}
                  className="mt-1 bg-white/5 border-blue-500/20 text-white"
                  placeholder="Message title"
                />
              </div>
              <div>
                <Label className="text-gray-300">Message</Label>
                <textarea
                  value={messageBody}
                  onChange={(e) => setMessageBody(e.target.value)}
                  className="mt-1 w-full bg-white/5 border border-blue-500/20 text-white rounded-md p-2 min-h-[100px]"
                  placeholder="Message content"
                />
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={sendMessageToAllUsers}
                  disabled={sendingMessage}
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  {sendingMessage ? 'Sending...' : 'Send Message'}
                </Button>
                <Button
                  onClick={() => {
                    setShowMessageModal(false);
                    setMessageTitle('');
                    setMessageBody('');
                  }}
                  variant="outline"
                  className="bg-white/5 border-blue-500/20 text-white"
                >
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
