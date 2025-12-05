'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Settings, DollarSign, Users, Shield, Zap } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminSettingsPage() {
  const handleSave = () => {
    toast.success('Settings saved successfully');
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
          <Settings className="w-8 h-8 text-blue-400" />
          Platform Settings
        </h1>
        <p className="text-gray-400">Configure platform-wide settings and parameters</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-green-400" />
              Subscription Pricing
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-gray-300">User Plan ($/month)</Label>
              <Input
                type="number"
                defaultValue="39.99"
                step="0.01"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
            <div>
              <Label className="text-gray-300">Pro Plan ($/month)</Label>
              <Input
                type="number"
                defaultValue="49.99"
                step="0.01"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
            <div>
              <Label className="text-gray-300">Creator Plan ($/month)</Label>
              <Input
                type="number"
                defaultValue="99.99"
                step="0.01"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-yellow-400" />
              Performance Fees
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-gray-300">User/Pro Fee (%)</Label>
              <Input
                type="number"
                defaultValue="5"
                step="0.1"
                max="10"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
            <div>
              <Label className="text-gray-300">Creator Fee (%)</Label>
              <Input
                type="number"
                defaultValue="3"
                step="0.1"
                max="10"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
            <div>
              <Label className="text-gray-300">Max Royalty Rate (%)</Label>
              <Input
                type="number"
                defaultValue="25"
                step="1"
                max="50"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Users className="w-5 h-5 text-purple-400" />
              User Management
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-gray-300">Free Trial Days</Label>
              <Input
                type="number"
                defaultValue="14"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
            <div>
              <Label className="text-gray-300">Max Strategies Per User</Label>
              <Input
                type="number"
                defaultValue="50"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
            <div>
              <Label className="text-gray-300">Max Groups Per Creator</Label>
              <Input
                type="number"
                defaultValue="10"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Shield className="w-5 h-5 text-red-400" />
              Security & API Keys
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-gray-300">Market Data API Key</Label>
              <Input
                type="password"
                placeholder="••••••••••••••••"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
            <div>
              <Label className="text-gray-300">Broker API Key</Label>
              <Input
                type="password"
                placeholder="••••••••••••••••"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
            <div>
              <Label className="text-gray-300">Encryption Key</Label>
              <Input
                type="password"
                placeholder="••••••••••••••••"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Zap className="w-5 h-5 text-blue-400" />
              Brain AI Settings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-gray-300">AI Model</Label>
              <Input
                defaultValue="GPT-4-Turbo"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
            <div>
              <Label className="text-gray-300">Max Signals Per Day</Label>
              <Input
                type="number"
                defaultValue="100"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
            <div>
              <Label className="text-gray-300">Confidence Threshold (%)</Label>
              <Input
                type="number"
                defaultValue="75"
                max="100"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white">Platform Controls</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-white/5 border border-blue-500/20 rounded-lg">
              <div>
                <div className="font-medium text-white">Maintenance Mode</div>
                <div className="text-sm text-gray-400">Temporarily disable platform</div>
              </div>
              <Switch />
            </div>

            <div className="flex items-center justify-between p-3 bg-white/5 border border-blue-500/20 rounded-lg">
              <div>
                <div className="font-medium text-white">New Registrations</div>
                <div className="text-sm text-gray-400">Allow new user signups</div>
              </div>
              <Switch defaultChecked />
            </div>

            <div className="flex items-center justify-between p-3 bg-white/5 border border-blue-500/20 rounded-lg">
              <div>
                <div className="font-medium text-white">Real Trading</div>
                <div className="text-sm text-gray-400">Enable live trading</div>
              </div>
              <Switch defaultChecked />
            </div>

            <div className="flex items-center justify-between p-3 bg-white/5 border border-blue-500/20 rounded-lg">
              <div>
                <div className="font-medium text-white">Brain Signals</div>
                <div className="text-sm text-gray-400">AI signal generation</div>
              </div>
              <Switch defaultChecked />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex justify-end gap-3">
        <Button variant="outline" className="bg-white/5 border-blue-500/20 text-white">
          Reset to Defaults
        </Button>
        <Button onClick={handleSave} className="bg-blue-600 hover:bg-blue-700">
          Save All Settings
        </Button>
      </div>
    </div>
  );
}
