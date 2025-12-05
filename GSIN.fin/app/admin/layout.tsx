'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Sidebar } from '@/components/sidebar';
import { Topbar } from '@/components/topbar';
import { RobotAssistant } from '@/components/robot-assistant';
import { NotificationsBanner } from '@/components/notifications-banner';
import { ErrorBoundary } from '@/components/error-boundary';
import { useStore } from '@/lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertTriangle } from 'lucide-react';

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const user = useStore((state) => state.user);
  const isAdmin = user?.email?.toLowerCase() === 'patelhetul803@gmail.com';

  useEffect(() => {
    // Redirect non-admin users to dashboard
    if (user && !isAdmin) {
      router.push('/dashboard');
    }
  }, [user, isAdmin, router]);

  // Show access denied message for non-admin users
  if (user && !isAdmin) {
    return (
      <ErrorBoundary>
        <div className="min-h-screen bg-black flex items-center justify-center">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-950/10 via-purple-950/10 to-black" />
          <Card className="bg-black/60 backdrop-blur-xl border-red-500/20 max-w-md w-full mx-4">
            <CardHeader>
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-8 h-8 text-red-400" />
                <CardTitle className="text-white">Access Denied</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-gray-400">
                You do not have permission to access the admin area. Only administrators can view this section.
              </p>
            </CardContent>
          </Card>
        </div>
      </ErrorBoundary>
    );
  }

  // Show loading state while checking user
  if (!user) {
    return (
      <ErrorBoundary>
        <div className="min-h-screen bg-black flex items-center justify-center">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-950/10 via-purple-950/10 to-black" />
          <div className="text-white">Loading...</div>
        </div>
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-black">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-950/10 via-purple-950/10 to-black" />
        <ErrorBoundary>
          <NotificationsBanner />
        </ErrorBoundary>
        <div className="relative flex">
          <ErrorBoundary>
            <Sidebar />
          </ErrorBoundary>
          <div className="flex-1 flex flex-col min-h-screen">
            <ErrorBoundary>
              <Topbar />
            </ErrorBoundary>
            <main className="flex-1 overflow-auto">
              <ErrorBoundary>
                {children}
              </ErrorBoundary>
            </main>
          </div>
        </div>
        <ErrorBoundary>
          <RobotAssistant />
        </ErrorBoundary>
      </div>
    </ErrorBoundary>
  );
}
