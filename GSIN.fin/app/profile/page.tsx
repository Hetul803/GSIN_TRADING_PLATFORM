'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useStore } from '@/lib/store';
import { User, Mail, DollarSign, TrendingUp, Layers, Users, Award, Settings } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface UserProfile {
  id: string;
  email: string;
  name: string | null;
  role: string;
  subscriptionTier: string;
  createdAt: string;
  updatedAt: string;
}

export default function ProfilePage() {
  const storeUser = useStore((state) => state.user);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [summary, setSummary] = useState<any>(null);
  const [strategies, setStrategies] = useState<any[]>([]);
  const [groups, setGroups] = useState<any[]>([]);

  useEffect(() => {
    if (storeUser?.id) {
      fetchUserProfile();
      fetchTradingStats();
    }
  }, [storeUser?.id]);

  const fetchTradingStats = async () => {
    if (!storeUser?.id) return;
    
    try {
      // Fetch trade summary
      const summaryRes = await fetch(`${BACKEND_URL}/api/trades/summary?mode=PAPER`, {
        headers: { 'X-User-Id': storeUser.id },
      });
      if (summaryRes.ok) {
        const data = await summaryRes.json();
        setSummary(data);
      }

      // Fetch strategies count
      const strategiesRes = await fetch(`${BACKEND_URL}/api/strategies`, {
        headers: { 'X-User-Id': storeUser.id },
      });
      if (strategiesRes.ok) {
        const data = await strategiesRes.json();
        setStrategies(data || []);
      }

      // Fetch groups count
      const groupsRes = await fetch(`${BACKEND_URL}/api/groups?userId=${storeUser.id}`, {
        headers: { 'X-User-Id': storeUser.id },
      });
      if (groupsRes.ok) {
        const data = await groupsRes.json();
        setGroups(data.groups || []);
      }
    } catch (error) {
      console.error('Error fetching trading stats:', error);
    }
  };

  const fetchUserProfile = async () => {
    if (!storeUser?.id) return;
    
    try {
      setLoading(true);
      
      // Get JWT token from localStorage
      const token = typeof window !== 'undefined' ? localStorage.getItem('gsin_token') : null;
      if (!token) {
        toast.error('Authentication required. Please log in again.');
        return;
      }
      
      const response = await fetch(`${BACKEND_URL}/api/users/me`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch user profile' }));
        throw new Error(errorData.detail || 'Failed to fetch user profile');
      }

      const data = await response.json();
      setUser(data);
      setName(data.name || '');
      setEmail(data.email || '');
    } catch (error: any) {
      console.error('Error fetching user profile:', error);
      toast.error(error.message || 'Failed to load profile');
      // Fallback to store user if available
      if (storeUser) {
        setUser({
          id: storeUser.id,
          email: storeUser.email,
          name: storeUser.name,
          role: 'user',
          subscriptionTier: storeUser.subscriptionTier,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        });
        setName(storeUser.name || '');
        setEmail(storeUser.email || '');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!user) return;

    try {
      setSaving(true);
      const userId = user.id;
      
      // Get JWT token from localStorage
      const token = typeof window !== 'undefined' ? localStorage.getItem('gsin_token') : null;
      if (!token) {
        toast.error('Authentication required. Please log in again.');
        return;
      }
      
      const response = await fetch(`${BACKEND_URL}/api/users/me`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: name || null,
          email: email || null,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to update profile' }));
        throw new Error(errorData.detail || 'Failed to update profile');
      }

      const updatedUser = await response.json();
      setUser(updatedUser);
      
      // Update store if available
      const setStoreUser = useStore.getState().setUser;
      if (setStoreUser && storeUser) {
        setStoreUser({
          ...storeUser,
          name: updatedUser.name || storeUser.name,
          email: updatedUser.email || storeUser.email,
          subscriptionTier: updatedUser.subscriptionTier as any,
        });
      }

      toast.success('Profile updated successfully');
    } catch (error) {
      console.error('Error updating profile:', error);
      toast.error('Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white text-lg">Loading profile...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white">Profile</h1>
        <p className="text-gray-400">Manage your account settings and view your stats</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white">Personal Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-gray-300">Full Name</Label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  disabled={loading || saving}
                />
              </div>

              <div>
                <Label className="text-gray-300">Email</Label>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  disabled={loading || saving}
                />
              </div>

              <div>
                <Label className="text-gray-300">Country</Label>
                <Input
                  defaultValue="United States"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                />
              </div>

              <div className="flex justify-end gap-3 pt-4">
                <Button 
                  variant="outline" 
                  className="bg-white/5 border-blue-500/20 text-white"
                  onClick={() => {
                    setName(user?.name || '');
                    setEmail(user?.email || '');
                  }}
                  disabled={loading || saving}
                >
                  Cancel
                </Button>
                <Button 
                  onClick={handleSave} 
                  className="bg-blue-600 hover:bg-blue-700"
                  disabled={loading || saving}
                >
                  {saving ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white">Trading Statistics</CardTitle>
            </CardHeader>
            <CardContent>
              {summary ? (
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-white/5 border border-blue-500/20 rounded-lg">
                    <div className="text-sm text-gray-400 mb-1">Total Trades</div>
                    <div className="text-2xl font-bold text-white">{summary.total_trades}</div>
                  </div>
                  <div className="p-4 bg-white/5 border border-green-500/20 rounded-lg">
                    <div className="text-sm text-gray-400 mb-1">Win Rate</div>
                    <div className="text-2xl font-bold text-green-400">
                      {(summary.win_rate * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="p-4 bg-white/5 border border-blue-500/20 rounded-lg">
                    <div className="text-sm text-gray-400 mb-1">Total P&L</div>
                    <div className={`text-2xl font-bold ${summary.total_realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {summary.total_realized_pnl >= 0 ? '+' : ''}${summary.total_realized_pnl.toFixed(2)}
                    </div>
                  </div>
                  <div className="p-4 bg-white/5 border border-purple-500/20 rounded-lg">
                    <div className="text-sm text-gray-400 mb-1">Closed Trades</div>
                    <div className="text-2xl font-bold text-purple-400">{summary.closed_trades}</div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-gray-400">
                  <p>No trading statistics yet</p>
                  <p className="text-sm text-gray-500 mt-2">Start trading to see your stats here</p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white">Security</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-gray-300">Current Password</Label>
                <Input
                  type="password"
                  placeholder="••••••••"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                />
              </div>

              <div>
                <Label className="text-gray-300">New Password</Label>
                <Input
                  type="password"
                  placeholder="••••••••"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                />
              </div>

              <div>
                <Label className="text-gray-300">Confirm New Password</Label>
                <Input
                  type="password"
                  placeholder="••••••••"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                />
              </div>

              <Button className="bg-blue-600 hover:bg-blue-700">
                Update Password
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white">Account Overview</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3 p-3 bg-gradient-to-r from-blue-500/20 to-purple-500/20 border border-blue-500/20 rounded-lg">
                <User className="w-8 h-8 text-blue-400" />
                <div>
                  <div className="text-sm text-gray-400">Subscription</div>
                  <div className="font-semibold text-white capitalize">{user?.subscriptionTier || storeUser?.subscriptionTier || 'user'} Plan</div>
                </div>
              </div>

              <div className="flex items-center gap-3 p-3 bg-white/5 border border-blue-500/20 rounded-lg">
                <DollarSign className="w-8 h-8 text-green-400" />
                <div>
                  <div className="text-sm text-gray-400">Account Equity</div>
                  <div className="font-semibold text-white">${storeUser?.equity?.toLocaleString() || '0'}</div>
                </div>
              </div>

              <div className="flex items-center gap-3 p-3 bg-white/5 border border-blue-500/20 rounded-lg">
                <TrendingUp className="w-8 h-8 text-blue-400" />
                <div>
                  <div className="text-sm text-gray-400">Active Strategies</div>
                  <div className="font-semibold text-white">{strategies.length}</div>
                </div>
              </div>

              <div className="flex items-center gap-3 p-3 bg-white/5 border border-blue-500/20 rounded-lg">
                <Users className="w-8 h-8 text-purple-400" />
                <div>
                  <div className="text-sm text-gray-400">Groups Joined</div>
                  <div className="font-semibold text-white">{groups.length}</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {(user?.subscriptionTier === 'creator' || storeUser?.subscriptionTier === 'creator') && (
            <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Award className="w-5 h-5 text-yellow-400" />
                  Creator Stats
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-400">Strategies Published</span>
                  <span className="text-white font-semibold">{strategies.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Groups Created</span>
                  <span className="text-white font-semibold">
                    {groups.filter((g: any) => g.ownerId === storeUser?.id).length}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Total P&L</span>
                  <span className={`font-semibold ${(summary?.total_realized_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {summary?.total_realized_pnl ? (summary.total_realized_pnl >= 0 ? '+' : '') + '$' + summary.total_realized_pnl.toFixed(2) : '$0.00'}
                  </span>
                </div>
              </CardContent>
            </Card>
          )}

          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Link href="/settings/account">
                <Button variant="outline" className="w-full justify-start gap-2 bg-white/5 border-blue-500/20 text-white">
                  <Settings className="w-4 h-4" />
                  Account Settings
                </Button>
              </Link>
              <Button variant="outline" className="w-full justify-start gap-2 bg-white/5 border-blue-500/20 text-white">
                <Layers className="w-4 h-4" />
                My Strategies
              </Button>
              <Button variant="outline" className="w-full justify-start gap-2 bg-white/5 border-blue-500/20 text-white">
                <Users className="w-4 h-4" />
                My Groups
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
