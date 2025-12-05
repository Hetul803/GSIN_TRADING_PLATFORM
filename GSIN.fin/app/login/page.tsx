'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Zap, Mail, Bot, TrendingUp, Users, Layers } from 'lucide-react';
import { useStore } from '@/lib/store';
import { mockUser } from '@/lib/mock-data';
import Link from 'next/link';
import { toast } from 'sonner';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mounted, setMounted] = useState(false);
  const [showRobotTooltip, setShowRobotTooltip] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!email || !password) {
      toast.error('Please enter both email and password');
      return;
    }
    
    const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    
    try {
      // Login with email and password
      const loginResponse = await fetch(`${BACKEND_URL}/users/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
        }),
      });
      
      if (loginResponse.ok) {
        const loginData = await loginResponse.json();
        // Store JWT token if provided
        if (typeof window !== 'undefined' && loginData.access_token) {
          localStorage.setItem('gsin_token', loginData.access_token);
        }
        
        const userData = loginData.user || loginData; // Handle both response formats
        // Check if this is a new user (first login) or returning user
        const checkResponse = await fetch(`${BACKEND_URL}/users/check-email?email=${encodeURIComponent(email)}`);
        const checkData = await checkResponse.json();
        const isNewUser = checkData.isNewUser || false;
        
        const user = {
          id: userData.id,
          email: userData.email,
          name: userData.name || 'User',
          role: userData.role, // Store user role from backend
          subscriptionTier: userData.subscriptionTier.toLowerCase() as any,
          equity: 0, // TODO: Fetch from backend
          paperEquity: 0,
          realEquity: 0,
          isNewUser: isNewUser,
        };
        useStore.getState().setUser(user);
        
        // Reset auto-logout timer
        if (typeof window !== 'undefined') {
          // Reset timer on login
          const resetTimer = () => {
            if (typeof window !== 'undefined') {
              const timer = setTimeout(() => {
                useStore.getState().setUser(null);
                window.location.href = '/login';
              }, 30 * 60 * 1000); // 30 minutes
              // Store timer ID in localStorage to clear on next login
              localStorage.setItem('gsin_logout_timer', timer.toString());
            }
          };
          // Clear any existing timer
          const existingTimer = localStorage.getItem('gsin_logout_timer');
          if (existingTimer) {
            clearTimeout(parseInt(existingTimer));
          }
          resetTimer();
        }
        
        router.push('/dashboard');
      } else {
        const errorData = await loginResponse.json();
        toast.error(errorData.detail || 'Invalid email or password');
      }
    } catch (error) {
      console.error('Login error:', error);
      toast.error('Login failed. Please try again.');
    }
  };

  const handleOAuthLogin = async (provider: string) => {
    const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '868233570155-9l27vih6hboheqtcv0sjtkisotj6cktp.apps.googleusercontent.com';
    
    if (provider === 'google' && GOOGLE_CLIENT_ID) {
      // Real Google OAuth flow
      try {
        // Get OAuth URL from backend
        const response = await fetch(`${BACKEND_URL}/api/auth/oauth/google/authorize`, {
          method: 'GET',
        });
        
        if (response.ok) {
          const data = await response.json();
          // Redirect to Google OAuth
          if (data.authorization_url) {
            window.location.href = data.authorization_url;
          } else {
            throw new Error('No authorization URL received');
          }
        } else {
          // Fallback: Direct Google OAuth redirect
          // Use the current origin for redirect URI (must match Google Cloud Console)
          const redirectUri = `${window.location.origin}/api/auth/oauth/callback`;
          const scope = 'openid email profile';
          const googleAuthUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${GOOGLE_CLIENT_ID}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=code&scope=${encodeURIComponent(scope)}&access_type=offline&prompt=consent`;
          console.log('Redirecting to Google OAuth with redirect_uri:', redirectUri);
          window.location.href = googleAuthUrl;
        }
      } catch (error) {
        console.error('OAuth error:', error);
        toast.error('OAuth sign in failed. Please try again.');
      }
    } else {
      // Mock OAuth for development (when Google Client ID not configured)
      try {
        const mockOAuthData = {
          provider: 'google',
          provider_id: `mock_${provider}_${Date.now()}`,
          email: `user_${Date.now()}@${provider}.com`,
          name: `User from ${provider}`,
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
          toast.error(errorData.detail || 'OAuth sign in failed');
        }
      } catch (error) {
        console.error('OAuth error:', error);
        toast.error('OAuth sign in failed. Please try again.');
      }
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-slate-900 relative overflow-hidden flex items-center justify-center lg:justify-start">
      <AnimatedCandlestickBackground />

      <div className="container mx-auto px-4 lg:px-8 relative z-10 grid lg:grid-cols-2 gap-12 items-center min-h-screen py-12">
        <div className={`space-y-8 transition-all duration-1000 ${mounted ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-10'}`}>
          <div className="flex items-center gap-4 mb-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-2xl shadow-blue-500/50 animate-float">
              <Zap className="w-10 h-10 text-white" />
            </div>
            <div>
              <div className="text-3xl lg:text-4xl font-bold text-white">GSIN</div>
              <div className="text-sm text-blue-400">Strategy Intelligence</div>
            </div>
          </div>

          <div>
            <h1 className="text-4xl lg:text-6xl font-bold text-white mb-4 leading-tight">
              Global Strategy Intelligence Network
            </h1>
            <p className="text-xl text-gray-300 mb-6">
              Build, Trade, and Earn Royalties from Strategies.
            </p>
            <p className="text-gray-400 text-lg">
              AI-powered trading Brain with real data, backtests, and profit-sharing.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <div className="px-4 py-2 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-300 text-sm font-medium flex items-center gap-2 hover:bg-blue-500/20 transition-colors">
              <TrendingUp className="w-4 h-4" />
              Paper & Real Trading
            </div>
            <div className="px-4 py-2 rounded-full bg-purple-500/10 border border-purple-500/30 text-purple-300 text-sm font-medium flex items-center gap-2 hover:bg-purple-500/20 transition-colors">
              <Layers className="w-4 h-4" />
              Strategy Marketplace
            </div>
            <div className="px-4 py-2 rounded-full bg-green-500/10 border border-green-500/30 text-green-300 text-sm font-medium flex items-center gap-2 hover:bg-green-500/20 transition-colors">
              <Users className="w-4 h-4" />
              Trading Communities
            </div>
          </div>

          <div className="pt-8 border-t border-blue-500/20">
            <p className="text-gray-500 text-sm">
              Trusted by 12,000+ traders worldwide
            </p>
            <div className="flex items-center gap-4 mt-3">
              <div className="flex -space-x-2">
                {[1, 2, 3, 4].map((i) => (
                  <div
                    key={i}
                    className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 border-2 border-slate-900 flex items-center justify-center text-white text-xs font-semibold"
                  >
                    {String.fromCharCode(65 + i)}
                  </div>
                ))}
              </div>
              <div className="text-yellow-400 text-sm flex items-center gap-1">
                <span>★★★★★</span>
                <span className="text-gray-400 ml-1">4.9/5</span>
              </div>
            </div>
          </div>
        </div>

        <Card className={`bg-black/40 backdrop-blur-2xl border border-blue-500/20 shadow-2xl hover:shadow-blue-500/20 hover:border-blue-500/40 transition-all duration-500 ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}>
          <CardHeader>
            <CardTitle className="text-white text-center text-2xl">Sign In to GSIN</CardTitle>
            <p className="text-center text-gray-400 text-sm mt-2">Access your trading dashboard</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
              <Button
                onClick={() => handleOAuthLogin('google')}
                variant="outline"
                className="w-full bg-white/5 border-blue-500/20 text-white hover:bg-white/10 hover:-translate-y-0.5 hover:shadow-lg transition-all duration-200"
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
                Continue with Google
              </Button>

            </div>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-blue-500/20" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-black px-2 text-gray-400">Or continue with email</span>
              </div>
            </div>

            <form onSubmit={handleLogin} className="space-y-4">
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
                className="w-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-blue-500/50 transition-all duration-200"
              >
                <Mail className="w-4 h-4 mr-2" />
                Sign In with Email
              </Button>
            </form>

            <div className="text-center text-sm">
              <Link href="/forgot-password" className="text-blue-400 hover:text-blue-300 transition-colors">
                Forgot password?
              </Link>
            </div>

            <div className="text-center text-sm text-gray-400">
              Don't have an account?{' '}
              <Link href="/register" className="text-blue-400 hover:text-blue-300 transition-colors">
                Sign up
              </Link>
            </div>

            <div className="pt-4 border-t border-blue-500/10">
              <p className="text-center text-xs text-gray-500">
                Powered by GSIN Brain · Performance fees 3–5% based on plan
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div
        className="fixed bottom-6 right-6 z-50 group"
        onMouseEnter={() => setShowRobotTooltip(true)}
        onMouseLeave={() => setShowRobotTooltip(false)}
      >
        {showRobotTooltip && (
          <div className="absolute bottom-full right-0 mb-3 w-64 p-4 bg-black/90 backdrop-blur-xl border border-blue-500/30 rounded-lg shadow-2xl animate-in slide-in-from-bottom-2">
            <p className="text-sm text-white font-medium mb-1">Hello, I'm the GSIN Brain 🧠</p>
            <p className="text-xs text-gray-400">I learn from every trade and help you make smarter decisions.</p>
          </div>
        )}
        <div className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-2xl hover:shadow-blue-500/50 hover:scale-110 transition-all duration-300 cursor-pointer animate-float">
          <Bot className="w-8 h-8 text-white" />
        </div>
      </div>

      <style jsx>{`
        @keyframes float {
          0%, 100% {
            transform: translateY(0px) rotate(0deg);
          }
          50% {
            transform: translateY(-10px) rotate(5deg);
          }
        }

        .animate-float {
          animation: float 3s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}

function AnimatedCandlestickBackground() {
  const candlesticks = Array.from({ length: 15 }, (_, i) => ({
    id: i,
    height: Math.random() * 60 + 40,
    top: Math.random() * 100,
    left: (i / 15) * 100,
    delay: Math.random() * 5,
    isGreen: Math.random() > 0.5,
  }));

  const lines = Array.from({ length: 8 }, (_, i) => ({
    id: i,
    top: (i / 8) * 100,
    delay: i * 0.5,
  }));

  return (
    <div className="absolute inset-0 overflow-hidden opacity-10">
      <div className="absolute inset-0">
        {candlesticks.map((candle) => (
          <div
            key={candle.id}
            className="absolute w-2"
            style={{
              left: `${candle.left}%`,
              top: `${candle.top}%`,
              height: `${candle.height}px`,
              animation: `candleGlow 4s ease-in-out infinite`,
              animationDelay: `${candle.delay}s`,
            }}
          >
            <div className={`w-full h-full ${candle.isGreen ? 'bg-green-500/40' : 'bg-red-500/40'} rounded-sm`} />
            <div className={`absolute left-1/2 -translate-x-1/2 w-0.5 h-8 -top-8 ${candle.isGreen ? 'bg-green-500/30' : 'bg-red-500/30'}`} />
            <div className={`absolute left-1/2 -translate-x-1/2 w-0.5 h-8 -bottom-8 ${candle.isGreen ? 'bg-green-500/30' : 'bg-red-500/30'}`} />
          </div>
        ))}
      </div>

      <svg className="absolute inset-0 w-full h-full">
        {lines.map((line) => (
          <line
            key={line.id}
            x1="0"
            y1={`${line.top}%`}
            x2="100%"
            y2={`${line.top + (Math.random() - 0.5) * 20}%`}
            stroke="url(#lineGradient)"
            strokeWidth="1"
            className="animate-pulse"
            style={{ animationDelay: `${line.delay}s`, animationDuration: '3s' }}
          />
        ))}
        <defs>
          <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity="0" />
            <stop offset="50%" stopColor="#3b82f6" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
          </linearGradient>
        </defs>
      </svg>

      <div className="absolute inset-0">
        {Array.from({ length: 30 }).map((_, i) => (
          <div
            key={i}
            className="absolute w-1 h-1 bg-blue-400/30 rounded-full"
            style={{
              top: `${Math.random() * 100}%`,
              left: `${Math.random() * 100}%`,
              animation: `float ${Math.random() * 10 + 10}s infinite ease-in-out`,
              animationDelay: `${Math.random() * 5}s`,
            }}
          />
        ))}
      </div>

      <style jsx>{`
        @keyframes candleGlow {
          0%, 100% { opacity: 0.4; transform: scaleY(1); }
          50% { opacity: 0.8; transform: scaleY(1.1); }
        }
      `}</style>
    </div>
  );
}
