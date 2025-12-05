'use client';

import { useState, useEffect } from 'react';
import { useStore } from '@/lib/store';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { X, Bell, Info, AlertCircle, CheckCircle, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface Notification {
  id: string;
  user_id: string | null;
  title: string;
  body: string;  // PHASE 2: Changed from 'message' to 'body'
  read_flag: boolean;  // PHASE 2: Added
  created_at: string;
  created_by: string | null;  // PHASE 2: Added
}

export function NotificationsBanner() {
  const user = useStore((state) => state.user);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user?.id) {
      loadNotifications();
      // Poll for new notifications every 30 seconds
      const interval = setInterval(loadNotifications, 30000);
      return () => clearInterval(interval);
    }
  }, [user?.id]);

  async function loadNotifications() {
    if (!user?.id) return;
    
    setLoading(true);
    try {
      // PHASE 2: Use new notifications API with unread_only filter
      const response = await fetch(`${BACKEND_URL}/api/notifications?unread_only=true`, {
        headers: { 'X-User-Id': user.id },
      });
      if (response.ok) {
        const data = await response.json();
        // Filter to only unread notifications
        const unread = (data || []).filter((n: Notification) => !n.read_flag);
        setNotifications(unread);
      }
    } catch (error) {
      console.error('Error loading notifications:', error);
    } finally {
      setLoading(false);
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
        // Remove from local state
        setNotifications(prev => prev.filter(n => n.id !== notificationId));
      }
    } catch (error) {
      console.error('Error marking notification as read:', error);
      toast.error('Failed to dismiss notification');
    }
  }

  if (!user?.id || notifications.length === 0) {
    return null;
  }

  const getIcon = (type: string) => {
    switch (type) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-400" />;
      case 'update':
        return <Info className="w-5 h-5 text-blue-400" />;
      default:
        return <Bell className="w-5 h-5 text-blue-400" />;
    }
  };

  const getBorderColor = (type: string) => {
    switch (type) {
      case 'success':
        return 'border-green-500/30 bg-green-500/10';
      case 'warning':
        return 'border-yellow-500/30 bg-yellow-500/10';
      case 'update':
        return 'border-blue-500/30 bg-blue-500/10';
      default:
        return 'border-blue-500/30 bg-blue-500/10';
    }
  };

  return (
    <div className="fixed top-0 left-0 right-0 z-50 p-4 space-y-2">
      {notifications.map((notification) => (
        <Card
          key={notification.id}
          className={`${getBorderColor(notification.notification_type)} border backdrop-blur-xl`}
        >
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              {getIcon(notification.notification_type)}
              <div className="flex-1">
                <h3 className="font-semibold text-white mb-1">{notification.title}</h3>
                <p className="text-sm text-gray-300 whitespace-pre-line">{notification.body}</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => markAsRead(notification.id)}
                className="text-gray-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

