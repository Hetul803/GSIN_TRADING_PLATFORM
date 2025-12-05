'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Shield } from 'lucide-react';
import { apiRequest } from '@/lib/api-client';

export default function PrivacyPage() {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadPrivacy() {
      try {
        const data = await apiRequest<{ content: string }>('/api/compliance/privacy');
        setContent(data.content || 'Privacy policy content not available.');
      } catch (error) {
        console.error('Error loading privacy policy:', error);
        setContent('Privacy policy content not available.');
      } finally {
        setLoading(false);
      }
    }
    loadPrivacy();
  }, []);

  return (
    <div className="min-h-screen bg-black p-6">
      <div className="max-w-4xl mx-auto">
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white text-3xl flex items-center gap-3">
              <Shield className="w-8 h-8 text-blue-400" />
              Privacy Policy
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-gray-400">Loading privacy policy...</div>
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

