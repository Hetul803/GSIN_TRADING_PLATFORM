'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Search, TrendingUp, Award, Users, Filter, Upload, Layers } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { useStore } from '@/lib/store';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface Strategy {
  id: string;
  name: string;
  description: string | null;
  score: number | null;
  status: string;
  is_proposable: boolean;
  user_id: string;
  last_backtest_at?: string | null;
}

export default function StrategiesPage() {
  const router = useRouter();
  const user = useStore((state) => state.user);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('profitable');
  const [filterVisibility, setFilterVisibility] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (!user?.id) {
      router.push('/login');
      return;
    }
    loadStrategies();
  }, [user?.id, router]);

  async function loadStrategies() {
    if (!user?.id) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/strategies`, {
        headers: { 'X-User-Id': user.id },
      });
      if (response.ok) {
        const data = await response.json();
        setStrategies(data || []);
      }
    } catch (error) {
      console.error('Error loading strategies:', error);
    } finally {
      setLoading(false);
    }
  }

  const filteredStrategies = strategies.filter((strategy) => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      if (!strategy.name.toLowerCase().includes(query) && 
          !(strategy.description || '').toLowerCase().includes(query)) {
        return false;
      }
    }
    return true;
  });

  if (!user?.id) {
    return null;
  }

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-screen">
        <div className="text-white text-lg">Loading strategies...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Strategy Marketplace</h1>
          <p className="text-gray-400">Discover and deploy proven trading strategies</p>
        </div>
        <Link href="/strategies/upload">
          <Button className="gap-2 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700">
            <Upload className="w-4 h-4" />
            Upload Strategy
          </Button>
        </Link>
      </div>

      <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
        <CardContent className="p-6">
          <div className="flex items-center gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                placeholder="Search strategies..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 bg-white/5 border-blue-500/20 text-white"
              />
            </div>
            <Select value={filterVisibility} onValueChange={setFilterVisibility}>
              <SelectTrigger className="w-48 bg-white/5 border-blue-500/20 text-white">
                <SelectValue placeholder="Filter" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Strategies</SelectItem>
                <SelectItem value="public">Public Only</SelectItem>
                <SelectItem value="group">Group Only</SelectItem>
                <SelectItem value="private">My Private</SelectItem>
              </SelectContent>
            </Select>
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="w-48 bg-white/5 border-blue-500/20 text-white">
                <SelectValue placeholder="Sort by" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="profitable">Most Profitable</SelectItem>
                <SelectItem value="used">Most Used</SelectItem>
                <SelectItem value="drawdown">Lowest Drawdown</SelectItem>
                <SelectItem value="sharpe">Highest Sharpe</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {filteredStrategies.length === 0 ? (
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardContent className="p-12 text-center">
            <Layers className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-400 text-lg mb-2">
              {strategies.length === 0 ? 'No strategies yet' : 'No strategies match your search'}
            </p>
            <p className="text-gray-500 text-sm mb-4">
              {strategies.length === 0 
                ? 'Create or upload a strategy to get started'
                : 'Try adjusting your search or filters'}
            </p>
            {strategies.length === 0 && (
              <Link href="/strategies/upload">
                <Button className="bg-gradient-to-r from-blue-500 to-purple-600">
                  Upload Strategy
                </Button>
              </Link>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredStrategies.map((strategy) => (
            <Link key={strategy.id} href={`/strategies/${strategy.id}`}>
              <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20 hover:border-blue-500/40 transition-all cursor-pointer h-full">
                <CardHeader>
                  <div className="flex items-start justify-between mb-2">
                    <CardTitle className="text-white text-lg">{strategy.name}</CardTitle>
                    <Badge className={
                      strategy.status === 'proposable' 
                        ? 'bg-green-500/20 text-green-400' 
                        : strategy.status === 'candidate'
                        ? 'bg-blue-500/20 text-blue-400'
                        : 'bg-gray-500/20 text-gray-400'
                    }>
                      {strategy.status}
                    </Badge>
                  </div>
                  <p className="text-sm text-gray-400 line-clamp-2">{strategy.description || 'No description'}</p>
                  {/* PHASE 1: Show human explanation if available */}
                  {(strategy as any).explanation_human && (
                    <p className="text-xs text-gray-500 mt-2 line-clamp-2">
                      {(strategy as any).explanation_human}
                    </p>
                  )}
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* PHASE 1: Show risk note if available */}
                  {(strategy as any).risk_note && (
                    <div className="p-2 bg-yellow-500/10 border border-yellow-500/20 rounded text-xs">
                      <div className="text-yellow-400 font-semibold mb-1">⚠️ Risk</div>
                      <div className="text-yellow-300/80 line-clamp-2">
                        {(strategy as any).risk_note}
                      </div>
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                      <div className="text-xs text-gray-400 mb-1">Score</div>
                      <div className="text-lg font-bold text-blue-400">
                        {strategy.score ? (strategy.score * 100).toFixed(1) : 'N/A'}%
                      </div>
                    </div>
                    <div className="p-3 bg-purple-500/10 border border-purple-500/20 rounded-lg">
                      <div className="text-xs text-gray-400 mb-1">Status</div>
                      <div className="text-lg font-bold text-purple-400 capitalize">
                        {strategy.status === 'experiment' && !strategy.last_backtest_at ? 'Still Testing' : (strategy.status || 'UNKNOWN')}
                      </div>
                    </div>
                  </div>

                  <Button variant="outline" className="w-full bg-white/5 border-blue-500/20 text-white">
                    View Details
                  </Button>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
