'use client';

import { Bot, X } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';

export function RobotAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [message] = useState('Welcome to GSIN!');

  const tips = [
    'Try uploading your first strategy in the Marketplace!',
    'Enable paper trading to test strategies risk-free.',
    'Check out the Brain signals for AI-powered trade ideas.',
  ];

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {isOpen && (
        <div className="mb-4 w-80 rounded-lg border border-blue-500/20 bg-black/90 backdrop-blur-xl p-4 shadow-2xl animate-in slide-in-from-bottom-2">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center animate-pulse">
                <Bot className="w-6 h-6 text-white" />
              </div>
              <div>
                <div className="font-semibold text-white">GSIN Assistant</div>
                <div className="text-xs text-gray-400">Always here to help</div>
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => setIsOpen(false)}
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
          <div className="space-y-3">
            <div className="text-sm text-gray-300 bg-blue-500/10 rounded-lg p-3 border border-blue-500/20">
              {message}
            </div>
            <div className="text-xs text-gray-400">Quick tips:</div>
            <div className="space-y-2">
              {tips.map((tip, i) => (
                <div
                  key={i}
                  className="w-full text-left text-xs text-gray-400 p-2 rounded"
                >
                  • {tip}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-2xl hover:shadow-blue-500/50 transition-all hover:scale-110 animate-bounce"
        style={{ animationDuration: '3s' }}
      >
        {isOpen ? (
          <X className="w-8 h-8 text-white" />
        ) : (
          <Bot className="w-8 h-8 text-white" />
        )}
      </button>
    </div>
  );
}
