'use client';

import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useStore } from '@/lib/store';
import { useRouter } from 'next/navigation';
import { apiRequest } from '@/lib/api-client';
import { ArrowLeft, Users, Copy, MessageCircle, Trash2, Send, X, RefreshCw, Upload, Play, Layers, AlertCircle } from 'lucide-react';
import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from '@/components/ui/dialog';
import { format } from 'date-fns';

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

interface GroupMessage {
  id: string;
  group_id: string;
  user_id: string;
  content: string;
  message_type?: string;
  strategy_id?: string | null;
  strategy_data?: {
    id: string;
    name: string;
    description: string | null;
    status: string;
    is_backtested: boolean;
    backtest_status: string;
    win_rate?: number | null;
    sharpe_ratio?: number | null;
    total_trades?: number | null;
    explanation_human?: string | null;
    risk_note?: string | null;
  } | null;
  created_at: string;
  sender_name: string | null;
  is_owner_message: boolean;
}

interface GroupMember {
  id: string;
  user_id: string;
  role: string;
  created_at: string;
  name?: string;
}

export default function GroupDetailPage({ params }: { params: { groupId: string } }) {
  const user = useStore((state) => state.user);
  const router = useRouter();
  const [group, setGroup] = useState<Group | null>(null);
  const [members, setMembers] = useState<GroupMember[]>([]);
  const [messages, setMessages] = useState<GroupMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [messageContent, setMessageContent] = useState('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteConfirmDialogOpen, setDeleteConfirmDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [leaveDialogOpen, setLeaveDialogOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [referralCode, setReferralCode] = useState<string | null>(null);
  const [referralDialogOpen, setReferralDialogOpen] = useState(false);
  const [generatingReferral, setGeneratingReferral] = useState(false);
  const [strategies, setStrategies] = useState<any[]>([]);
  const [uploadStrategyDialogOpen, setUploadStrategyDialogOpen] = useState(false);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [executingStrategy, setExecutingStrategy] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  useEffect(() => {
    if (user?.id) {
      loadGroupData();
      loadMessages();
      loadGroupStrategies();
      // Poll for new messages every 5 seconds
      const interval = setInterval(() => {
        loadMessages();
        loadGroupStrategies();
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [user?.id, params.groupId]);

  useEffect(() => {
    // Scroll to bottom when new messages arrive
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function loadGroupData() {
    if (!user?.id) return;

    setLoading(true);
    try {
      // Load group details using apiRequest (includes JWT token)
      const groupData = await apiRequest<Group>(`/api/groups/${params.groupId}`);
      setGroup(groupData);

      // Load members using apiRequest (includes JWT token)
      const membersData = await apiRequest<GroupMember[]>(`/api/groups/${params.groupId}/members`);
      setMembers(membersData);
    } catch (error: any) {
      console.error('Error loading group:', error);
      // If group not found (404), it might have been deleted
      if (error.message?.includes('404') || error.message?.includes('not found')) {
        toast.error('This group may have been deleted. Check your notifications.');
        // Redirect to groups page after a short delay
        setTimeout(() => {
          router.push('/groups');
        }, 2000);
      } else {
        toast.error(error.message || 'Failed to load group');
      }
    } finally {
      setLoading(false);
    }
  }

  async function loadMessages() {
    if (!user?.id || !params.groupId) return;

    try {
      const messagesData = await apiRequest<GroupMessage[]>(`/api/groups/${params.groupId}/messages?limit=100`);
      // Messages are already in chronological order (oldest first)
      setMessages(messagesData);
    } catch (error) {
      console.error('Error loading messages:', error);
    }
  }

  async function loadGroupStrategies() {
    if (!user?.id || !params.groupId) return;
    try {
      const response = await fetch(`${BACKEND_URL}/api/groups/${params.groupId}/strategies`, {
        headers: { 'X-User-Id': user.id },
      });
      if (response.ok) {
        const data = await response.json();
        setStrategies(data.strategies || []);
      }
    } catch (error) {
      console.error('Error loading group strategies:', error);
    }
  }

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!user?.id || !messageContent.trim()) return;

    setSending(true);
    try {
      const newMessage = await apiRequest<GroupMessage>(`/api/groups/${params.groupId}/messages`, {
        method: 'POST',
        body: JSON.stringify({
          content: messageContent.trim(),
          message_type: 'TEXT',
        }),
      });

      setMessages([...messages, newMessage]);
      setMessageContent('');
      toast.success('Message sent');
    } catch (error: any) {
      console.error('Error sending message:', error);
      toast.error(error.message || 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  const handleUploadStrategy = async (strategyId: string) => {
    if (!user?.id || !strategyId) return;
    
    setSending(true);
    try {
      // First, get strategy details
      const strategy = await apiRequest<any>(`/api/strategies/${strategyId}`);
      
      // Send strategy as message
      const newMessage = await apiRequest<GroupMessage>(`/api/groups/${params.groupId}/messages`, {
        method: 'POST',
        body: JSON.stringify({
          content: `Shared strategy: ${strategy.name}`,
          message_type: 'STRATEGY',
          strategy_id: strategyId,
        }),
      });

      setMessages([...messages, newMessage]);
      setUploadStrategyDialogOpen(false);
      setSelectedStrategyId(null);
      toast.success('Strategy shared in group');
      loadGroupStrategies();
    } catch (error: any) {
      console.error('Error uploading strategy:', error);
      toast.error(error.message || 'Failed to share strategy');
    } finally {
      setSending(false);
    }
  };

  const handleExecuteStrategy = async (strategyId: string) => {
    if (!user?.id || !strategyId) return;
    
    setExecutingStrategy(strategyId);
    try {
      // Validate that user can execute this strategy from the group
      await apiRequest(`/api/groups/${params.groupId}/strategies/${strategyId}/execute`, {
        method: 'POST',
      });
      
      // Redirect to trading terminal with strategy pre-selected
      toast.success('Redirecting to trading terminal to execute strategy...');
      router.push(`/terminal?strategy=${strategyId}`);
    } catch (error: any) {
      console.error('Error executing strategy:', error);
      toast.error(error.message || 'Failed to execute strategy');
    } finally {
      setExecutingStrategy(null);
    }
  };

  const handleDeleteMessage = async (messageId: string) => {
    if (!user?.id) return;

    try {
      await apiRequest(`/api/groups/${params.groupId}/messages/${messageId}`, {
        method: 'DELETE',
      });
      toast.success('Message deleted');
      await loadMessages();
    } catch (error: any) {
      console.error('Error deleting message:', error);
      toast.error(error.message || 'Failed to delete message');
    }
  };

  const handleDeleteGroup = async () => {
    if (!user?.id || !group) return;

    setDeleting(true);
    try {
      await apiRequest(`/api/groups/${group.id}`, {
        method: 'DELETE',
      });
      toast.success('Group deleted successfully');
      router.push('/groups');
    } catch (error: any) {
      console.error('Error deleting group:', error);
      toast.error(error.message || 'Failed to delete group');
    } finally {
      setDeleting(false);
      setDeleteDialogOpen(false);
      setDeleteConfirmDialogOpen(false);
    }
  };

  const handleCopyJoinCode = () => {
    if (group?.join_code) {
      navigator.clipboard.writeText(group.join_code);
      toast.success('Join code copied to clipboard');
    }
  };

  const handleLeaveGroup = async () => {
    if (!user?.id || !group) return;

    setLeaving(true);
    try {
      await apiRequest(`/api/groups/${group.id}/leave`, {
        method: 'POST',
      });
      toast.success('You have left the group. You will need an invitation or join code to rejoin.');
      router.push('/groups');
    } catch (error: any) {
      console.error('Error leaving group:', error);
      toast.error(error.message || 'Failed to leave group');
    } finally {
      setLeaving(false);
      setLeaveDialogOpen(false);
    }
  };

  const handleGenerateReferral = async () => {
    if (!user?.id || !group) return;

    setGeneratingReferral(true);
    try {
      const data = await apiRequest<{ referral_code?: string; code?: string }>(`/api/groups/${group.id}/referral`, {
        method: 'POST',
      });
      setReferralCode(data.referral_code || data.code || null);
      setReferralDialogOpen(true);
      toast.success('Referral code generated');
    } catch (error: any) {
      console.error('Error generating referral:', error);
      toast.error(error.message || 'Failed to generate referral code');
    } finally {
      setGeneratingReferral(false);
    }
  };

  const isOwner = group && user?.id === group.owner_id;

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white">Loading group...</div>
      </div>
    );
  }

  if (!group) {
    return (
      <div className="p-6">
        <Link href="/groups">
          <Button variant="ghost" className="gap-2 text-gray-400 hover:text-white">
            <ArrowLeft className="w-4 h-4" />
            Back to Groups
          </Button>
        </Link>
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20 mt-6">
          <CardContent className="p-8 text-center">
            <p className="text-gray-400">Group not found</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <Link href="/groups">
        <Button variant="ghost" className="gap-2 text-gray-400 hover:text-white">
          <ArrowLeft className="w-4 h-4" />
          Back to Groups
        </Button>
      </Link>

      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-bold text-white">{group.name}</h1>
            {isOwner && <Badge className="bg-green-500/20 text-green-400">Owner</Badge>}
          </div>
          {group.description && <p className="text-gray-400 mb-4">{group.description}</p>}
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-gray-400" />
              <span className="text-white">{members.length} members</span>
            </div>
            {group.price_monthly && (
              <Badge className="bg-blue-500/20 text-blue-400">
                ${(group.price_monthly / 100).toFixed(2)}/month
              </Badge>
            )}
          </div>
        </div>
        <div className="flex gap-3">
          {!isOwner && (
            <Dialog open={leaveDialogOpen} onOpenChange={setLeaveDialogOpen}>
              <DialogTrigger asChild>
                <Button
                  variant="outline"
                  disabled={leaving}
                  className="gap-2 bg-orange-500/10 border-orange-500/20 text-orange-400 hover:bg-orange-500/20"
                >
                  <X className="w-4 h-4" />
                  Leave Group
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-black/90 border-blue-500/20">
                <DialogHeader>
                  <DialogTitle className="text-white">Leave Group</DialogTitle>
                  <DialogDescription className="text-gray-400">
                    Are you sure you want to leave this group? You will not be a member of this group anymore and will need an invitation or join code to join again.
                  </DialogDescription>
                </DialogHeader>
                <div className="flex gap-3 mt-4">
                  <Button
                    onClick={handleLeaveGroup}
                    disabled={leaving}
                    className="flex-1 bg-orange-600 hover:bg-orange-700"
                  >
                    {leaving ? 'Leaving...' : 'Leave Group'}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setLeaveDialogOpen(false)}
                    className="flex-1 border-blue-500/20 text-white"
                  >
                    Cancel
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          )}
          {isOwner && (
            <>
              <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline" className="gap-2 bg-red-500/10 border-red-500/20 text-red-400 hover:bg-red-500/20">
                    <Trash2 className="w-4 h-4" />
                    Delete Group
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-black/90 border-blue-500/20">
                  <DialogHeader>
                    <DialogTitle className="text-white">Delete Group - First Confirmation</DialogTitle>
                    <DialogDescription className="text-gray-400">
                      Are you sure you want to delete this group? This action cannot be undone.
                      All members, messages, and associated data will be permanently deleted.
                      All members will be notified that the group has been deleted.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="flex gap-3 mt-4">
                    <Button
                      onClick={() => {
                        setDeleteDialogOpen(false);
                        setDeleteConfirmDialogOpen(true);
                      }}
                      className="flex-1 bg-red-600 hover:bg-red-700"
                    >
                      Yes, Delete Group
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => setDeleteDialogOpen(false)}
                      className="flex-1 border-blue-500/20 text-white"
                    >
                      Cancel
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
              <Dialog open={deleteConfirmDialogOpen} onOpenChange={setDeleteConfirmDialogOpen}>
                <DialogContent className="bg-black/90 border-red-500/20">
                  <DialogHeader>
                    <DialogTitle className="text-white">Delete Group - Final Confirmation</DialogTitle>
                    <DialogDescription className="text-gray-400">
                      <strong className="text-red-400">WARNING:</strong> This is your final confirmation. 
                      Once you delete this group, it cannot be recovered. All members will be notified and lose access immediately.
                      <br /><br />
                      Are you absolutely sure you want to delete "{group?.name}"?
                    </DialogDescription>
                  </DialogHeader>
                  <div className="flex gap-3 mt-4">
                    <Button
                      onClick={handleDeleteGroup}
                      disabled={deleting}
                      className="flex-1 bg-red-600 hover:bg-red-700"
                    >
                      {deleting ? 'Deleting...' : 'Yes, Delete Permanently'}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setDeleteConfirmDialogOpen(false);
                        setDeleteDialogOpen(false);
                      }}
                      className="flex-1 border-blue-500/20 text-white"
                    >
                      Cancel
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
            </>
          )}
        </div>
      </div>

      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardContent className="p-6">
          <div className="space-y-4">
            <div>
              <label className="text-gray-300 text-sm mb-2 block">Join Code</label>
              <div className="flex gap-2">
                <Input
                  value={group.join_code}
                  readOnly
                  className="bg-white/5 border-blue-500/20 text-white font-mono"
                />
                <Button onClick={handleCopyJoinCode} variant="outline" className="gap-2 bg-white/5 border-blue-500/20 text-white">
                  <Copy className="w-4 h-4" />
                  Copy
                </Button>
              </div>
            </div>
            {isOwner && (
              <div>
                <label className="text-gray-300 text-sm mb-2 block">Referral Code</label>
                <div className="flex gap-2">
                  <Button
                    onClick={handleGenerateReferral}
                    disabled={generatingReferral}
                    variant="outline"
                    className="gap-2 bg-white/5 border-blue-500/20 text-white"
                  >
                    {generatingReferral ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        Generating...
                      </>
                    ) : (
                      <>
                        <Copy className="w-4 h-4" />
                        Generate Invite Link
                      </>
                    )}
                  </Button>
                </div>
                {referralCode && (
                  <div className="mt-2 p-3 bg-green-500/10 border border-green-500/20 rounded-lg">
                    <p className="text-xs text-gray-400 mb-1">Referral Code:</p>
                    <p className="text-green-400 font-mono font-semibold">{referralCode}</p>
                    <p className="text-xs text-gray-500 mt-2">Share this code to invite members</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="chat" className="space-y-6">
        <TabsList className="bg-black/60 backdrop-blur-xl border border-blue-500/20">
          <TabsTrigger value="chat">Group Chat</TabsTrigger>
          <TabsTrigger value="members">Members</TabsTrigger>
        </TabsList>

        <TabsContent value="chat">
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <MessageCircle className="w-5 h-5" />
                Group Chat
                <Badge className="ml-auto bg-blue-500/20 text-blue-400">
                  {messages.length} messages
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4 mb-4 h-96 overflow-y-auto p-4 bg-white/5 rounded-lg">
                {messages.length === 0 ? (
                  <div className="text-center text-gray-400 py-8">
                    No messages yet. Start the conversation!
                  </div>
                ) : (
                  messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`p-3 bg-white/5 border border-blue-500/20 rounded-lg ${
                        msg.is_owner_message ? 'border-green-500/30 bg-green-500/5' : ''
                      }`}
                    >
                    <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-white text-sm">
                            {msg.sender_name || 'Unknown'}
                          </span>
                          {msg.is_owner_message && (
                            <Badge className="bg-green-500/20 text-green-400 text-xs">Owner</Badge>
                          )}
                          {msg.user_id === user?.id && (
                            <Badge className="bg-blue-500/20 text-blue-400 text-xs">You</Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-400">
                            {format(new Date(msg.created_at), 'MMM dd, HH:mm')}
                          </span>
                          {/* Show delete button:
                              - Owner can delete any message
                              - Members can delete their own messages (but NOT owner's messages) */}
                          {isOwner ? (
                            // Owner can delete any message
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteMessage(msg.id)}
                              className="h-6 w-6 p-0 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                            >
                              <X className="w-3 h-3" />
                            </Button>
                          ) : (
                            // Members can only delete their own messages (not owner's)
                            msg.user_id === user?.id && !msg.is_owner_message && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeleteMessage(msg.id)}
                                className="h-6 w-6 p-0 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                              >
                                <X className="w-3 h-3" />
                              </Button>
                            )
                          )}
                        </div>
                      </div>
                      <p className="text-sm text-gray-300">{msg.content}</p>
                      
                      {/* GROUP CHAT STRATEGY FUNCTIONALITY: Display strategy if message type is STRATEGY */}
                      {msg.message_type === 'STRATEGY' && msg.strategy_data && (
                        <div className="mt-3 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <Layers className="w-4 h-4 text-blue-400" />
                              <span className="font-semibold text-white">{msg.strategy_data.name}</span>
                            </div>
                            <Badge className={
                              msg.strategy_data.is_backtested
                                ? 'bg-green-500/20 text-green-400'
                                : 'bg-yellow-500/20 text-yellow-400'
                            }>
                              {msg.strategy_data.backtest_status}
                            </Badge>
                          </div>
                          {msg.strategy_data.description && (
                            <p className="text-sm text-gray-300 mb-2">{msg.strategy_data.description}</p>
                          )}
                          {msg.strategy_data.is_backtested && (
                            <div className="grid grid-cols-3 gap-2 text-xs mb-2">
                              {msg.strategy_data.win_rate !== null && msg.strategy_data.win_rate !== undefined && (
                                <div>
                                  <span className="text-gray-400">Win Rate:</span>
                                  <span className="text-white ml-1">{((msg.strategy_data.win_rate || 0) * 100).toFixed(1)}%</span>
                                </div>
                              )}
                              {msg.strategy_data.sharpe_ratio !== null && msg.strategy_data.sharpe_ratio !== undefined && (
                                <div>
                                  <span className="text-gray-400">Sharpe:</span>
                                  <span className="text-white ml-1">{(msg.strategy_data.sharpe_ratio || 0).toFixed(2)}</span>
                                </div>
                              )}
                              {msg.strategy_data.total_trades !== null && (
                                <div>
                                  <span className="text-gray-400">Trades:</span>
                                  <span className="text-white ml-1">{msg.strategy_data.total_trades}</span>
                                </div>
                              )}
                            </div>
                          )}
                          {!msg.strategy_data.is_backtested && (
                            <div className="flex items-center gap-2 text-xs text-yellow-400 mb-2">
                              <AlertCircle className="w-3 h-3" />
                              <span>This strategy has not been backtested by GSIN Brain</span>
                            </div>
                          )}
                          {/* Allow all members (not just owner) to execute strategies posted by owner */}
                          <Button
                            onClick={() => handleExecuteStrategy(msg.strategy_data!.id)}
                            disabled={executingStrategy === msg.strategy_data!.id}
                            className="w-full mt-2 bg-green-600 hover:bg-green-700"
                            size="sm"
                          >
                            {executingStrategy === msg.strategy_data!.id ? (
                              <>
                                <RefreshCw className="w-3 h-3 mr-2 animate-spin" />
                                Executing...
                              </>
                            ) : (
                              <>
                                <Play className="w-3 h-3 mr-2" />
                                Execute Strategy
                              </>
                            )}
                          </Button>
                        </div>
                      )}
                    </div>
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>
              <div className="flex gap-2">
                <form onSubmit={handleSendMessage} className="flex-1 flex gap-2">
                <Input
                    value={messageContent}
                    onChange={(e) => setMessageContent(e.target.value)}
                  placeholder="Type a message..."
                  className="bg-white/5 border-blue-500/20 text-white"
                    disabled={sending}
                  />
                  <Button type="submit" disabled={sending || !messageContent.trim()} className="bg-blue-600 hover:bg-blue-700">
                    <Send className="w-4 h-4" />
                  </Button>
                </form>
                {/* GROUP CHAT STRATEGY FUNCTIONALITY: Strategy upload button for group owner */}
                {isOwner && (
                  <Dialog open={uploadStrategyDialogOpen} onOpenChange={setUploadStrategyDialogOpen}>
                    <DialogTrigger asChild>
                      <Button variant="outline" className="gap-2 bg-purple-500/10 border-purple-500/20 text-purple-400 hover:bg-purple-500/20">
                        <Upload className="w-4 h-4" />
                        Upload Strategy
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="bg-black/90 border-blue-500/20">
                      <DialogHeader>
                        <DialogTitle className="text-white">Upload Strategy to Group</DialogTitle>
                        <DialogDescription className="text-gray-400">
                          Select a strategy to share with the group. Only you can upload strategies.
                        </DialogDescription>
                      </DialogHeader>
                      <div className="space-y-2 max-h-96 overflow-y-auto">
                        {strategies.length === 0 ? (
                          <div className="text-center text-gray-400 py-8">
                            <p>No strategies available. Create a strategy first.</p>
                            <Button
                              onClick={() => router.push('/strategies/upload')}
                              className="mt-4 bg-blue-600 hover:bg-blue-700"
                            >
                              Create Strategy
                            </Button>
                          </div>
                        ) : (
                          strategies.map((strategy) => (
                            <div
                              key={strategy.id}
                              className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                                selectedStrategyId === strategy.id
                                  ? 'border-blue-500 bg-blue-500/10'
                                  : 'border-blue-500/20 bg-white/5 hover:bg-white/10'
                              }`}
                              onClick={() => setSelectedStrategyId(strategy.id)}
                            >
                              <div className="flex items-center justify-between">
                                <div>
                                  <div className="font-semibold text-white">{strategy.name}</div>
                                  {strategy.description && (
                                    <div className="text-sm text-gray-400 mt-1">{strategy.description}</div>
                                  )}
                                </div>
                                <Badge className={
                                  strategy.is_backtested
                                    ? 'bg-green-500/20 text-green-400'
                                    : 'bg-yellow-500/20 text-yellow-400'
                                }>
                                  {strategy.backtest_status}
                                </Badge>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                      <div className="flex gap-2 mt-4">
                        <Button
                          onClick={() => {
                            if (selectedStrategyId) {
                              handleUploadStrategy(selectedStrategyId);
                            }
                          }}
                          disabled={!selectedStrategyId || sending}
                          className="flex-1 bg-blue-600 hover:bg-blue-700"
                        >
                          {sending ? 'Uploading...' : 'Upload Strategy'}
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => {
                            setUploadStrategyDialogOpen(false);
                            setSelectedStrategyId(null);
                          }}
                          className="border-blue-500/20 text-white"
                        >
                          Cancel
                        </Button>
                      </div>
                    </DialogContent>
                  </Dialog>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="members">
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardHeader>
              <CardTitle className="text-white">Group Members ({members.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {members.length === 0 ? (
                <div className="text-center text-gray-400 py-8">No members yet</div>
              ) : (
              <div className="space-y-3">
                  {members.map((member) => {
                    const isMemberOwner = member.user_id === group.owner_id;
                    return (
                      <div
                        key={member.id}
                        className="flex items-center justify-between p-3 bg-white/5 border border-blue-500/20 rounded-lg"
                      >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-semibold">
                            {member.name?.split(' ').map((n) => n[0]).join('').toUpperCase() || 'U'}
                      </div>
                      <div>
                            <div className="font-semibold text-white">
                              {member.name || 'Unknown User'}
                            </div>
                            <div className="text-xs text-gray-400">
                              Joined {format(new Date(member.created_at), 'MMM yyyy')}
                            </div>
                          </div>
                        </div>
                        <Badge
                          className={
                            isMemberOwner
                              ? 'bg-green-500/20 text-green-400'
                              : 'bg-blue-500/20 text-blue-400'
                          }
                        >
                          {isMemberOwner ? 'Owner' : member.role}
                        </Badge>
                      </div>
                    );
                  })}
                    </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
