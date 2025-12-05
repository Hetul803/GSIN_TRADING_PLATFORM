'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Info, CheckCircle2, X, AlertCircle, Loader2, Key, ExternalLink } from 'lucide-react';
import { useTradingMode, useStore } from '@/lib/store';
import { apiRequest } from '@/lib/api-client';
import { toast } from 'sonner';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

export default function BrokerSettingsPage() {
  const user = useStore((state) => state.user);
  const tradingModeHook = useTradingMode();
  const tradingMode = tradingModeHook?.tradingMode || 'paper';

  // PHASE 6: Real broker connection state
  const [brokerStatus, setBrokerStatus] = useState<{
    connected: boolean;
    provider: string | null;
    verified: boolean;
    account_type: string | null;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [showManualDialog, setShowManualDialog] = useState(false);
  
  // Manual API key form
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [baseUrl, setBaseUrl] = useState('https://paper-api.alpaca.markets/v2');

  useEffect(() => {
    if (user?.id) {
      loadBrokerStatus();
    }
  }, [user?.id]);

  async function loadBrokerStatus() {
    if (!user?.id) return;
    
    setLoading(true);
    try {
      const status = await apiRequest<{
        connected: boolean;
        provider: string | null;
        verified: boolean;
        account_type: string | null;
      }>('/api/broker/status', { method: 'GET' });
      setBrokerStatus(status);
    } catch (error: any) {
      console.error('Failed to load broker status:', error);
      setBrokerStatus({ connected: false, provider: null, verified: false, account_type: null });
    } finally {
      setLoading(false);
    }
  }

  const handleConnectManual = async () => {
    if (!apiKey.trim() || !apiSecret.trim()) {
      toast.error('Please enter both API key and secret');
      return;
    }

    setConnecting(true);
    try {
      const result = await apiRequest<{
        success: boolean;
        message: string;
        verified: boolean;
        needs_verification: boolean;
        error?: string;
      }>('/api/broker/connect/manual', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          api_key: apiKey.trim(),
          api_secret: apiSecret.trim(),
          base_url: baseUrl || undefined,
        }),
      });
      
      // Check if auto-verification succeeded
      if (result.verified) {
        toast.success(result.message || 'Broker credentials saved and verified successfully!');
      } else if (result.error) {
        toast.warning(result.message || 'Broker credentials saved but verification failed. Please verify manually.');
      } else {
        toast.success(result.message || 'Broker credentials stored. Please verify connection.');
      }
      
      setShowManualDialog(false);
      setApiKey('');
      setApiSecret('');
      await loadBrokerStatus();
    } catch (error: any) {
      toast.error(error.message || 'Failed to connect broker');
    } finally {
      setConnecting(false);
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    try {
      const result = await apiRequest<{
        verified: boolean;
        message: string;
        account_id?: string;
        account_type?: string;
      }>('/api/broker/verify', { method: 'POST' });
      
      if (result.verified) {
        toast.success(result.message || 'Broker connection verified!');
        await loadBrokerStatus();
      } else {
        toast.error(result.message || 'Verification failed');
      }
    } catch (error: any) {
      toast.error(error.message || 'Failed to verify broker connection');
    } finally {
      setVerifying(false);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm('Are you sure you want to disconnect your broker? This will disable Real Mode trading.')) {
      return;
    }

    try {
      await apiRequest('/api/broker/disconnect', { method: 'DELETE' });
      toast.success('Broker disconnected successfully');
      await loadBrokerStatus();
    } catch (error: any) {
      toast.error(error.message || 'Failed to disconnect broker');
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Broker & Real Money Settings</h1>
        <p className="text-gray-400">
          Connect your broker to enable real trading. Start in Paper Mode to learn the platform.
        </p>
      </div>

      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Info className="w-5 h-5 text-blue-400" />
            Important Information
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
            <p className="text-sm text-gray-300 mb-2">
              You do not need a broker account to use GSIN.
            </p>
            <p className="text-sm text-gray-300 mb-2">
              You can start in <strong>Paper Mode</strong> with real market data and test all features using virtual funds.
            </p>
            <p className="text-sm text-gray-300">
              Connect a broker and switch to <strong>Real Mode</strong> once you are comfortable with the platform.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardHeader>
          <CardTitle className="text-white">Current Trading Mode</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <Badge
              className={
                tradingMode === 'paper'
                  ? 'bg-blue-500/20 text-blue-400 border-blue-500/30 px-4 py-2'
                  : 'bg-red-500/20 text-red-400 border-red-500/30 px-4 py-2'
              }
            >
              {tradingMode === 'paper' ? 'Paper Mode' : 'Real Mode'}
            </Badge>
            <span className="text-sm text-gray-400">
              {tradingMode === 'paper'
                ? 'Simulated trading with real market data'
                : 'Live trading via connected broker'}
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-3">
            To change modes, use the toggle on the Dashboard or Manual Trading page.
          </p>
        </CardContent>
      </Card>

      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardHeader>
          <CardTitle className="text-white">Supported Brokers</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-4 border border-blue-500/20 rounded-lg bg-white/5">
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="text-xl font-semibold text-white">Alpaca</h3>
                  {brokerStatus?.connected && brokerStatus?.provider === 'alpaca' ? (
                    <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                      <CheckCircle2 className="w-3 h-3 mr-1" />
                      Connected
                    </Badge>
                  ) : (
                    <Badge className="bg-gray-500/20 text-gray-400 border-gray-500/30">
                      Not connected
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-gray-400">
                  API-first broker for US stocks and ETFs. Commission-free trading.
                </p>
              </div>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
                <span className="ml-2 text-gray-400">Loading...</span>
              </div>
            ) : !brokerStatus?.connected ? (
              <div className="space-y-3">
                <Dialog open={showManualDialog} onOpenChange={setShowManualDialog}>
                  <DialogTrigger asChild>
                    <Button className="w-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700">
                      <Key className="w-4 h-4 mr-2" />
                      Connect with API Keys
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="bg-black/90 border-blue-500/20 text-white">
                    <DialogHeader>
                      <DialogTitle>Connect Alpaca Broker</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 pt-4">
                      <div>
                        <Label className="text-gray-300">API Key</Label>
                        <Input
                          type="password"
                          value={apiKey}
                          onChange={(e) => setApiKey(e.target.value)}
                          placeholder="Enter your Alpaca API key"
                          className="mt-2 bg-white/5 border-blue-500/20 text-white"
                        />
                      </div>
                      <div>
                        <Label className="text-gray-300">API Secret</Label>
                        <Input
                          type="password"
                          value={apiSecret}
                          onChange={(e) => setApiSecret(e.target.value)}
                          placeholder="Enter your Alpaca API secret"
                          className="mt-2 bg-white/5 border-blue-500/20 text-white"
                        />
                      </div>
                      <div>
                        <Label className="text-gray-300">Base URL (Optional)</Label>
                        <Select value={baseUrl} onValueChange={setBaseUrl}>
                          <SelectTrigger className="mt-2 bg-white/5 border-blue-500/20 text-white">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="https://paper-api.alpaca.markets/v2">Paper Trading</SelectItem>
                            <SelectItem value="https://api.alpaca.markets/v2">Live Trading</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                        <p className="text-xs text-yellow-200">
                          ⚠️ Your credentials will be encrypted and stored securely. Never share your API keys.
                        </p>
                      </div>
                      <Button
                        onClick={handleConnectManual}
                        disabled={connecting || !apiKey.trim() || !apiSecret.trim()}
                        className="w-full bg-blue-600 hover:bg-blue-700"
                      >
                        {connecting ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Connecting...
                          </>
                        ) : (
                          'Connect Broker'
                        )}
                      </Button>
                    </div>
                  </DialogContent>
                </Dialog>
                <p className="text-xs text-gray-500 text-center">
                  Get your API keys from{' '}
                  <a
                    href="https://alpaca.markets"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:text-blue-300 inline-flex items-center gap-1"
                  >
                    alpaca.markets
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className={`p-3 border rounded-lg ${
                  brokerStatus.verified
                    ? 'bg-green-500/10 border-green-500/20'
                    : 'bg-yellow-500/10 border-yellow-500/20'
                }`}>
                  <div className="flex items-center gap-2 mb-2">
                    {brokerStatus.verified ? (
                      <>
                        <CheckCircle2 className="w-4 h-4 text-green-400" />
                        <p className="text-sm text-green-200 font-semibold">Connection Verified</p>
                      </>
                    ) : (
                      <>
                        <AlertCircle className="w-4 h-4 text-yellow-400" />
                        <p className="text-sm text-yellow-200 font-semibold">Connection Not Verified</p>
                      </>
                    )}
                  </div>
                  <p className="text-xs text-gray-300">
                    {brokerStatus.verified
                      ? `Account type: ${brokerStatus.account_type || 'unknown'}`
                      : 'Please verify your connection to enable Real Mode trading.'}
                  </p>
                </div>
                
                {!brokerStatus.verified && (
                  <Button
                    onClick={handleVerify}
                    disabled={verifying}
                    className="w-full bg-green-600 hover:bg-green-700"
                  >
                    {verifying ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Verifying...
                      </>
                    ) : (
                      'Verify Connection'
                    )}
                  </Button>
                )}
                
                <Button
                  onClick={handleDisconnect}
                  variant="outline"
                  className="w-full border-red-500/30 text-red-400 hover:bg-red-500/10"
                >
                  <X className="w-4 h-4 mr-2" />
                  Disconnect Broker
                </Button>
              </div>
            )}

            <p className="text-xs text-gray-500 mt-3">
              Get your API keys from{' '}
              <a
                href="https://alpaca.markets"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300"
              >
                alpaca.markets
              </a>
            </p>
          </div>

          <p className="text-sm text-gray-500 text-center">
            More brokers coming soon (Interactive Brokers, TD Ameritrade, etc.)
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
