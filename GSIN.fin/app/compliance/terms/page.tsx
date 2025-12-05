'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FileText } from 'lucide-react';
import { apiRequest } from '@/lib/api-client';

export default function TermsPage() {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadTerms() {
      try {
        const data = await apiRequest<{ content: string }>('/api/compliance/terms');
        setContent(data.content || 'Terms of service content not available.');
      } catch (error) {
        console.error('Error loading terms:', error);
        setContent('Terms of service content not available.');
      } finally {
        setLoading(false);
      }
    }
    loadTerms();
  }, []);

  return (
    <div className="min-h-screen bg-black p-6">
      <div className="max-w-4xl mx-auto">
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white text-3xl flex items-center gap-3">
              <FileText className="w-8 h-8 text-blue-400" />
              Terms of Service
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-gray-400">Loading terms of service...</div>
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

