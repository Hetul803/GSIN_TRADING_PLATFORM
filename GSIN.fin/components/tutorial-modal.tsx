'use client';

import { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Zap, Shield, Brain, Layers, DollarSign, AlertTriangle, Users, X } from 'lucide-react';
import { apiRequest } from '@/lib/api-client';

interface TutorialModalProps {
  open: boolean;
  onComplete: () => void;
  onSkip: () => void;
}

const tutorialSteps = [
  {
    id: 1,
    title: 'Welcome to GSIN',
    description: 'GSIN (Global Strategy Intelligence Network) is an AI-powered trading platform where you can build, test, and deploy trading strategies.',
    icon: Zap,
    content: (
      <div className="space-y-3 text-sm text-gray-300">
        <p>GSIN combines:</p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>AI-powered Brain for intelligent trade signals</li>
          <li>Strategy marketplace to share and earn royalties</li>
          <li>Paper and real trading modes</li>
          <li>Community groups for collaboration</li>
        </ul>
      </div>
    ),
  },
  {
    id: 2,
    title: 'Paper vs Real Trading',
    description: 'Understand the difference between paper and real trading modes.',
    icon: Shield,
    content: (
      <div className="space-y-3 text-sm text-gray-300">
        <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
          <div className="font-semibold text-blue-400 mb-1">Paper Mode (Recommended for beginners)</div>
          <p>• Simulated trading with real market data</p>
          <p>• No real money at risk</p>
          <p>• Perfect for learning and testing strategies</p>
        </div>
        <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
          <div className="font-semibold text-red-400 mb-1">Real Mode (Advanced users only)</div>
          <p>• Live trades via your connected broker</p>
          <p>• Real money at risk</p>
          <p>• Requires broker connection and careful risk management</p>
        </div>
      </div>
    ),
  },
  {
    id: 3,
    title: 'AI Brain & MCN',
    description: 'The Brain uses Memory Cluster Networks (MCN) to learn from every trade and improve over time.',
    icon: Brain,
    content: (
      <div className="space-y-3 text-sm text-gray-300">
        <p>The AI Brain analyzes:</p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>Market regimes (trending, ranging, volatile)</li>
          <li>Multi-timeframe trends</li>
          <li>Volume confirmation</li>
          <li>Portfolio risk levels</li>
          <li>Historical strategy performance</li>
        </ul>
        <p className="mt-3">Visit the <span className="text-blue-400 font-semibold">Brain</span> tab to see strategy evolution and performance.</p>
      </div>
    ),
  },
  {
    id: 4,
    title: 'Strategy Marketplace & Royalties',
    description: 'Upload strategies, share them, and earn royalties when others profit from them.',
    icon: Layers,
    content: (
      <div className="space-y-3 text-sm text-gray-300">
        <p>Strategy creators earn:</p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li><span className="text-green-400 font-semibold">3%</span> royalties for CREATOR tier</li>
          <li><span className="text-green-400 font-semibold">5%</span> royalties for regular users</li>
          <li>Royalties paid automatically on profitable trades</li>
        </ul>
        <p className="mt-3">View your royalties in the <span className="text-blue-400 font-semibold">Dashboard</span>.</p>
      </div>
    ),
  },
  {
    id: 5,
    title: 'Risk Controls',
    description: 'Configure your trading settings to manage risk and protect your capital.',
    icon: AlertTriangle,
    content: (
      <div className="space-y-3 text-sm text-gray-300">
        <p>Key risk settings:</p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>Maximum position size per trade</li>
          <li>Maximum capital allocation</li>
          <li>Stop loss and take profit levels</li>
          <li>Portfolio exposure limits</li>
        </ul>
        <p className="mt-3">Configure these in <span className="text-blue-400 font-semibold">Settings → Trading</span>.</p>
      </div>
    ),
  },
  {
    id: 6,
    title: 'Groups & Collaboration',
    description: 'Join or create trading groups to collaborate with other traders.',
    icon: Users,
    content: (
      <div className="space-y-3 text-sm text-gray-300">
        <p>Groups allow you to:</p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>Share strategies privately</li>
          <li>Discuss trading ideas</li>
          <li>Invite members via referral codes</li>
          <li>Collaborate on strategy development</li>
        </ul>
        <p className="mt-3">Visit <span className="text-blue-400 font-semibold">Groups</span> to explore or create a group.</p>
      </div>
    ),
  },
];

export function TutorialModal({ open, onComplete, onSkip }: TutorialModalProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [completing, setCompleting] = useState(false);

  const step = tutorialSteps[currentStep];
  const Icon = step?.icon || Zap;
  const progress = ((currentStep + 1) / tutorialSteps.length) * 100;

  const handleNext = () => {
    if (currentStep < tutorialSteps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      handleComplete();
    }
  };

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleComplete = async () => {
    setCompleting(true);
    try {
      await apiRequest('/api/tutorial/complete', {
        method: 'POST',
      });
      onComplete();
    } catch (error) {
      console.error('Error completing tutorial:', error);
      // Still close modal even if API call fails
      onComplete();
    } finally {
      setCompleting(false);
    }
  };

  const handleSkip = async () => {
    // Mark as complete when skipping too
    await handleComplete();
    onSkip();
  };

  if (!step) return null;

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent className="bg-black/95 border-blue-500/20 max-w-2xl">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <DialogTitle className="text-white text-2xl flex items-center gap-2">
              <Icon className="w-6 h-6 text-blue-400" />
              {step.title}
            </DialogTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleSkip}
              className="text-gray-400 hover:text-white"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
          <DialogDescription className="text-gray-400 mt-2">
            {step.description}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4">
          <Progress value={progress} className="mb-6" />
          
          <div className="min-h-[200px]">
            {step.content}
          </div>

          <div className="flex items-center justify-between mt-6 pt-4 border-t border-blue-500/20">
            <div className="text-sm text-gray-400">
              Step {currentStep + 1} of {tutorialSteps.length}
            </div>
            <div className="flex gap-3">
              {currentStep > 0 && (
                <Button
                  variant="outline"
                  onClick={handlePrevious}
                  className="border-blue-500/20 text-white"
                >
                  Previous
                </Button>
              )}
              <Button
                onClick={handleNext}
                disabled={completing}
                className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700"
              >
                {currentStep === tutorialSteps.length - 1
                  ? completing
                    ? 'Completing...'
                    : 'Get Started'
                  : 'Next'}
              </Button>
            </div>
          </div>

          <div className="mt-4 text-center">
            <Button
              variant="ghost"
              onClick={handleSkip}
              className="text-xs text-gray-500 hover:text-gray-400"
            >
              Skip for now
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

