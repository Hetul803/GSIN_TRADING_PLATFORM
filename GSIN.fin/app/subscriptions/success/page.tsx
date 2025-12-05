'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CheckCircle, Loader2 } from 'lucide-react';
import { useStore } from '@/lib/store';
import { toast } from 'sonner';

function SubscriptionSuccessContent() {
  const router = useRouter();
  const user = useStore((state) => state.user);
  const [loading, setLoading] = useState(true);
  const [success, setSuccess] = useState(false);
  const [mounted, setMounted] = useState(false);

  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
  
  // Get sessionId only after mount to avoid hydration issues
  // Use window.location instead of useSearchParams to avoid SSR issues
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    // Mark as mounted and get sessionId from URL
    // Only access window after mount to avoid hydration issues
    setMounted(true);
    
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      const id = urlParams.get('session_id');
      setSessionId(id);
    }
  }, []);

  useEffect(() => {
    // Only run after component is mounted and sessionId is set
    if (!mounted || !sessionId) {
      if (mounted && !sessionId) {
        // Only show error after mount to avoid hydration issues
        toast.error('Invalid session ID');
        router.push('/subscriptions');
      }
      return;
    }

    // Wait a moment for webhook to process, then verify subscription
    const verifySubscription = async () => {
      try {
        // Give webhook time to process (2 seconds)
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Fetch current subscription to verify it was updated
        if (user?.id) {
          const response = await fetch(`${BACKEND_URL}/subscriptions/me`, {
            headers: {
              'X-User-Id': user.id,
            },
          });

          if (response.ok) {
            const subData = await response.json();
            setSuccess(true);
            
            // Update user in store
            useStore.getState().setUser({
              ...user,
              subscriptionTier: subData.planCode?.toLowerCase() as any,
            });

            toast.success('Subscription activated successfully!');
          }
        }
      } catch (error) {
        console.error('Error verifying subscription:', error);
        // Still show success page - webhook might have processed it
        setSuccess(true);
      } finally {
        setLoading(false);
      }
    };

    verifySubscription();
  }, [sessionId, user?.id, router, mounted]);

  // Show loading state until mounted and sessionId is available
  if (!mounted || loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-slate-900 flex items-center justify-center">
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20 p-8">
          <CardContent className="flex flex-col items-center gap-4">
            <Loader2 className="w-12 h-12 text-blue-500 animate-spin" />
            <p className="text-white">Processing your payment...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-slate-900 flex items-center justify-center p-6">
      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20 max-w-md w-full">
        <CardContent className="p-8 text-center space-y-6">
          {success ? (
            <>
              <div className="flex justify-center">
                <CheckCircle className="w-16 h-16 text-green-500" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white mb-2">
                  Payment Successful!
                </h1>
                <p className="text-gray-400">
                  Your subscription has been activated. You now have access to all plan features.
                </p>
              </div>
              <div className="space-y-3">
                <Button
                  onClick={() => router.push('/dashboard')}
                  className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                >
                  Go to Dashboard
                </Button>
                <Button
                  onClick={() => router.push('/subscriptions')}
                  variant="outline"
                  className="w-full border-blue-500/20 text-gray-300 hover:bg-blue-500/10"
                >
                  View Subscription Details
                </Button>
              </div>
            </>
          ) : (
            <>
              <div className="flex justify-center">
                <Loader2 className="w-16 h-16 text-blue-500 animate-spin" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white mb-2">
                  Processing...
                </h1>
                <p className="text-gray-400">
                  Please wait while we confirm your payment.
                </p>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Client-only wrapper to prevent hydration issues
function ClientOnlySubscriptionSuccess() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-slate-900 flex items-center justify-center">
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20 p-8">
          <CardContent className="flex flex-col items-center gap-4">
            <Loader2 className="w-12 h-12 text-blue-500 animate-spin" />
            <p className="text-white">Loading...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return <SubscriptionSuccessContent />;
}

export default function SubscriptionSuccessPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-slate-900 flex items-center justify-center">
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20 p-8">
          <CardContent className="flex flex-col items-center gap-4">
            <Loader2 className="w-12 h-12 text-blue-500 animate-spin" />
            <p className="text-white">Loading...</p>
          </CardContent>
        </Card>
      </div>
    }>
      <ClientOnlySubscriptionSuccess />
    </Suspense>
  );
}

