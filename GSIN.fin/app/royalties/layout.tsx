import { Sidebar } from '@/components/sidebar';
import { Topbar } from '@/components/topbar';
import { RobotAssistant } from '@/components/robot-assistant';
import { NotificationsBanner } from '@/components/notifications-banner';
import { ErrorBoundary } from '@/components/error-boundary';
import { ComplianceFooter } from '@/components/compliance-footer';

export default function RoyaltiesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-black flex flex-col">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-950/10 via-purple-950/10 to-black" />
        <ErrorBoundary>
          <NotificationsBanner />
        </ErrorBoundary>
        <div className="relative flex flex-1">
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
            <ErrorBoundary>
              <ComplianceFooter />
            </ErrorBoundary>
          </div>
        </div>
        <ErrorBoundary>
          <RobotAssistant />
        </ErrorBoundary>
      </div>
    </ErrorBoundary>
  );
}

