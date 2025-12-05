'use client';

import { useState, useEffect } from 'react';
import { Bell, Search, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useStore } from '@/lib/store';
import { useRouter } from 'next/navigation';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { X } from 'lucide-react';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface Notification {
  id: string;
  title: string;
  body: string;
  read_flag: boolean;
  created_at: string;
}

export function Topbar() {
  const user = useStore((state) => state.user);
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notificationsOpen, setNotificationsOpen] = useState(false);

  // Prevent hydration mismatch by only rendering user data after mount
  useEffect(() => {
    setMounted(true);
    if (user?.id) {
      loadNotifications();
      loadUnreadCount();
      // Poll for new notifications every 30 seconds
      const interval = setInterval(() => {
        loadNotifications();
        loadUnreadCount();
      }, 30000);
      return () => clearInterval(interval);
    }
  }, [user?.id]);

  async function loadNotifications() {
    if (!user?.id) return;
    try {
      const response = await fetch(`${BACKEND_URL}/api/notifications?unread_only=false`, {
        headers: { 'X-User-Id': user.id },
      });
      if (response.ok) {
        const data = await response.json();
        setNotifications(data || []);
      }
    } catch (error) {
      console.error('Error loading notifications:', error);
    }
  }

  async function loadUnreadCount() {
    if (!user?.id) return;
    try {
      const response = await fetch(`${BACKEND_URL}/api/notifications/unread/count`, {
        headers: { 'X-User-Id': user.id },
      });
      if (response.ok) {
        const data = await response.json();
        setUnreadCount(data.count || 0);
      }
    } catch (error) {
      console.error('Error loading unread count:', error);
    }
  }

  async function markAsRead(notificationId: string) {
    if (!user?.id) return;
    try {
      const response = await fetch(`${BACKEND_URL}/api/notifications/${notificationId}/read`, {
        method: 'POST',
        headers: { 'X-User-Id': user.id },
      });
      if (response.ok) {
        // Update local state
        setNotifications(prev => prev.map(n => n.id === notificationId ? { ...n, read_flag: true } : n));
        setUnreadCount(prev => Math.max(0, prev - 1));
      }
    } catch (error) {
      console.error('Error marking notification as read:', error);
    }
  }

  const handleLogout = () => {
    useStore.getState().setUser(null);
    // Clear localStorage
    if (typeof window !== 'undefined') {
      localStorage.removeItem('gsin_user');
    }
    router.push('/login');
  };

  // Get user initials safely - only after mount
  const getUserInitials = () => {
    if (!mounted || !user?.name) return 'U';
    const initials = user.name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
    return initials || 'U';
  };

  return (
    <div className="h-16 bg-black/40 backdrop-blur-xl border-b border-blue-500/10 flex items-center justify-between px-6">
      <div className="flex-1 max-w-xl">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            placeholder="Search strategies, symbols, groups..."
            className="pl-10 bg-white/5 border-blue-500/20 text-white placeholder:text-gray-500"
          />
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* PHASE 2: Notifications bell with unread count */}
        <Popover open={notificationsOpen} onOpenChange={setNotificationsOpen}>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="w-5 h-5 text-gray-400" />
              {unreadCount > 0 && (
                <Badge className="absolute top-0 right-0 h-5 w-5 p-0 flex items-center justify-center bg-red-500 text-white text-xs">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </Badge>
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80 bg-black/90 border-blue-500/20" align="end">
            <CardHeader className="pb-3">
              <CardTitle className="text-white text-lg">Notifications</CardTitle>
            </CardHeader>
            <CardContent className="p-0 max-h-96 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="p-4 text-center text-gray-400 text-sm">
                  No notifications
                </div>
              ) : (
                <div className="space-y-2">
                  {notifications.map((notification) => (
                    <div
                      key={notification.id}
                      className={`p-3 rounded-lg border ${
                        notification.read_flag
                          ? 'bg-white/5 border-blue-500/10'
                          : 'bg-blue-500/10 border-blue-500/30'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1">
                          <div className="font-semibold text-white text-sm mb-1">
                            {notification.title}
                          </div>
                          <div className="text-xs text-gray-300">
                            {notification.body}
                          </div>
                          <div className="text-xs text-gray-500 mt-1">
                            {new Date(notification.created_at).toLocaleDateString()}
                          </div>
                        </div>
                        {!notification.read_flag && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => markAsRead(notification.id)}
                            className="h-6 w-6 p-0"
                          >
                            <X className="w-3 h-3" />
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </PopoverContent>
        </Popover>

        {mounted && user ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-3 hover:bg-white/5 rounded-lg p-2 transition-colors">
                <Avatar className="w-8 h-8">
                  <AvatarFallback className="bg-gradient-to-br from-blue-500 to-purple-600 text-white text-sm">
                    {getUserInitials()}
                  </AvatarFallback>
                </Avatar>
                <div className="text-left">
                  <div className="text-sm font-medium text-white">
                    {user.name || 'User'}
                  </div>
                  <div className="text-xs text-gray-400 capitalize">
                    {user.subscriptionTier || 'user'} Plan
                  </div>
                </div>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem onClick={() => router.push('/profile')}>
                Profile
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => router.push('/subscriptions')}>
                Subscriptions
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleLogout}>
                <LogOut className="w-4 h-4 mr-2" />
                Logout
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          // Show placeholder during SSR or when user is not loaded
          <div className="flex items-center gap-3 rounded-lg p-2">
            <Avatar className="w-8 h-8">
              <AvatarFallback className="bg-gradient-to-br from-blue-500 to-purple-600 text-white text-sm">
                U
              </AvatarFallback>
            </Avatar>
            <div className="text-left">
              <div className="text-sm font-medium text-white">Loading...</div>
              <div className="text-xs text-gray-400">user Plan</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
