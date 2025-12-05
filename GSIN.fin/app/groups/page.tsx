'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useStore } from '@/lib/store';
import { Search, Users, Plus, Key, Copy, Check } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import Link from 'next/link';
import { canCreateGroups, canJoinGroups, canAccessGroups } from '@/lib/subscription-utils';
import { Lock, ArrowUp } from 'lucide-react';
import { apiRequest } from '@/lib/api-client';

interface Group {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  join_code: string;
  max_size: number | null;
  is_discoverable: boolean;
  is_paid: boolean;
  price_monthly: number | null;
  created_at: string;
}

export default function GroupsPage() {
  const user = useStore((state) => state.user);
  const [ownedGroups, setOwnedGroups] = useState<Group[]>([]);
  const [memberGroups, setMemberGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [joining, setJoining] = useState(false);
  const [subscriptionInfo, setSubscriptionInfo] = useState<any>(null);
  
  // Create group form
  const [groupName, setGroupName] = useState('');
  const [groupDescription, setGroupDescription] = useState('');
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  
  // Join group form
  const [joinCode, setJoinCode] = useState('');
  const [joinDialogOpen, setJoinDialogOpen] = useState(false);
  const [referralCode, setReferralCode] = useState('');
  const [joinReferralDialogOpen, setJoinReferralDialogOpen] = useState(false);
  
  // Copy join code state
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  useEffect(() => {
    if (user?.id) {
      loadGroups();
      loadSubscriptionInfo();
    }
  }, [user?.id]);

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
    }
  }

  async function loadGroups() {
    if (!user?.id) {
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const data = await apiRequest<{ owned: Group[]; member: Group[] }>('/api/groups');
      setOwnedGroups(data.owned || []);
      setMemberGroups(data.member || []);
    } catch (error) {
      console.error('Error loading groups:', error);
      toast.error('Failed to load groups');
    } finally {
      setLoading(false);
    }
  }

  const handleCreateGroup = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!user?.id) {
      toast.error('Please log in to create a group');
      return;
    }

    if (!groupName.trim()) {
      toast.error('Group name is required');
      return;
    }

    setCreating(true);
    try {
      const newGroup = await apiRequest<Group>('/api/groups', {
        method: 'POST',
        body: JSON.stringify({
          name: groupName.trim(),
          description: groupDescription.trim() || null,
        }),
      });
      setOwnedGroups([...ownedGroups, newGroup]);
      setGroupName('');
      setGroupDescription('');
      setCreateDialogOpen(false);
      toast.success(`Group "${newGroup.name}" created! Share join code: ${newGroup.join_code}`);
    } catch (error: any) {
      console.error('Error creating group:', error);
      toast.error(error.message || 'Failed to create group');
    } finally {
      setCreating(false);
    }
  };

  const handleJoinGroup = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!user?.id) {
      toast.error('Please log in to join a group');
      return;
    }

    if (!joinCode.trim()) {
      toast.error('Join code is required');
      return;
    }

    setJoining(true);
    try {
      const joinedGroup = await apiRequest<Group>('/api/groups/join', {
        method: 'POST',
        body: JSON.stringify({
          join_code: joinCode.trim().toUpperCase(),
        }),
      });
      setMemberGroups([...memberGroups, joinedGroup]);
      setJoinCode('');
      setJoinDialogOpen(false);
      toast.success(`Successfully joined "${joinedGroup.name}"!`);
      await loadGroups(); // Reload to get fresh data
    } catch (error: any) {
      console.error('Error joining group:', error);
      toast.error(error.message || 'Failed to join group');
    } finally {
      setJoining(false);
    }
  };

  const handleJoinByReferral = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!user?.id) {
      toast.error('Please log in to join a group');
      return;
    }

    if (!referralCode.trim()) {
      toast.error('Referral code is required');
      return;
    }

    setJoining(true);
    try {
      const joinedGroup = await apiRequest<Group>('/api/groups/join/referral', {
        method: 'POST',
        body: JSON.stringify({
          referral_code: referralCode.trim(),
        }),
      });
      setMemberGroups([...memberGroups, joinedGroup]);
      setReferralCode('');
      setJoinReferralDialogOpen(false);
      toast.success(`Successfully joined "${joinedGroup.name}" via referral!`);
      await loadGroups(); // Reload to get fresh data
    } catch (error: any) {
      console.error('Error joining group by referral:', error);
      toast.error(error.message || 'Failed to join group');
    } finally {
      setJoining(false);
    }
  };

  const copyJoinCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    toast.success('Join code copied to clipboard!');
    setTimeout(() => setCopiedCode(null), 2000);
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white">Loading groups...</div>
      </div>
    );
  }

  // Check if user can access groups at all (Starter cannot access groups page)
  const planCode = subscriptionInfo?.planCode || user?.subscriptionTier?.toUpperCase() || 'USER';
  const canAccess = canAccessGroups(planCode);
  const canJoin = canJoinGroups(planCode);
  const canCreate = canCreateGroups(planCode);

  // Show upgrade message for Starter users - they cannot access groups at all
  if (!canAccess) {
    return (
      <div className="p-6 space-y-6">
        <Card className="bg-yellow-500/10 border-yellow-500/30">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <Lock className="w-8 h-8 text-yellow-400" />
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-white mb-1">Upgrade Required</h3>
                <p className="text-gray-300 mb-3">
                  Groups are only available for Pro and Creator accounts. Starter account users cannot access the Groups section. Upgrade to Pro or Creator to join trading groups and collaborate with other traders.
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
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Trading Groups</h1>
          <p className="text-gray-400">Collaborate with traders and share strategies</p>
        </div>
        <div className="flex gap-3">
          <Dialog open={joinDialogOpen} onOpenChange={setJoinDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="gap-2 bg-white/5 border-blue-500/20 text-white">
                <Key className="w-4 h-4" />
                Join with Code
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-black/90 border-blue-500/20">
              <DialogHeader>
                <DialogTitle className="text-white">Join Group with Code</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleJoinGroup} className="space-y-4 pt-4">
                <div>
                  <Label className="text-gray-300">Join Code</Label>
                  <Input
                    value={joinCode}
                    onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                    placeholder="ABC12345"
                    className="mt-2 bg-white/5 border-blue-500/20 text-white"
                    maxLength={10}
                  />
                  <p className="text-xs text-gray-400 mt-1">Enter the 8-character join code</p>
                </div>
                <Button 
                  type="submit" 
                  disabled={joining}
                  className="w-full bg-blue-600 hover:bg-blue-700"
                >
                  {joining ? 'Joining...' : 'Join Group'}
                </Button>
              </form>
            </DialogContent>
          </Dialog>

          <Dialog open={joinReferralDialogOpen} onOpenChange={setJoinReferralDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="gap-2 bg-white/5 border-purple-500/20 text-white">
                <Users className="w-4 h-4" />
                Join with Referral
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-black/90 border-blue-500/20">
              <DialogHeader>
                <DialogTitle className="text-white">Join Group with Referral Code</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleJoinByReferral} className="space-y-4 pt-4">
                <div>
                  <Label className="text-gray-300">Referral Code</Label>
                  <Input
                    value={referralCode}
                    onChange={(e) => setReferralCode(e.target.value)}
                    placeholder="Enter referral code"
                    className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  />
                  <p className="text-xs text-gray-400 mt-1">Enter the referral code shared by a group member</p>
                </div>
                <Button 
                  type="submit" 
                  disabled={joining}
                  className="w-full bg-purple-600 hover:bg-purple-700"
                >
                  {joining ? 'Joining...' : 'Join Group'}
                </Button>
              </form>
            </DialogContent>
          </Dialog>
          
          <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button 
                className="gap-2 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={!canCreate}
                title={!canCreate ? 'Upgrade to Creator to create groups (unlimited groups for Creator accounts)' : ''}
              >
              <Plus className="w-4 h-4" />
              Create Group {canCreate && planCode === 'CREATOR' && '(Unlimited)'}
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-black/90 border-blue-500/20">
              <DialogHeader>
                <DialogTitle className="text-white">Create New Group</DialogTitle>
              </DialogHeader>
              {!canCreate ? (
                <div className="p-6">
                  <div className="flex items-center gap-4 mb-4">
                    <Lock className="w-8 h-8 text-yellow-400" />
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-white mb-1">Upgrade Required</h3>
                      <p className="text-gray-300 mb-3">
                        Group creation is only available for Creator accounts. Upgrade your plan to create and manage groups.
                      </p>
                      <Link href="/subscriptions">
                        <Button className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 gap-2">
                          <ArrowUp className="w-4 h-4" />
                          Upgrade to Creator
            </Button>
          </Link>
        </div>
      </div>
                </div>
              ) : (
              <form onSubmit={handleCreateGroup} className="space-y-4 pt-4">
                <div>
                  <Label className="text-gray-300">Group Name *</Label>
            <Input
                    value={groupName}
                    onChange={(e) => setGroupName(e.target.value)}
                    placeholder="My Trading Group"
                    className="mt-2 bg-white/5 border-blue-500/20 text-white"
                    required
                  />
                </div>
                <div>
                  <Label className="text-gray-300">Description (Optional)</Label>
                  <Textarea
                    value={groupDescription}
                    onChange={(e) => setGroupDescription(e.target.value)}
                    placeholder="Describe your group..."
                    className="mt-2 bg-white/5 border-blue-500/20 text-white"
                    rows={3}
            />
          </div>
                <Button 
                  type="submit" 
                  disabled={creating}
                  className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                >
                  {creating ? 'Creating...' : 'Create Group'}
                </Button>
              </form>
              )}
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* My Groups (Owned) */}
      {ownedGroups.length > 0 && (
      <div>
        <h2 className="text-xl font-semibold text-white mb-4">My Groups</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {ownedGroups.map((group) => (
              <Card key={group.id} className="bg-black/60 backdrop-blur-xl border-blue-500/20 hover:border-blue-500/40 transition-all">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <CardTitle className="text-white text-lg">{group.name}</CardTitle>
                    <Badge className="bg-green-500/20 text-green-400">Owner</Badge>
                  </div>
                  {group.description && (
                    <p className="text-sm text-gray-400 line-clamp-2 mt-2">{group.description}</p>
                  )}
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
                    <div>
                      <p className="text-xs text-gray-400">Join Code</p>
                      <p className="text-lg font-mono font-bold text-white">{group.join_code}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => copyJoinCode(group.join_code)}
                      className="hover:bg-blue-500/20"
                    >
                      {copiedCode === group.join_code ? (
                        <Check className="w-4 h-4 text-green-400" />
                      ) : (
                        <Copy className="w-4 h-4 text-gray-400" />
                      )}
                    </Button>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="text-xs text-gray-400">
                      Created {new Date(group.created_at).toLocaleDateString()}
                    </div>
                    <Link href={`/groups/${group.id}`}>
                      <Button variant="outline" size="sm" className="text-xs">
                        View Group
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
          ))}
        </div>
      </div>
      )}

      {/* Groups I've Joined */}
      {memberGroups.length > 0 && (
      <div>
          <h2 className="text-xl font-semibold text-white mb-4">Groups I've Joined</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {memberGroups.map((group) => (
              <Card key={group.id} className="bg-black/60 backdrop-blur-xl border-blue-500/20 hover:border-blue-500/40 transition-all">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <CardTitle className="text-white text-lg">{group.name}</CardTitle>
                    <Badge className="bg-blue-500/20 text-blue-400">Member</Badge>
                  </div>
                  {group.description && (
                    <p className="text-sm text-gray-400 line-clamp-2 mt-2">{group.description}</p>
                  )}
              </CardHeader>
              <CardContent className="space-y-4">
                  <div className="flex items-center gap-2 text-sm text-gray-400">
                    <Users className="w-4 h-4" />
                    <span>Joined {new Date(group.created_at).toLocaleDateString()}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
      )}

      {/* Empty State */}
      {ownedGroups.length === 0 && memberGroups.length === 0 && (
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardContent className="p-12 text-center">
            <Users className="w-16 h-16 text-gray-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-white mb-2">No Groups Yet</h3>
            <p className="text-gray-400 mb-6">
              Create your first group or join one using a join code
            </p>
            <div className="flex gap-3 justify-center">
              <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                <DialogTrigger asChild>
                  <Button className="gap-2 bg-gradient-to-r from-blue-500 to-purple-600">
                    <Plus className="w-4 h-4" />
                    Create Group
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-black/90 border-blue-500/20">
                  <DialogHeader>
                    <DialogTitle className="text-white">Create New Group</DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleCreateGroup} className="space-y-4 pt-4">
                    <div>
                      <Label className="text-gray-300">Group Name *</Label>
                      <Input
                        value={groupName}
                        onChange={(e) => setGroupName(e.target.value)}
                        placeholder="My Trading Group"
                        className="mt-2 bg-white/5 border-blue-500/20 text-white"
                        required
                      />
                    </div>
                    <div>
                      <Label className="text-gray-300">Description (Optional)</Label>
                      <Textarea
                        value={groupDescription}
                        onChange={(e) => setGroupDescription(e.target.value)}
                        placeholder="Describe your group..."
                        className="mt-2 bg-white/5 border-blue-500/20 text-white"
                        rows={3}
                      />
                    </div>
                    <Button 
                      type="submit" 
                      disabled={creating}
                      className="w-full bg-gradient-to-r from-blue-600 to-purple-600"
                    >
                      {creating ? 'Creating...' : 'Create Group'}
                    </Button>
                  </form>
                </DialogContent>
              </Dialog>
              <Dialog open={joinDialogOpen} onOpenChange={setJoinDialogOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline" className="gap-2 border-blue-500/20 text-white">
                    <Key className="w-4 h-4" />
                    Join with Code
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-black/90 border-blue-500/20">
                  <DialogHeader>
                    <DialogTitle className="text-white">Join Group with Code</DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleJoinGroup} className="space-y-4 pt-4">
                    <div>
                      <Label className="text-gray-300">Join Code</Label>
                      <Input
                        value={joinCode}
                        onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                        placeholder="ABC12345"
                        className="mt-2 bg-white/5 border-blue-500/20 text-white"
                        maxLength={10}
                      />
                    </div>
                    <Button 
                      type="submit" 
                      disabled={joining}
                      className="w-full bg-blue-600 hover:bg-blue-700"
                    >
                      {joining ? 'Joining...' : 'Join Group'}
                    </Button>
                  </form>
                </DialogContent>
              </Dialog>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
