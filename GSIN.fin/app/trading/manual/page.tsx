'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { mockTrades } from '@/lib/mock-data';
import { Search, TrendingUp, TrendingDown, AlertTriangle, Shield } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { useTradingMode } from '@/lib/store';

export default function ManualTradingPage() {
  const { tradingMode } = useTradingMode();
  const [symbol, setSymbol] = useState('');
  const [quantity, setQuantity] = useState('');
  const [side, setSide] = useState<'buy' | 'sell'>('buy');
  const [limitPrice, setLimitPrice] = useState('');

  const handleTrade = async (orderType: 'market' | 'limit') => {
    if (!symbol || !quantity) {
      toast.error('Please enter both symbol and quantity');
      return;
    }

    try {
      const response = await fetch('/api/trading/place-order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          side,
          quantity: parseInt(quantity),
          orderType,
          limitPrice: orderType === 'limit' ? parseFloat(limitPrice) : undefined,
          mode: tradingMode,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        toast.success(`${side.toUpperCase()} order for ${quantity} ${symbol} placed successfully in ${tradingMode.toUpperCase()} mode`);
        setSymbol('');
        setQuantity('');
        setLimitPrice('');
      } else {
        toast.error(data.error || 'Failed to place order');
      }
    } catch (error) {
      console.error('Error placing order:', error);
      toast.error('Failed to place order');
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Manual Trading</h1>
          <p className="text-gray-400">Execute trades with full control</p>
        </div>
        <Badge
          className={
            tradingMode === 'paper'
              ? 'bg-blue-500/20 text-blue-400 border-blue-500/30 px-4 py-2 text-sm'
              : 'bg-red-500/20 text-red-400 border-red-500/30 px-4 py-2 text-sm'
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
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white">Order Ticket</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-gray-300">Symbol</Label>
                <div className="relative mt-2">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                    placeholder="AAPL"
                    className="pl-10 bg-white/5 border-blue-500/20 text-white"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Button
                  onClick={() => setSide('buy')}
                  className={side === 'buy' ? 'bg-green-600 hover:bg-green-700' : 'bg-white/5'}
                >
                  <TrendingUp className="w-4 h-4 mr-2" />
                  Buy
                </Button>
                <Button
                  onClick={() => setSide('sell')}
                  className={side === 'sell' ? 'bg-red-600 hover:bg-red-700' : 'bg-white/5'}
                >
                  <TrendingDown className="w-4 h-4 mr-2" />
                  Sell
                </Button>
              </div>

              <Tabs defaultValue="market">
                <TabsList className="grid w-full grid-cols-2 bg-black/60">
                  <TabsTrigger value="market">Market</TabsTrigger>
                  <TabsTrigger value="limit">Limit</TabsTrigger>
                </TabsList>
                <TabsContent value="market" className="space-y-4">
                  <div>
                    <Label className="text-gray-300">Quantity</Label>
                    <Input
                      type="number"
                      value={quantity}
                      onChange={(e) => setQuantity(e.target.value)}
                      placeholder="100"
                      className="mt-2 bg-white/5 border-blue-500/20 text-white"
                    />
                  </div>
                  <Button onClick={() => handleTrade('market')} className="w-full bg-blue-600 hover:bg-blue-700">
                    Place Market Order
                  </Button>
                </TabsContent>
                <TabsContent value="limit" className="space-y-4">
                  <div>
                    <Label className="text-gray-300">Quantity</Label>
                    <Input
                      type="number"
                      value={quantity}
                      onChange={(e) => setQuantity(e.target.value)}
                      placeholder="100"
                      className="mt-2 bg-white/5 border-blue-500/20 text-white"
                    />
                  </div>
                  <div>
                    <Label className="text-gray-300">Limit Price</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={limitPrice}
                      onChange={(e) => setLimitPrice(e.target.value)}
                      placeholder="178.50"
                      className="mt-2 bg-white/5 border-blue-500/20 text-white"
                    />
                  </div>
                  <Button onClick={() => handleTrade('limit')} className="w-full bg-blue-600 hover:bg-blue-700">
                    Place Limit Order
                  </Button>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>

          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white">Open Positions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-blue-500/20">
                      <th className="text-left text-sm text-gray-400 pb-2">Symbol</th>
                      <th className="text-left text-sm text-gray-400 pb-2">Side</th>
                      <th className="text-left text-sm text-gray-400 pb-2">Qty</th>
                      <th className="text-left text-sm text-gray-400 pb-2">Avg Price</th>
                      <th className="text-left text-sm text-gray-400 pb-2">P&L</th>
                      <th className="text-left text-sm text-gray-400 pb-2">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mockTrades.filter(t => t.status === 'open').map(trade => (
                      <tr key={trade.id} className="border-b border-blue-500/10">
                        <td className="py-3 text-white font-medium">{trade.symbol}</td>
                        <td className="py-3">
                          <span className={trade.side === 'buy' ? 'text-green-400' : 'text-red-400'}>
                            {trade.side.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-3 text-white">{trade.quantity}</td>
                        <td className="py-3 text-white">${trade.price}</td>
                        <td className="py-3 text-gray-400">$0.00</td>
                        <td className="py-3">
                          <Button size="sm" variant="outline" className="bg-white/5 border-blue-500/20 text-white">
                            Close
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white">Risk Caps</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-gray-300">Max $ Per Trade</Label>
                <Input
                  type="number"
                  defaultValue="5000"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                />
              </div>
              <div>
                <Label className="text-gray-300">Max Trades Per Day</Label>
                <Input
                  type="number"
                  defaultValue="10"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                />
              </div>
              <div>
                <Label className="text-gray-300">Daily Loss Limit</Label>
                <Input
                  type="number"
                  defaultValue="2000"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                />
              </div>
              <Button className="w-full bg-blue-600 hover:bg-blue-700">
                Update Limits
              </Button>
            </CardContent>
          </Card>

          <Card className="bg-black/60 backdrop-blur-xl border-red-500/20">
            <CardContent className="p-6">
              <div className="flex items-start gap-3 mb-4">
                <AlertTriangle className="w-6 h-6 text-red-400 mt-1" />
                <div>
                  <h3 className="text-lg font-semibold text-white mb-2">Emergency Stop</h3>
                  <p className="text-sm text-gray-400">
                    Immediately close all positions and pause all signals
                  </p>
                </div>
              </div>
              <Button className="w-full bg-red-600 hover:bg-red-700">
                PAUSE ALL SIGNALS
              </Button>
            </CardContent>
          </Card>
        </div>
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
