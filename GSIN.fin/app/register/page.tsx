'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Zap, Mail } from 'lucide-react';
import { useStore } from '@/lib/store';
import { mockUser } from '@/lib/mock-data';
import Link from 'next/link';
import { toast } from 'sonner';

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!email || !password || !name) {
      toast.error('Please fill in all fields');
      return;
    }
    
    if (password.length < 8) {
      toast.error('Password must be at least 8 characters long');
      return;
    }
    
    const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    
    try {
      // Register user with password (password will be hashed on backend)
      const response = await fetch(`${BACKEND_URL}/users/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password, // Password is sent securely and hashed on backend
          name,
        }),
      });
      
      if (response.ok) {
        const registerData = await response.json();
        // Store JWT token if provided
        if (typeof window !== 'undefined' && registerData.access_token) {
          localStorage.setItem('gsin_token', registerData.access_token);
        }
        
        const userData = registerData.user || registerData; // Handle both response formats
        // New user registration - mark as new user
        useStore.getState().setUser({
          id: userData.id,
          email: userData.email,
          name: userData.name || name,
          role: userData.role, // Store user role from backend
          subscriptionTier: userData.subscriptionTier.toLowerCase() as any,
          equity: 0,
          paperEquity: 0,
          realEquity: 0,
          isNewUser: registerData.requires_verification !== false, // New user if verification required
        });
        
        if (registerData.requires_verification) {
          toast.info('Please check your email to verify your account');
        }
        router.push('/dashboard');
      } else {
        const errorData = await response.json();
        toast.error(errorData.detail || 'Registration failed. Please try again.');
      }
    } catch (error) {
      console.error('Registration error:', error);
      toast.error('Registration failed. Please try again.');
      // Don't proceed to dashboard on error
    }
  };

  const handleOAuthRegister = async (provider: string) => {
    const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    
    // For now, we'll use a mock OAuth flow since OAuth providers aren't fully configured
    // In production, this would redirect to the OAuth provider (Google/GitHub/Twitter)
    // and then redirect back with an authorization code
    
    try {
      // Mock OAuth data - in production, this comes from Google OAuth provider callback
      const mockOAuthData = {
        provider: 'google', // Only Google is supported
        provider_id: `mock_google_${Date.now()}`, // Mock provider ID
        email: `user_${Date.now()}@gmail.com`, // Mock email
        name: `User from Google`,
      };
      
      const response = await fetch(`${BACKEND_URL}/api/auth/oauth/callback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(mockOAuthData),
      });
      
      if (response.ok) {
        const data = await response.json();
        // Store JWT token
        if (typeof window !== 'undefined' && data.access_token) {
          localStorage.setItem('gsin_token', data.access_token);
        }
        
        useStore.getState().setUser({
          id: data.user.id,
          email: data.user.email,
          name: data.user.name || 'User',
          role: data.user.role,
          subscriptionTier: data.user.subscriptionTier.toLowerCase() as any,
          equity: 0,
          paperEquity: 0,
          realEquity: 0,
          isNewUser: data.is_new_user,
        });
        
        toast.success(data.is_new_user ? 'Account created successfully!' : 'Signed in successfully!');
        router.push('/dashboard');
      } else {
        const errorData = await response.json();
        toast.error(errorData.detail || 'OAuth sign up failed');
      }
    } catch (error) {
      console.error('OAuth error:', error);
      toast.error('OAuth sign up failed. Please try again.');
    }
  };

  return (
    <div className="min-h-screen bg-black relative overflow-hidden flex items-center justify-center">
      <div className="absolute inset-0 bg-gradient-to-br from-blue-950/20 via-purple-950/20 to-black" />

      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-20 left-20 w-72 h-72 bg-blue-500/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-20 right-20 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
      </div>

      <div className="relative z-10 w-full max-w-md px-4">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center animate-pulse">
              <Zap className="w-10 h-10 text-white" />
            </div>
          </div>
          <h1 className="text-4xl font-bold text-white mb-2">
            Join GSIN
          </h1>
          <p className="text-gray-400 text-lg">
            Start building and trading strategies today
          </p>
        </div>

        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20 shadow-2xl">
          <CardHeader>
            <CardTitle className="text-white text-center">Create Account</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
              <Button
                onClick={() => handleOAuthRegister('google')}
                variant="outline"
                className="w-full bg-white/5 border-blue-500/20 text-white hover:bg-white/10"
              >
                <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                  <path
                    fill="currentColor"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="currentColor"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  />
                </svg>
                Sign up with Google
              </Button>

            </div>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-blue-500/20" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-black px-2 text-gray-400">Or sign up with email</span>
              </div>
            </div>

            <form onSubmit={handleRegister} className="space-y-4">
              <div>
                <Label className="text-gray-300">Full Name</Label>
                <Input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Alex Chen"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  required
                />
              </div>

              <div>
                <Label className="text-gray-300">Email</Label>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="trader@gsin.trade"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  required
                />
              </div>

              <div>
                <Label className="text-gray-300">Password</Label>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                  required
                />
              </div>

              <Button
                type="submit"
                className="w-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700"
              >
                <Mail className="w-4 h-4 mr-2" />
                Create Account
              </Button>
            </form>

            <div className="text-center text-sm text-gray-400">
              Already have an account?{' '}
              <Link href="/login" className="text-blue-400 hover:text-blue-300">
                Sign in
              </Link>
            </div>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-gray-500 mt-6">
          By creating an account, you agree to GSIN's Terms of Service and Privacy Policy
        </p>
      </div>
    </div>
  );
}
