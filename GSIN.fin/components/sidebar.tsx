'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  TrendingUp,
  Layers,
  Users,
  User,
  CreditCard,
  Settings,
  Activity,
  Upload,
  History,
  Zap,
  Shield,
  BarChart3,
  Brain,
  DollarSign,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useStore } from '@/lib/store';
import { LucideIcon } from 'lucide-react';
import { canAccessGroups, canUploadStrategies } from '@/lib/subscription-utils';

type NavigationItem = {
  name: string;
  href?: string;
  icon: LucideIcon;
  adminOnly?: boolean;
  requiresPro?: boolean; // Requires Pro or Creator account
  children?: NavigationItem[];
};

const navigation: NavigationItem[] = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  {
    name: 'Trading',
    icon: TrendingUp,
    children: [
      { name: 'Trading Terminal', href: '/terminal', icon: BarChart3 },
      { name: 'AI Signals', href: '/trading/signals', icon: Zap },
      { name: 'History', href: '/trading/history', icon: History },
      { name: 'Broker Settings', href: '/settings/broker', icon: Settings },
    ],
  },
  {
    name: 'Strategies',
    icon: Layers,
    children: [
      { name: 'Marketplace', href: '/strategies', icon: BarChart3 },
      { name: 'Upload Strategy', href: '/strategies/upload', icon: Upload, requiresPro: true },
    ],
  },
  { name: 'Groups', href: '/groups', icon: Users, requiresPro: true },
  { name: 'Brain', href: '/brain', icon: Brain },
  { name: 'Royalties', href: '/royalties', icon: DollarSign, requiresPro: true },
  { name: 'Profile', href: '/profile', icon: User },
  { name: 'Subscriptions', href: '/subscriptions', icon: CreditCard },
  { name: 'Admin', href: '/admin', icon: Shield, adminOnly: true },
];

export function Sidebar() {
  const pathname = usePathname();
  const user = useStore((state) => state.user);
  const [mounted, setMounted] = useState(false);
  const [subscriptionInfo, setSubscriptionInfo] = useState<any>(null);
  
  // Only check user role on client side to avoid hydration mismatch
  useEffect(() => {
    setMounted(true);
    if (user?.id) {
      loadSubscriptionInfo();
    }
  }, [user?.id]);
  
  async function loadSubscriptionInfo() {
    if (!user?.id) return;
    try {
      const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
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
  
  // Check if user is admin by email (only after mount to avoid hydration issues)
  const isAdmin = mounted && user?.email?.toLowerCase() === 'patelhetul803@gmail.com';
  
  // Check subscription permissions
  const planCode = subscriptionInfo?.planCode || user?.subscriptionTier?.toUpperCase() || 'USER';
  const canAccessGroupsPage = canAccessGroups(planCode);
  const canUpload = canUploadStrategies(planCode);

  return (
    <div className="w-64 h-screen bg-black/40 backdrop-blur-xl border-r border-blue-500/10 flex flex-col">
      <div className="p-6 border-b border-blue-500/10">
        <Link href="/dashboard" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
            <Zap className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="font-bold text-white text-lg group-hover:text-blue-400 transition-colors">
              GSIN
            </div>
            <div className="text-xs text-gray-400">Strategy Intelligence</div>
          </div>
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto p-4 space-y-1">
        {navigation.map((item) => {
          // Hide admin-only items during SSR or if user is not admin
          // This ensures server and client render the same initially
          const shouldHideAdmin = item.adminOnly && (!mounted || !isAdmin);
          
          // Hide items that require Pro/Creator for Starter users
          const shouldHidePro = item.requiresPro && (!mounted || !canAccessGroupsPage);
          const shouldHide = shouldHideAdmin || shouldHidePro;
          
          if (item.children) {
            return (
              <div key={item.name} style={{ display: shouldHide ? 'none' : 'block' }} suppressHydrationWarning>
                <div className="flex items-center gap-3 px-3 py-2 text-sm text-gray-400 font-medium">
                  <item.icon className="w-4 h-4" />
                  {item.name}
                </div>
                <div className="ml-4 space-y-1">
                  {item.children.map((child) => {
                    if (!child.href) return null;
                    // Check if child requires Pro (like Upload Strategy)
                    const childRequiresPro = child.requiresPro && (!mounted || !canUpload);
                    if (childRequiresPro) return null;
                    
                    const isActive = pathname === child.href;
                    return (
                      <Link
                        key={child.href}
                        href={child.href}
                        className={cn(
                          'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                          isActive
                            ? 'bg-blue-500/20 text-blue-400'
                            : 'text-gray-400 hover:text-white hover:bg-white/5'
                        )}
                      >
                        <child.icon className="w-4 h-4" />
                        {child.name}
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          }

          if (!item.href) return null;
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              style={{ display: shouldHide ? 'none' : 'flex' }}
              suppressHydrationWarning
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                isActive
                  ? 'bg-blue-500/20 text-blue-400'
                  : 'text-gray-400 hover:text-white hover:bg-white/5'
              )}
            >
              <item.icon className="w-4 h-4" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-blue-500/10">
        <div className="text-xs text-gray-500 text-center">
          Performance Fee: 3-5%
        </div>
      </div>
    </div>
  );
}
