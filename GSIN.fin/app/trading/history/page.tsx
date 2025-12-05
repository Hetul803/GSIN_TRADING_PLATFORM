'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { TrendingUp, TrendingDown, Filter, Search, Plus, X, AlertCircle } from 'lucide-react';
import { format } from 'date-fns';
import { useStore } from '@/lib/store';
import { toast } from 'sonner';

interface Trade {
  id: string;
  symbol: string;
  asset_type: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  entry_price: number;
  exit_price: number | null;
  status: 'OPEN' | 'CLOSED';
  mode: 'PAPER' | 'REAL';
  source: 'MANUAL' | 'BRAIN';
  opened_at: string;
  closed_at: string | null;
  realized_pnl: number | null;
  strategy_id: string | null;
  group_id: string | null;
  created_at: string;
}

interface TradeSummary {
  total_trades: number;
  open_trades: number;
  closed_trades: number;
  win_rate: number; // As decimal (0.67 = 67%)
  total_realized_pnl: number;
  avg_realized_pnl: number;
}

export default function TradeHistoryPage() {
  const user = useStore((state) => state.user);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [summary, setSummary] = useState<TradeSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [symbolFilter, setSymbolFilter] = useState<string>('');
  
  // Create trade dialog
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newTrade, setNewTrade] = useState({
    symbol: '',
    asset_type: 'STOCK',
    side: 'BUY',
    quantity: '',
    entry_price: '',
  });
  
  // Close trade dialog
  const [closeDialogOpen, setCloseDialogOpen] = useState(false);
  const [closing, setClosing] = useState(false);
  const [selectedTrade, setSelectedTrade] = useState<Trade | null>(null);
  const [exitPrice, setExitPrice] = useState('');

  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  useEffect(() => {
    if (user?.id) {
      loadData();
    }
  }, [user?.id, statusFilter]);

  async function loadData() {
    if (!user?.id) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    
    try {
      // Fetch trades
      const tradesUrl = `${BACKEND_URL}/trades?status=${statusFilter}&mode=PAPER`;
      const tradesResponse = await fetch(tradesUrl, {
        headers: {
          'X-User-Id': user.id,
        },
      });

      if (!tradesResponse.ok) {
        throw new Error('Failed to fetch trades');
      }

      const tradesData = await tradesResponse.json();
      setTrades(tradesData);

      // Fetch summary
      const summaryResponse = await fetch(`${BACKEND_URL}/trades/summary?mode=PAPER`, {
        headers: {
          'X-User-Id': user.id,
        },
      });

      if (summaryResponse.ok) {
        const summaryData = await summaryResponse.json();
        setSummary(summaryData);
      }
    } catch (err: any) {
      console.error('Error loading trades:', err);
      setError(err.message || 'Failed to load trade history');
      setTrades([]);
    } finally {
      setLoading(false);
    }
  }

  const handleCreateTrade = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!user?.id) {
      toast.error('Please log in to create a trade');
      return;
    }

    if (!newTrade.symbol.trim() || !newTrade.quantity || !newTrade.entry_price) {
      toast.error('Please fill in all required fields');
      return;
    }

    const quantity = parseFloat(newTrade.quantity);
    const entryPrice = parseFloat(newTrade.entry_price);

    if (quantity <= 0 || entryPrice <= 0) {
      toast.error('Quantity and entry price must be positive');
      return;
    }

    setCreating(true);
    try {
      const response = await fetch(`${BACKEND_URL}/trades`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': user.id,
        },
        body: JSON.stringify({
          symbol: newTrade.symbol.trim().toUpperCase(),
          asset_type: newTrade.asset_type,
          side: newTrade.side,
          quantity: quantity,
          entry_price: entryPrice,
          mode: 'PAPER',
          source: 'MANUAL',
        }),
      });

      if (response.ok) {
        toast.success('Trade created successfully!');
        setNewTrade({ symbol: '', asset_type: 'STOCK', side: 'BUY', quantity: '', entry_price: '' });
        setCreateDialogOpen(false);
        await loadData();
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create trade');
      }
    } catch (error: any) {
      console.error('Error creating trade:', error);
      toast.error(error.message || 'Failed to create trade');
    } finally {
      setCreating(false);
    }
  };

  const handleCloseTrade = async (trade: Trade) => {
    setSelectedTrade(trade);
    setExitPrice('');
    setCloseDialogOpen(true);
  };

  const confirmCloseTrade = async () => {
    if (!selectedTrade || !exitPrice) {
      toast.error('Please enter an exit price');
      return;
    }

    const exitPriceNum = parseFloat(exitPrice);
    if (exitPriceNum <= 0) {
      toast.error('Exit price must be positive');
      return;
    }

    if (!user?.id) {
      toast.error('Please log in');
      return;
    }

    setClosing(true);
    try {
      const response = await fetch(`${BACKEND_URL}/trades/${selectedTrade.id}/close`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': user.id,
        },
        body: JSON.stringify({
          exit_price: exitPriceNum,
        }),
      });

      if (response.ok) {
        toast.success('Trade closed successfully!');
        setCloseDialogOpen(false);
        setSelectedTrade(null);
        setExitPrice('');
        await loadData();
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to close trade');
      }
    } catch (error: any) {
      console.error('Error closing trade:', error);
      toast.error(error.message || 'Failed to close trade');
    } finally {
      setClosing(false);
    }
  };

  const filteredTrades = trades.filter((trade) => {
    if (symbolFilter) {
      return trade.symbol.toLowerCase().includes(symbolFilter.toLowerCase());
    }
    return true;
  });

  const formatCurrency = (value: number | null) => {
    if (value === null) return 'N/A';
    const formatted = Math.abs(value).toFixed(2);
    return value >= 0 ? `+$${formatted}` : `-$${formatted}`;
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white text-lg">Loading trade history...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Trade History</h1>
          <p className="text-gray-400">
            View your past trades, P&L, and which strategies or Brain signals were used.
          </p>
        </div>
        <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700">
              <Plus className="w-4 h-4" />
              New Trade
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-black/90 border-blue-500/20">
            <DialogHeader>
              <DialogTitle className="text-white">Create New PAPER Trade</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleCreateTrade} className="space-y-4 pt-4">
              <div>
                <Label className="text-gray-300">Symbol *</Label>
                <Input
                  value={newTrade.symbol}
                  onChange={(e) => setNewTrade({ ...newTrade, symbol: e.target.value.toUpperCase() })}
                  placeholder="AAPL"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  required
                />
              </div>
              <div>
                <Label className="text-gray-300">Asset Type</Label>
                <Select
                  value={newTrade.asset_type}
                  onValueChange={(value) => setNewTrade({ ...newTrade, asset_type: value })}
                >
                  <SelectTrigger className="mt-2 bg-white/5 border-blue-500/20 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="STOCK">Stock</SelectItem>
                    <SelectItem value="CRYPTO">Crypto</SelectItem>
                    <SelectItem value="FOREX">Forex</SelectItem>
                    <SelectItem value="OTHER">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-gray-300">Side *</Label>
                <Select
                  value={newTrade.side}
                  onValueChange={(value: 'BUY' | 'SELL') => setNewTrade({ ...newTrade, side: value })}
                >
                  <SelectTrigger className="mt-2 bg-white/5 border-blue-500/20 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="BUY">Buy</SelectItem>
                    <SelectItem value="SELL">Sell</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-gray-300">Quantity *</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={newTrade.quantity}
                  onChange={(e) => setNewTrade({ ...newTrade, quantity: e.target.value })}
                  placeholder="10"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  required
                />
              </div>
              <div>
                <Label className="text-gray-300">Entry Price *</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={newTrade.entry_price}
                  onChange={(e) => setNewTrade({ ...newTrade, entry_price: e.target.value })}
                  placeholder="150.00"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  required
                />
              </div>
              <Button
                type="submit"
                disabled={creating}
                className="w-full bg-gradient-to-r from-blue-600 to-purple-600"
              >
                {creating ? 'Creating...' : 'Create Trade'}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {error && (
        <Card className="bg-red-500/10 border-red-500/20">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-red-400">
              <AlertCircle className="w-5 h-5" />
              <p>{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-400">Total Realized P&L</CardTitle>
            </CardHeader>
            <CardContent>
              <div
                className={`text-2xl font-bold ${
                  summary.total_realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {formatCurrency(summary.total_realized_pnl)}
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Avg: {formatCurrency(summary.avg_realized_pnl)} per trade
              </p>
            </CardContent>
          </Card>

          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-400">Win Rate</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-white">
                {(summary.win_rate * 100).toFixed(1)}%
              </div>
              <p className="text-xs text-gray-400 mt-1">
                {summary.closed_trades} closed trades
              </p>
            </CardContent>
          </Card>

          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-400">Total Trades</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-white">{summary.total_trades}</div>
              <p className="text-xs text-gray-400 mt-1">
                {summary.open_trades} open / {summary.closed_trades} closed
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardHeader>
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <CardTitle className="text-white">Trade History</CardTitle>
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  placeholder="Search symbol..."
                  value={symbolFilter}
                  onChange={(e) => setSymbolFilter(e.target.value)}
                  className="pl-10 bg-white/5 border-blue-500/20 text-white w-40"
                />
              </div>

              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="bg-white/5 border-blue-500/20 text-white w-32">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">All</SelectItem>
                  <SelectItem value="OPEN">Open</SelectItem>
                  <SelectItem value="CLOSED">Closed</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {filteredTrades.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-400 text-lg mb-2">No trades found</p>
              <p className="text-gray-500 text-sm">
                {trades.length === 0
                  ? 'Start trading to see your trade history here'
                  : 'Try adjusting your filters'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-blue-500/20">
                    <th className="text-left text-sm text-gray-400 pb-3 font-medium">Date</th>
                    <th className="text-left text-sm text-gray-400 pb-3 font-medium">Symbol</th>
                    <th className="text-left text-sm text-gray-400 pb-3 font-medium">Side</th>
                    <th className="text-right text-sm text-gray-400 pb-3 font-medium">Qty</th>
                    <th className="text-right text-sm text-gray-400 pb-3 font-medium">Entry</th>
                    <th className="text-right text-sm text-gray-400 pb-3 font-medium">Exit</th>
                    <th className="text-right text-sm text-gray-400 pb-3 font-medium">P&L</th>
                    <th className="text-left text-sm text-gray-400 pb-3 font-medium">Status</th>
                    <th className="text-left text-sm text-gray-400 pb-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTrades.map((trade) => (
                    <tr key={trade.id} className="border-b border-blue-500/10 hover:bg-white/5">
                      <td className="py-3 text-sm text-gray-300">
                        {format(new Date(trade.opened_at), 'MMM dd, HH:mm')}
                      </td>
                      <td className="py-3 text-sm font-medium text-white">{trade.symbol}</td>
                      <td className="py-3">
                        <Badge
                          className={
                            trade.side === 'BUY'
                              ? 'bg-green-500/20 text-green-400 border-green-500/30'
                              : 'bg-red-500/20 text-red-400 border-red-500/30'
                          }
                        >
                          {trade.side === 'BUY' ? (
                            <TrendingUp className="w-3 h-3 mr-1" />
                          ) : (
                            <TrendingDown className="w-3 h-3 mr-1" />
                          )}
                          {trade.side}
                        </Badge>
                      </td>
                      <td className="py-3 text-sm text-right text-white">{trade.quantity}</td>
                      <td className="py-3 text-sm text-right text-gray-300">
                        ${trade.entry_price.toFixed(2)}
                      </td>
                      <td className="py-3 text-sm text-right text-gray-300">
                        {trade.exit_price ? `$${trade.exit_price.toFixed(2)}` : '-'}
                      </td>
                      <td
                        className={`py-3 text-sm text-right font-medium ${
                          trade.realized_pnl === null
                            ? 'text-gray-500'
                            : trade.realized_pnl >= 0
                            ? 'text-green-400'
                            : 'text-red-400'
                        }`}
                      >
                        {formatCurrency(trade.realized_pnl)}
                      </td>
                      <td className="py-3">
                        <Badge
                          className={
                            trade.status === 'OPEN'
                              ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                              : 'bg-gray-500/20 text-gray-400 border-gray-500/30'
                          }
                        >
                          {trade.status}
                        </Badge>
                      </td>
                      <td className="py-3">
                        {trade.status === 'OPEN' && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleCloseTrade(trade)}
                            className="bg-red-500/10 border-red-500/20 text-red-400 hover:bg-red-500/20"
                          >
                            Close
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Close Trade Dialog */}
      <Dialog open={closeDialogOpen} onOpenChange={setCloseDialogOpen}>
        <DialogContent className="bg-black/90 border-blue-500/20">
          <DialogHeader>
            <DialogTitle className="text-white">Close Trade</DialogTitle>
          </DialogHeader>
          {selectedTrade && (
            <div className="space-y-4 pt-4">
              <div className="p-4 bg-white/5 rounded-lg">
                <p className="text-sm text-gray-400">Symbol</p>
                <p className="text-white font-medium">{selectedTrade.symbol}</p>
                <p className="text-sm text-gray-400 mt-2">Side</p>
                <p className="text-white font-medium">{selectedTrade.side}</p>
                <p className="text-sm text-gray-400 mt-2">Quantity</p>
                <p className="text-white font-medium">{selectedTrade.quantity}</p>
                <p className="text-sm text-gray-400 mt-2">Entry Price</p>
                <p className="text-white font-medium">${selectedTrade.entry_price.toFixed(2)}</p>
              </div>
              <div>
                <Label className="text-gray-300">Exit Price *</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={exitPrice}
                  onChange={(e) => setExitPrice(e.target.value)}
                  placeholder="150.00"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  required
                />
              </div>
              <div className="flex gap-3">
                <Button
                  onClick={confirmCloseTrade}
                  disabled={closing || !exitPrice}
                  className="flex-1 bg-red-600 hover:bg-red-700"
                >
                  {closing ? 'Closing...' : 'Close Trade'}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setCloseDialogOpen(false);
                    setSelectedTrade(null);
                    setExitPrice('');
                  }}
                  className="flex-1 border-blue-500/20 text-white"
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
