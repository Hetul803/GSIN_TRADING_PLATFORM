'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Plus, X, Lock, ArrowUp, Save, AlertCircle } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { useStore } from '@/lib/store';
import { canUploadStrategies } from '@/lib/subscription-utils';
import Link from 'next/link';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface EntryRule {
  indicator: string;
  operator: string;
  value: string | number | [number, number];
  lookback?: number;
}

interface ExitRule {
  stop_loss_percent: number;
  take_profit_percent: number;
  trailing_stop_percent?: number;
}

export default function UploadStrategyPage() {
  const router = useRouter();
  const user = useStore((state) => state.user);
  const [subscriptionInfo, setSubscriptionInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  
  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [assetType, setAssetType] = useState<string>('STOCK');
  const [symbols, setSymbols] = useState<string[]>(['']);
  const [timeframe, setTimeframe] = useState<string>('1d');
  const [direction, setDirection] = useState<string>('both');
  const [entryRules, setEntryRules] = useState<EntryRule[]>([
    { indicator: 'rsi', operator: '<', value: 30 }
  ]);
  const [exitRules, setExitRules] = useState<ExitRule>({
    stop_loss_percent: 2.0,
    take_profit_percent: 5.0
  });
  const [maxRiskPerTrade, setMaxRiskPerTrade] = useState<number>(2.0);
  const [positionSizePercent, setPositionSizePercent] = useState<number | undefined>(undefined);
  const [intendedRegime, setIntendedRegime] = useState<string>('any');
  const [tags, setTags] = useState<string[]>([]);
  const [maxConcurrentPositions, setMaxConcurrentPositions] = useState<number | undefined>(undefined);
  const [cooldownBars, setCooldownBars] = useState<number | undefined>(undefined);

  useEffect(() => {
    if (!user?.id) {
      router.push('/login');
      return;
    }
    loadSubscriptionInfo();
  }, [user?.id, router]);

  async function loadSubscriptionInfo() {
    if (!user?.id) return;
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/subscriptions/me`, {
        headers: { 'X-User-Id': user.id },
      });
      if (response.ok) {
        const data = await response.json();
        setSubscriptionInfo(data);
      }
    } catch (error) {
      console.error('Error loading subscription:', error);
    } finally {
      setLoading(false);
    }
  }

  const planCode = subscriptionInfo?.planCode || user?.subscriptionTier?.toUpperCase() || 'USER';
  const canUpload = canUploadStrategies(planCode);
  const isDisabled = !canUpload;

  const addSymbol = () => {
    setSymbols([...symbols, '']);
  };

  const removeSymbol = (index: number) => {
    setSymbols(symbols.filter((_, i) => i !== index));
  };

  const updateSymbol = (index: number, value: string) => {
    const newSymbols = [...symbols];
    newSymbols[index] = value.toUpperCase();
    setSymbols(newSymbols);
  };

  const addEntryRule = () => {
    setEntryRules([...entryRules, { indicator: 'rsi', operator: '>', value: 50 }]);
  };

  const removeEntryRule = (index: number) => {
    setEntryRules(entryRules.filter((_, i) => i !== index));
  };

  const updateEntryRule = (index: number, field: keyof EntryRule, value: any) => {
    const newRules = [...entryRules];
    newRules[index] = { ...newRules[index], [field]: value };
    setEntryRules(newRules);
  };

  const addTag = (tag: string) => {
    if (tag && !tags.includes(tag)) {
      setTags([...tags, tag]);
    }
  };

  const removeTag = (tag: string) => {
    setTags(tags.filter(t => t !== tag));
  };

  const validateForm = (): string | null => {
    if (!name.trim()) return 'Strategy name is required';
    if (symbols.filter(s => s.trim()).length === 0) return 'At least one symbol is required';
    if (entryRules.length === 0) return 'At least one entry rule is required';
    if (!exitRules.stop_loss_percent || exitRules.stop_loss_percent <= 0) return 'Stop loss must be greater than 0';
    if (!exitRules.take_profit_percent || exitRules.take_profit_percent <= 0) return 'Take profit must be greater than 0';
    if (!maxRiskPerTrade || maxRiskPerTrade <= 0) return 'Max risk per trade must be greater than 0';
    return null;
  };

  const handleSubmit = async () => {
    const error = validateForm();
    if (error) {
      toast.error(error);
      return;
    }

    setSubmitting(true);
    try {
      // Build builder request
      const builderRequest = {
        name: name.trim(),
        description: description.trim() || undefined,
        asset_type: assetType,
        symbols: symbols.filter(s => s.trim()),
        timeframe,
        direction,
        entry_rules: entryRules.map(rule => ({
          indicator: rule.indicator,
          operator: rule.operator,
          value: rule.value,
          lookback: rule.lookback,
        })),
        exit_rules: {
          stop_loss_percent: exitRules.stop_loss_percent,
          take_profit_percent: exitRules.take_profit_percent,
          trailing_stop_percent: exitRules.trailing_stop_percent,
        },
        position_sizing: {
          max_risk_per_trade_percent: maxRiskPerTrade,
          position_size_percent: positionSizePercent,
        },
        intended_regime: intendedRegime,
        tags: tags.length > 0 ? tags : undefined,
        max_concurrent_positions: maxConcurrentPositions,
        cooldown_bars: cooldownBars,
      };

      const response = await fetch(`${BACKEND_URL}/api/strategies`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': user.id,
        },
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || undefined,
          asset_type: assetType,
          builder_request: builderRequest,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        toast.success('Strategy submitted successfully! It is now under review.');
        router.push('/strategies');
      } else {
        const error = await response.json().catch(() => ({ detail: 'Failed to submit strategy' }));
        toast.error(error.detail || 'Failed to submit strategy');
      }
    } catch (error: any) {
      console.error('Failed to submit strategy:', error);
      toast.error('Failed to submit strategy: ' + (error.message || 'Network error'));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white text-lg">Loading...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6" style={{ opacity: isDisabled ? 0.5 : 1, pointerEvents: isDisabled ? 'none' : 'auto' }}>
      {/* Navigation */}
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <Link href="/dashboard" className="hover:text-white transition-colors">Dashboard</Link>
        <span>/</span>
        <Link href="/strategies" className="hover:text-white transition-colors">Strategy Marketplace</Link>
        <span>/</span>
        <span className="text-white">Create Strategy</span>
      </div>

      <div>
        <h1 className="text-3xl font-bold text-white">Create Strategy</h1>
        <p className="text-gray-400">Build your trading strategy using our no-code builder</p>
      </div>

      {isDisabled && (
        <Card className="bg-yellow-500/10 border-yellow-500/30">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <Lock className="w-8 h-8 text-yellow-400" />
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-white mb-1">Upgrade Required</h3>
                <p className="text-gray-300 mb-3">
                  Strategy upload is only available for Pro and Creator accounts. Upgrade your plan to upload and share strategies.
                </p>
                <Link href="/subscriptions">
                  <Button className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 gap-2">
                    <ArrowUp className="w-4 h-4" />
                    Upgrade Plan
                  </Button>
                </Link>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Basic Information */}
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white">Basic Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-gray-300">Strategy Name *</Label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="My Awesome Strategy"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                />
              </div>

              <div>
                <Label className="text-gray-300">Description</Label>
                <Textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe your strategy, its logic, and what makes it unique..."
                  rows={4}
                  className="mt-2 bg-white/5 border-blue-500/20 text-white resize-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-gray-300">Asset Type *</Label>
                  <Select value={assetType} onValueChange={setAssetType}>
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
                  <Label className="text-gray-300">Timeframe *</Label>
                  <Select value={timeframe} onValueChange={setTimeframe}>
                    <SelectTrigger className="mt-2 bg-white/5 border-blue-500/20 text-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1m">1 Minute</SelectItem>
                      <SelectItem value="5m">5 Minutes</SelectItem>
                      <SelectItem value="15m">15 Minutes</SelectItem>
                      <SelectItem value="1h">1 Hour</SelectItem>
                      <SelectItem value="4h">4 Hours</SelectItem>
                      <SelectItem value="1d">1 Day</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div>
                <Label className="text-gray-300">Trading Direction *</Label>
                <Select value={direction} onValueChange={setDirection}>
                  <SelectTrigger className="mt-2 bg-white/5 border-blue-500/20 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="long">Long Only</SelectItem>
                    <SelectItem value="short">Short Only</SelectItem>
                    <SelectItem value="both">Both</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Symbols */}
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white">Symbols *</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {symbols.map((symbol, index) => (
                <div key={index} className="flex gap-2">
                  <Input
                    value={symbol}
                    onChange={(e) => updateSymbol(index, e.target.value)}
                    placeholder="AAPL"
                    className="bg-white/5 border-blue-500/20 text-white"
                  />
                  {symbols.length > 1 && (
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => removeSymbol(index)}
                      className="bg-white/5 border-red-500/20 text-red-400 hover:bg-red-500/10"
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              ))}
              <Button
                variant="outline"
                onClick={addSymbol}
                className="w-full bg-white/5 border-blue-500/20 text-white hover:bg-blue-500/10"
              >
                <Plus className="w-4 h-4 mr-2" />
                Add Symbol
              </Button>
            </CardContent>
          </Card>

          {/* Entry Rules */}
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white">Entry Rules *</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {entryRules.map((rule, index) => (
                <div key={index} className="p-4 bg-white/5 rounded-lg space-y-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-400">Rule {index + 1}</span>
                    {entryRules.length > 1 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeEntryRule(index)}
                        className="text-red-400 hover:text-red-300"
                      >
                        <X className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                  <div className="grid grid-cols-4 gap-2">
                    <div>
                      <Label className="text-xs text-gray-400">Indicator</Label>
                      <Select
                        value={rule.indicator}
                        onValueChange={(v) => updateEntryRule(index, 'indicator', v)}
                      >
                        <SelectTrigger className="bg-white/5 border-blue-500/20 text-white text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="rsi">RSI</SelectItem>
                          <SelectItem value="sma">SMA</SelectItem>
                          <SelectItem value="ema">EMA</SelectItem>
                          <SelectItem value="macd">MACD</SelectItem>
                          <SelectItem value="bollinger">Bollinger Bands</SelectItem>
                          <SelectItem value="stochastic">Stochastic</SelectItem>
                          <SelectItem value="adx">ADX</SelectItem>
                          <SelectItem value="atr">ATR</SelectItem>
                          <SelectItem value="volume">Volume</SelectItem>
                          <SelectItem value="price">Price</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-xs text-gray-400">Operator</Label>
                      <Select
                        value={rule.operator}
                        onValueChange={(v) => updateEntryRule(index, 'operator', v)}
                      >
                        <SelectTrigger className="bg-white/5 border-blue-500/20 text-white text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value=">">&gt;</SelectItem>
                          <SelectItem value="<">&lt;</SelectItem>
                          <SelectItem value="==">==</SelectItem>
                          <SelectItem value="crosses_above">Crosses Above</SelectItem>
                          <SelectItem value="crosses_below">Crosses Below</SelectItem>
                          <SelectItem value="between">Between</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-xs text-gray-400">Value</Label>
                      <Input
                        type="number"
                        value={typeof rule.value === 'number' ? rule.value : Array.isArray(rule.value) ? rule.value[0] : rule.value}
                        onChange={(e) => {
                          const num = parseFloat(e.target.value);
                          if (!isNaN(num)) {
                            updateEntryRule(index, 'value', rule.operator === 'between' ? [num, num] : num);
                          }
                        }}
                        className="bg-white/5 border-blue-500/20 text-white text-sm"
                        placeholder="50"
                      />
                    </div>
                    <div>
                      <Label className="text-xs text-gray-400">Lookback</Label>
                      <Input
                        type="number"
                        value={rule.lookback || ''}
                        onChange={(e) => updateEntryRule(index, 'lookback', e.target.value ? parseInt(e.target.value) : undefined)}
                        className="bg-white/5 border-blue-500/20 text-white text-sm"
                        placeholder="14"
                      />
                    </div>
                  </div>
                </div>
              ))}
              <Button
                variant="outline"
                onClick={addEntryRule}
                className="w-full bg-white/5 border-blue-500/20 text-white hover:bg-blue-500/10"
              >
                <Plus className="w-4 h-4 mr-2" />
                Add Entry Rule
              </Button>
            </CardContent>
          </Card>

          {/* Exit Rules */}
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white">Exit Rules *</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-gray-300">Stop Loss % *</Label>
                  <Input
                    type="number"
                    step="0.1"
                    value={exitRules.stop_loss_percent}
                    onChange={(e) => setExitRules({ ...exitRules, stop_loss_percent: parseFloat(e.target.value) || 0 })}
                    className="mt-2 bg-white/5 border-blue-500/20 text-white"
                    placeholder="2.0"
                  />
                </div>
                <div>
                  <Label className="text-gray-300">Take Profit % *</Label>
                  <Input
                    type="number"
                    step="0.1"
                    value={exitRules.take_profit_percent}
                    onChange={(e) => setExitRules({ ...exitRules, take_profit_percent: parseFloat(e.target.value) || 0 })}
                    className="mt-2 bg-white/5 border-blue-500/20 text-white"
                    placeholder="5.0"
                  />
                </div>
              </div>
              <div>
                <Label className="text-gray-300">Trailing Stop % (Optional)</Label>
                <Input
                  type="number"
                  step="0.1"
                  value={exitRules.trailing_stop_percent || ''}
                  onChange={(e) => setExitRules({ ...exitRules, trailing_stop_percent: e.target.value ? parseFloat(e.target.value) : undefined })}
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  placeholder="1.0"
                />
              </div>
            </CardContent>
          </Card>

          {/* Position Sizing */}
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white">Position Sizing *</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-gray-300">Max Risk Per Trade % *</Label>
                <Input
                  type="number"
                  step="0.1"
                  value={maxRiskPerTrade}
                  onChange={(e) => setMaxRiskPerTrade(parseFloat(e.target.value) || 0)}
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  placeholder="2.0"
                />
              </div>
              <div>
                <Label className="text-gray-300">Position Size % (Optional)</Label>
                <Input
                  type="number"
                  step="0.1"
                  value={positionSizePercent || ''}
                  onChange={(e) => setPositionSizePercent(e.target.value ? parseFloat(e.target.value) : undefined)}
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  placeholder="5.0"
                />
              </div>
            </CardContent>
          </Card>

          {/* Optional Settings */}
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white">Optional Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-gray-300">Intended Regime</Label>
                <Select value={intendedRegime} onValueChange={setIntendedRegime}>
                  <SelectTrigger className="mt-2 bg-white/5 border-blue-500/20 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="any">Any</SelectItem>
                    <SelectItem value="bull">Bull Market</SelectItem>
                    <SelectItem value="bear">Bear Market</SelectItem>
                    <SelectItem value="high_vol">High Volatility</SelectItem>
                    <SelectItem value="low_vol">Low Volatility</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-gray-300">Max Concurrent Positions</Label>
                <Input
                  type="number"
                  value={maxConcurrentPositions || ''}
                  onChange={(e) => setMaxConcurrentPositions(e.target.value ? parseInt(e.target.value) : undefined)}
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  placeholder="5"
                />
              </div>
              <div>
                <Label className="text-gray-300">Cooldown Bars</Label>
                <Input
                  type="number"
                  value={cooldownBars || ''}
                  onChange={(e) => setCooldownBars(e.target.value ? parseInt(e.target.value) : undefined)}
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  placeholder="0"
                />
              </div>
              <div>
                <Label className="text-gray-300">Tags (comma-separated)</Label>
                <Input
                  value={tags.join(', ')}
                  onChange={(e) => {
                    const newTags = e.target.value.split(',').map(t => t.trim()).filter(t => t);
                    setTags(newTags);
                  }}
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  placeholder="trend-following, breakout"
                />
              </div>
            </CardContent>
          </Card>

          {/* Submit Button */}
          <div className="flex gap-4">
            <Button
              onClick={handleSubmit}
              disabled={submitting || isDisabled}
              className="flex-1 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 gap-2"
            >
              <Save className="w-4 h-4" />
              {submitting ? 'Submitting...' : 'Submit Strategy'}
            </Button>
            <Link href="/strategies">
              <Button variant="outline" className="bg-white/5 border-blue-500/20 text-white">
                Cancel
              </Button>
            </Link>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white text-sm">Info</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 text-sm text-gray-400">
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-blue-400 mt-0.5" />
                  <p>Your strategy will be reviewed by our system before being made available.</p>
                </div>
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-blue-400 mt-0.5" />
                  <p>You'll receive a notification when your strategy is accepted, rejected, or promoted.</p>
                </div>
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-blue-400 mt-0.5" />
                  <p>Once approved, your strategy will be eligible for royalties based on your subscription plan.</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white text-sm">Royalties & Performance Fees</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 text-sm text-gray-400">
                <p>
                  When users execute trades using your strategy and make a <strong className="text-green-400">profit</strong>, you earn royalties based on your subscription tier.
                </p>
                <ul className="list-disc list-inside space-y-1">
                  <li>Starter: 0% (cannot upload)</li>
                  <li>Pro: 0%</li>
                  <li>Creator: 5%</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
