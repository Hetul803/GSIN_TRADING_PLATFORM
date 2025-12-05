'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useStore } from '@/lib/store';
import { Check, Crown, Zap, Users, Upload } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';

interface SubscriptionPlan {
  id: string;
  planCode: string;
  name: string;
  priceMonthly: number;
  defaultRoyaltyPercent: number;
  description: string;
  isCreatorPlan: boolean;
  isActive: boolean;
}

interface CurrentSubscription {
  userId: string;
  planId: string | null;
  planCode: string | null;
  planName: string | null;
  royaltyPercent: number;
  canUploadStrategies: boolean;
  isCreator: boolean;
}

export default function SubscriptionsPage() {
  const user = useStore((state) => state.user);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [currentSubscription, setCurrentSubscription] = useState<CurrentSubscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [changingPlan, setChangingPlan] = useState<string | null>(null);

  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  useEffect(() => {
    // Load user from localStorage on client side to avoid hydration mismatch
    if (typeof window !== 'undefined' && !user) {
      const stored = localStorage.getItem('gsin_user');
      if (stored) {
        try {
          const userData = JSON.parse(stored);
          useStore.getState().setUser(userData);
        } catch (error) {
          console.error('Error loading user from storage:', error);
        }
      }
    }
    
    loadData();
    
    // Check if user was redirected from canceled payment or successful free plan activation
    // Only access window in useEffect to avoid hydration issues
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get('canceled') === 'true') {
        toast.info('Payment was canceled. You can try again anytime.');
        // Clean up URL
        window.history.replaceState({}, '', '/subscriptions');
      } else if (urlParams.get('success') === 'true') {
        toast.success('Plan activated successfully!');
        // Clean up URL
        window.history.replaceState({}, '', '/subscriptions');
      }
    }
  }, [user?.id]);

  async function loadData() {
    setLoading(true);
    try {
      // Load plans
      const plansResponse = await fetch(`${BACKEND_URL}/api/subscriptions/plans`);
      if (!plansResponse.ok) {
        throw new Error('Failed to fetch plans');
      }
      const plansData = await plansResponse.json();
      setPlans(plansData.plans || []);

      // Load current subscription if user is logged in
      if (user?.id) {
        try {
          const subResponse = await fetch(`${BACKEND_URL}/api/subscriptions/me`, {
            headers: {
              'X-User-Id': user.id,
            },
          });
          if (subResponse.ok) {
            const subData = await subResponse.json();
            setCurrentSubscription(subData);
          }
        } catch (error) {
          console.error('Error loading subscription:', error);
        }
      }
    } catch (error) {
      console.error('Error loading subscription plans:', error);
      toast.error('Failed to load subscription plans');
    } finally {
      setLoading(false);
    }
  }

  const handleChangePlan = async (planId: string) => {
    if (!user?.id) {
      toast.error('Please log in to change your plan');
      return;
    }

    setChangingPlan(planId);
    try {
      // Create Stripe checkout session (or activate free plan)
      const response = await fetch(`${BACKEND_URL}/api/subscriptions/checkout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': user.id,
        },
        body: JSON.stringify({
          planId,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create checkout session');
      }

      const checkoutData = await response.json();
      
      // Handle free plans (no Stripe redirect needed)
      if (checkoutData.is_free) {
        toast.success(`Free plan activated successfully!`);
        // Reload subscription data
        await loadData();
        setChangingPlan(null);
        // Show success message
        window.location.href = checkoutData.checkout_url || '/subscriptions?success=true';
      } else if (checkoutData.checkout_url) {
        // Redirect to Stripe checkout for paid plans
        window.location.href = checkoutData.checkout_url;
      } else {
        throw new Error('No checkout URL received');
      }
    } catch (error: any) {
      console.error('Error creating checkout:', error);
      toast.error(error.message || 'Failed to start checkout');
      setChangingPlan(null);
    }
  };

  const getPlanConfig = (planCode: string) => {
    const configs: Record<string, any> = {
      USER: {
        icon: Users,
        color: 'from-blue-500 to-cyan-500',
        features: [
          'Use strategies from marketplace',
          'Manual trading + AI signals',
          'Basic backtesting',
          'Paper trading unlimited',
          'View-only (cannot upload)',
          'Performance fee: 7% on profitable trades',
        ],
        popular: false,
      },
      USER_PLUS_UPLOAD: {
        icon: Upload,
        color: 'from-purple-500 to-pink-500',
        features: [
          'Everything in User plan',
          'Upload your own strategies',
          'Earn 5% royalties on profitable trades',
          'Strategy marketplace access',
          'Full backtesting suite',
          'Performance fee: 5% on profitable trades',
        ],
        popular: true,
      },
      CREATOR: {
        icon: Crown,
        color: 'from-yellow-500 to-orange-500',
        features: [
          'Everything in User + Upload',
          'Earn 5% royalties on profitable trades',
          'Unlimited group creation',
          'Creator account benefits',
          'Performance fee: 3% on profitable trades',
          'Priority support',
        ],
        popular: false,
      },
    };
    return configs[planCode] || configs.USER;
  };

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white">Loading subscription plans...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="text-center max-w-2xl mx-auto">
        <h1 className="text-4xl font-bold text-white mb-3">Choose Your Plan</h1>
        <p className="text-gray-400 text-lg">
          Unlock powerful features and grow your trading business
        </p>
      </div>

      {currentSubscription && currentSubscription.planId && (
        <div className="max-w-2xl mx-auto">
          <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-white mb-1">Current Plan</h3>
                  <p className="text-gray-400">
                    {currentSubscription.planName} • {currentSubscription.royaltyPercent}% royalty rate
                  </p>
                  {currentSubscription.canUploadStrategies && (
                    <Badge className="mt-2 bg-green-500/20 text-green-400 border-green-500/30">
                      Can Upload Strategies
                    </Badge>
                  )}
                  {currentSubscription.isCreator && (
                    <Badge className="mt-2 ml-2 bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                      Creator Account
                    </Badge>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-7xl mx-auto">
        {plans.map((plan) => {
          const config = getPlanConfig(plan.planCode);
          const Icon = config.icon;
          const isCurrentPlan = currentSubscription?.planId === plan.id;
          const priceInDollars = (plan.priceMonthly / 100).toFixed(2);

          return (
            <Card
              key={plan.id}
              className={`bg-black/60 backdrop-blur-xl border-blue-500/20 relative ${
                config.popular ? 'border-purple-500/40 shadow-xl shadow-purple-500/20' : ''
              } ${isCurrentPlan ? 'ring-2 ring-blue-500' : ''}`}
            >
              {config.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <Badge className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-4">
                    Most Popular
                  </Badge>
                </div>
              )}

              {isCurrentPlan && (
                <div className="absolute -top-3 right-4">
                  <Badge className="bg-blue-500 text-white px-3">
                    Current Plan
                  </Badge>
                </div>
              )}

              <CardHeader className="text-center pb-8">
                <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${config.color} flex items-center justify-center mx-auto mb-4`}>
                  <Icon className="w-8 h-8 text-white" />
                </div>
                <CardTitle className="text-2xl text-white mb-2">{plan.name}</CardTitle>
                <div>
                  {plan.priceMonthly === 0 ? (
                    <div className="space-y-1">
                      <div className="flex items-center justify-center gap-2">
                        <span className="text-2xl font-bold text-gray-500 line-through">$29.99</span>
                        <Badge className="bg-green-500/20 text-green-400 border-green-500/30 text-xs">
                          Limited-time offer
                        </Badge>
                      </div>
                      <div className="text-4xl font-bold text-green-400">$0.00</div>
                      <span className="text-gray-400 text-sm">/month</span>
                    </div>
                  ) : (
                    <>
                      <span className="text-4xl font-bold text-white">${priceInDollars}</span>
                      <span className="text-gray-400">/month</span>
                    </>
                  )}
                </div>
                <p className="text-sm text-gray-500 mt-2">{plan.description}</p>
                {plan.defaultRoyaltyPercent > 0 && (
                  <p className="text-xs text-gray-400 mt-1">
                    {plan.defaultRoyaltyPercent}% royalty rate
                  </p>
                )}
              </CardHeader>

              <CardContent className="space-y-6">
                <ul className="space-y-3">
                  {config.features.map((feature: string, idx: number) => (
                    <li key={idx} className="flex items-start gap-2">
                      <Check className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                      <span className="text-sm text-gray-300">{feature}</span>
                    </li>
                  ))}
                </ul>

                <Button
                  className={`w-full ${
                    isCurrentPlan
                      ? 'bg-gray-700 text-gray-300 cursor-not-allowed'
                      : plan.priceMonthly === 0
                      ? 'bg-green-600 hover:bg-green-700'
                      : 'bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700'
                  }`}
                  onClick={() => !isCurrentPlan && handleChangePlan(plan.id)}
                  disabled={isCurrentPlan || changingPlan === plan.id}
                >
                  {isCurrentPlan
                    ? 'Current Plan'
                    : changingPlan === plan.id
                    ? 'Processing...'
                    : plan.priceMonthly === 0
                    ? 'Free - Activate'
                    : currentSubscription?.planId && plan.priceMonthly > (plans.find(p => p.id === currentSubscription.planId)?.priceMonthly || 0)
                    ? 'Upgrade'
                    : 'Select Plan'}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="max-w-4xl mx-auto mt-8 p-6 bg-black/40 rounded-lg border border-blue-500/20">
        <h3 className="text-lg font-semibold text-white mb-3">Plan Comparison</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-gray-400 mb-2">Upload Strategies</p>
            <p className="text-white">
              {plans.find(p => p.planCode === 'USER')?.planCode === 'USER' && '❌ '}
              {plans.find(p => p.planCode === 'USER_PLUS_UPLOAD')?.planCode === 'USER_PLUS_UPLOAD' && '✅ '}
              {plans.find(p => p.planCode === 'CREATOR')?.planCode === 'CREATOR' && '✅ '}
            </p>
          </div>
          <div>
            <p className="text-gray-400 mb-2">Royalty Rate</p>
            <p className="text-white">
              User: N/A • Upload: 5% • Creator: 3%
            </p>
          </div>
          <div>
            <p className="text-gray-400 mb-2">Private Groups</p>
            <p className="text-white">
              Coming soon (Creator only)
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
