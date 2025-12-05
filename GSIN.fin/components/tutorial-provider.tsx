'use client';

import { useEffect, useState } from 'react';
import { useStore } from '@/lib/store';
import { TutorialModal } from './tutorial-modal';
import { apiRequest } from '@/lib/api-client';

export function TutorialProvider({ children }: { children: React.ReactNode }) {
  const user = useStore((state) => state.user);
  const [showTutorial, setShowTutorial] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    async function checkTutorialStatus() {
      if (!user?.id) {
        setChecking(false);
        return;
      }

      try {
        const data = await apiRequest<{ has_seen_tutorial: boolean }>('/api/tutorial/status');
        if (!data.has_seen_tutorial) {
          setShowTutorial(true);
        }
      } catch (error) {
        console.error('Error checking tutorial status:', error);
        // Don't show tutorial if check fails
      } finally {
        setChecking(false);
      }
    }

    checkTutorialStatus();
  }, [user?.id]);

  const handleComplete = () => {
    setShowTutorial(false);
  };

  const handleSkip = () => {
    setShowTutorial(false);
  };

  if (checking) {
    return <>{children}</>;
  }

  return (
    <>
      {children}
      <TutorialModal
        open={showTutorial}
        onComplete={handleComplete}
        onSkip={handleSkip}
      />
    </>
  );
}

