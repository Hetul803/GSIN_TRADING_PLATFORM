'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useStore } from '@/lib/store';
import { DollarSign, TrendingUp, Calendar, Filter, RefreshCw } from 'lucide-react';
import { apiRequest } from '@/lib/api-client';
import { format } from 'date-fns';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';

interface RoyaltyEntry {
  id: string;
  strategy_id: string | null;
  trade_id: string;
  royalty_amount: number;
  platform_fee: number;
  net_amount: number;
  trade_profit?: number;  // Optional field
  created_at: string;
  strategy_name?: string;
  symbol?: string;
}

interface RoyaltySummary {
  total_royalties: number;
  total_platform_fees: number;
  total_net_paid: number;
  count: number;
}

export default function RoyaltiesPage() {
  const user = useStore((state) => state.user);
  const [royalties, setRoyalties] = useState<RoyaltyEntry[]>([]);
  const [summary, setSummary] = useState<RoyaltySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterStrategy, setFilterStrategy] = useState<string>('all');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [strategies, setStrategies] = useState<Array<{ id: string; name: string }>>([]);

  useEffect(() => {
    if (user?.id) {
      loadRoyalties();
      loadStrategies();
    }
  }, [user?.id]);

  async function loadStrategies() {
    try {
      const data = await apiRequest<Array<{ id: string; name: string }>>('/api/strategies');
      setStrategies(data || []);
    } catch (error) {
      console.error('Error loading strategies:', error);
    }
  }

  async function loadRoyalties() {
    if (!user?.id) return;

    setLoading(true);
    try {
      const [royaltiesData, summaryData] = await Promise.all([
        apiRequest<{ royalties: RoyaltyEntry[] }>('/api/royalties/me'),
        apiRequest<RoyaltySummary>('/api/royalties/summary'),
      ]);

      setRoyalties(royaltiesData.royalties || []);
      setSummary(summaryData);
    } catch (error: any) {
      console.error('Error loading royalties:', error);
      toast.error(error.message || 'Failed to load royalties');
    } finally {
      setLoading(false);
    }
  }

  const filteredRoyalties = royalties.filter((royalty) => {
    if (filterStrategy !== 'all' && royalty.strategy_id !== filterStrategy) {
      return false;
    }
    if (dateFrom && new Date(royalty.created_at) < new Date(dateFrom)) {
      return false;
    }
    if (dateTo && new Date(royalty.created_at) > new Date(dateTo)) {
      return false;
    }
    return true;
  });

  // Prepare chart data (royalties over time)
  const chartData = filteredRoyalties
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
    .reduce((acc, royalty, index) => {
      const date = format(new Date(royalty.created_at), 'MMM dd');
      const cumulative = index === 0 ? royalty.net_amount : acc[acc.length - 1].value + royalty.net_amount;
      acc.push({ date, value: cumulative });
      return acc;
    }, [] as Array<{ date: string; value: number }>);

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <Skeleton className="h-12 w-64" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <Skeleton className="h-96" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Royalties</h1>
        <p className="text-gray-400">Earnings from strategies used by other traders</p>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="bg-black/60 backdrop-blur-xl border-green-500/20">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-gray-400">Total Royalties</CardTitle>
              <DollarSign className="w-4 h-4 text-green-400" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-green-400">
                ${(summary.total_royalties || 0).toFixed(2)}
              </div>
              <p className="text-xs text-gray-500 mt-1">Before platform fees</p>
            </CardContent>
          </Card>

          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-gray-400">Net Paid</CardTitle>
              <TrendingUp className="w-4 h-4 text-blue-400" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-blue-400">
                ${(summary.total_net_paid || 0).toFixed(2)}
              </div>
              <p className="text-xs text-gray-500 mt-1">After platform fees</p>
            </CardContent>
          </Card>

          <Card className="bg-black/60 backdrop-blur-xl border-purple-500/20">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-gray-400">Total Transactions</CardTitle>
              <Calendar className="w-4 h-4 text-purple-400" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-purple-400">{summary.count}</div>
              <p className="text-xs text-gray-500 mt-1">Profitable trades</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Filter className="w-5 h-5" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <Label className="text-gray-300 text-sm">Strategy</Label>
              <Select value={filterStrategy} onValueChange={setFilterStrategy}>
                <SelectTrigger className="mt-2 bg-white/5 border-blue-500/20 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Strategies</SelectItem>
                  {strategies.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-gray-300 text-sm">From Date</Label>
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
            <div>
              <Label className="text-gray-300 text-sm">To Date</Label>
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
            <div className="flex items-end">
              <Button
                variant="outline"
                onClick={() => {
                  setFilterStrategy('all');
                  setDateFrom('');
                  setDateTo('');
                }}
                className="w-full border-blue-500/20 text-white"
              >
                Clear Filters
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Chart */}
      {chartData.length > 0 && (
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white">Royalties Over Time</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="date" stroke="#64748b" />
                <YAxis stroke="#64748b" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    border: '1px solid #1e293b',
                    borderRadius: '8px',
                    color: '#fff',
                  }}
                  formatter={(value: any) => [`$${value.toFixed(2)}`, 'Cumulative Royalties']}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Royalties List */}
      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardHeader>
          <CardTitle className="text-white">Royalty History</CardTitle>
        </CardHeader>
        <CardContent>
          {filteredRoyalties.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <DollarSign className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No royalties yet</p>
              <p className="text-sm mt-2">Royalties will appear here when others profit from your strategies</p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredRoyalties.map((royalty) => (
                <div
                  key={royalty.id}
                  className="p-4 bg-white/5 border border-blue-500/20 rounded-lg hover:border-blue-500/40 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge className="bg-green-500/20 text-green-400">
                          ${royalty.net_amount.toFixed(2)}
                        </Badge>
                        <span className="text-xs text-gray-400">
                          {format(new Date(royalty.created_at), 'MMM dd, yyyy HH:mm')}
                        </span>
                      </div>
                      <div className="text-sm text-gray-300 space-y-1">
                        {royalty.trade_profit !== undefined && (
                          <p>Trade Profit: <span className="text-green-400">${royalty.trade_profit.toFixed(2)}</span></p>
                        )}
                        <p>Royalty: ${royalty.royalty_amount.toFixed(2)} • Platform Fee: ${royalty.platform_fee.toFixed(2)}</p>
                        {royalty.strategy_id && (
                          <p className="text-xs text-gray-500">
                            Strategy: {strategies.find(s => s.id === royalty.strategy_id)?.name || 'Unknown'}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

