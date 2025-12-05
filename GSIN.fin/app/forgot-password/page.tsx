'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Mail, ArrowLeft, CheckCircle } from 'lucide-react';
import Link from 'next/link';
import { toast } from 'sonner';

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  const handleSendOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!email) {
      toast.error('Please enter your email address');
      return;
    }
    
    setLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/auth/send-otp`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          purpose: 'password_reset',
        }),
      });
      
      if (response.ok) {
        setOtpSent(true);
        toast.success('OTP code sent to your email');
      } else {
        const errorData = await response.json();
        // Don't reveal if email exists (security)
        toast.success('If an account exists, an OTP code has been sent to your email');
        setOtpSent(true); // Show OTP form anyway
      }
    } catch (error) {
      console.error('Send OTP error:', error);
      toast.error('Failed to send OTP. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!otpCode || !newPassword || !confirmPassword) {
      toast.error('Please fill in all fields');
      return;
    }
    
    if (newPassword.length < 8) {
      toast.error('Password must be at least 8 characters long');
      return;
    }
    
    if (newPassword !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }
    
    setLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/auth/reset-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          otp_code: otpCode,
          new_password: newPassword,
        }),
      });
      
      if (response.ok) {
        toast.success('Password reset successfully! You can now sign in.');
        router.push('/login');
      } else {
        const errorData = await response.json();
        toast.error(errorData.detail || 'Failed to reset password');
      }
    } catch (error) {
      console.error('Reset password error:', error);
      toast.error('Failed to reset password. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-slate-900 relative overflow-hidden flex items-center justify-center">
      <div className="absolute inset-0 bg-gradient-to-br from-blue-950/20 via-purple-950/20 to-black" />

      <div className="relative z-10 w-full max-w-md px-4">
        <Link href="/login">
          <Button variant="ghost" className="mb-6 text-gray-400 hover:text-white">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Sign In
          </Button>
        </Link>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20 shadow-2xl">
          <CardHeader>
            <CardTitle className="text-white text-center text-2xl">Reset Password</CardTitle>
            <p className="text-center text-gray-400 text-sm mt-2">
              {otpSent ? 'Enter the OTP code sent to your email' : 'Enter your email to receive a reset code'}
            </p>
          </CardHeader>
          <CardContent>
            {!otpSent ? (
              <form onSubmit={handleSendOTP} className="space-y-4">
                <div>
                  <Label className="text-gray-300">Email Address</Label>
                  <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="trader@gsin.trade"
                    className="mt-2 bg-white/5 border-blue-500/20 text-white"
                    required
                  />
                </div>

                <Button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700"
                >
                  <Mail className="w-4 h-4 mr-2" />
                  {loading ? 'Sending...' : 'Send Reset Code'}
                </Button>
              </form>
            ) : (
              <form onSubmit={handleResetPassword} className="space-y-4">
                <div>
                  <Label className="text-gray-300">Email</Label>
                  <Input
                    type="email"
                    value={email}
                    disabled
                    className="mt-2 bg-white/5 border-blue-500/20 text-gray-500"
                  />
                </div>

                <div>
                  <Label className="text-gray-300">OTP Code</Label>
                  <Input
                    type="text"
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    placeholder="123456"
                    className="mt-2 bg-white/5 border-blue-500/20 text-white text-center text-2xl tracking-widest"
                    maxLength={6}
                    required
                  />
                  <p className="text-xs text-gray-500 mt-1">Enter the 6-digit code sent to your email</p>
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
                  className="w-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700"
                >
                  <CheckCircle className="w-4 h-4 mr-2" />
                  {loading ? 'Resetting...' : 'Reset Password'}
                </Button>

                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setOtpSent(false);
                    setOtpCode('');
                    setNewPassword('');
                    setConfirmPassword('');
                  }}
                  className="w-full text-gray-400 hover:text-white"
                >
                  Use a different email
                </Button>
              </form>
            )}

            <div className="text-center text-sm text-gray-400 mt-6">
              Remember your password?{' '}
              <Link href="/login" className="text-blue-400 hover:text-blue-300 transition-colors">
                Sign in
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

