'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Zap } from 'lucide-react';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.push('/login');
  }, [router]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-slate-900 flex items-center justify-center">
      <div className="text-center">
        <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-2xl shadow-blue-500/50 mx-auto mb-6 animate-pulse">
          <Zap className="w-12 h-12 text-white" />
        </div>
        <h1 className="text-2xl font-bold text-white mb-2">GSIN</h1>
        <p className="text-gray-400">Loading...</p>
      </div>
    </div>
  );
}
