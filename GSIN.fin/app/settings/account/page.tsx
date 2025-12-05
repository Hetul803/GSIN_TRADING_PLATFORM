'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useStore } from '@/lib/store';
import { ArrowLeft, Lock } from 'lucide-react';
import { toast } from 'sonner';
import Link from 'next/link';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export default function AccountSettingsPage() {
  const router = useRouter();
  const user = useStore((state) => state.user);
  const [mounted, setMounted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  useEffect(() => {
    setMounted(true);
    if (!user?.id) {
      router.push('/login');
    }
  }, [user?.id, router]);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!user?.id) {
      toast.error('Please log in');
      return;
    }

    if (!currentPassword || !newPassword || !confirmPassword) {
      toast.error('Please fill in all fields');
      return;
    }

    if (newPassword !== confirmPassword) {
      toast.error('New passwords do not match');
      return;
    }

    if (newPassword.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/auth/change-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': user.id,
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      if (response.ok) {
        toast.success('Password changed successfully');
        setCurrentPassword('');
        setNewPassword('');
        setConfirmPassword('');
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to change password');
      }
    } catch (error: any) {
      console.error('Error changing password:', error);
      toast.error(error.message || 'Failed to change password');
    } finally {
      setLoading(false);
    }
  };

  if (!mounted) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white text-lg">Loading...</div>
      </div>
    );
  }

  if (!user?.id) {
    return null;
  }

  return (
    <div className="p-6 space-y-6" suppressHydrationWarning>
      <div className="flex items-center gap-4">
        <Link href="/profile">
          <Button variant="ghost" className="gap-2 text-gray-400 hover:text-white">
            <ArrowLeft className="w-4 h-4" />
            Back to Profile
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold text-white">Account Settings</h1>
          <p className="text-gray-400">Manage your account security and preferences</p>
        </div>
      </div>

      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Lock className="w-5 h-5 text-blue-400" />
            Change Password
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleChangePassword} className="space-y-4">
            <div>
              <Label className="text-gray-300">Current Password</Label>
              <Input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="••••••••"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
                required
              />
            </div>

            <div>
              <Label className="text-gray-300">New Password</Label>
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="••••••••"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
                required
                minLength={8}
              />
              <p className="text-xs text-gray-400 mt-1">Must be at least 8 characters</p>
            </div>

            <div>
              <Label className="text-gray-300">Confirm New Password</Label>
              <Input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
                required
                minLength={8}
              />
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {loading ? 'Changing...' : 'Change Password'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

