'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertTriangle } from 'lucide-react';
import { apiRequest } from '@/lib/api-client';

export default function DisclaimerPage() {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadDisclaimer() {
      try {
        const data = await apiRequest<{ content: string }>('/api/compliance/disclaimer');
        setContent(data.content || 'Trading disclaimer content not available.');
      } catch (error) {
        console.error('Error loading disclaimer:', error);
        setContent('Trading disclaimer content not available.');
      } finally {
        setLoading(false);
      }
    }
    loadDisclaimer();
  }, []);

  return (
    <div className="min-h-screen bg-black p-6">
      <div className="max-w-4xl mx-auto">
        <Card className="bg-black/60 backdrop-blur-xl border-red-500/20">
          <CardHeader>
            <CardTitle className="text-white text-3xl flex items-center gap-3">
              <AlertTriangle className="w-8 h-8 text-red-400" />
              Trading Disclaimer
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-gray-400">Loading disclaimer...</div>
            ) : (
              <div className="prose prose-invert max-w-none text-gray-300 whitespace-pre-wrap">
                {content}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

