'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { ArrowLeft, Users } from 'lucide-react';
import Link from 'next/link';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';

export default function CreateGroupPage() {
  const router = useRouter();
  const [isPrivate, setIsPrivate] = useState(false);

  const handleCreate = () => {
    toast.success('Group created successfully!');
    router.push('/groups');
  };

  return (
    <div className="p-6 space-y-6">
      <Link href="/groups">
        <Button variant="ghost" className="gap-2 text-gray-400 hover:text-white">
          <ArrowLeft className="w-4 h-4" />
          Back to Groups
        </Button>
      </Link>

      <div>
        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
          <Users className="w-8 h-8" />
          Create New Group
        </h1>
        <p className="text-gray-400">Build a community of traders around your strategies</p>
      </div>

      <div className="max-w-3xl">
        <Card className="bg-black/60 backdrop-blur-xl border-blue-500/20">
          <CardHeader>
            <CardTitle className="text-white">Group Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div>
              <Label className="text-gray-300">Group Name</Label>
              <Input
                placeholder="Elite Traders Club"
                className="mt-2 bg-white/5 border-blue-500/20 text-white"
              />
            </div>

            <div>
              <Label className="text-gray-300">Description</Label>
              <Textarea
                placeholder="Describe your group's focus, trading style, and what members can expect..."
                rows={4}
                className="mt-2 bg-white/5 border-blue-500/20 text-white resize-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-gray-300">Maximum Members</Label>
                <Select defaultValue="100">
                  <SelectTrigger className="mt-2 bg-white/5 border-blue-500/20 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="10">10 members</SelectItem>
                    <SelectItem value="50">50 members</SelectItem>
                    <SelectItem value="100">100 members</SelectItem>
                    <SelectItem value="200">200 members</SelectItem>
                    <SelectItem value="unlimited">Unlimited</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label className="text-gray-300">Monthly Price</Label>
                <Input
                  type="number"
                  placeholder="99.99"
                  className="mt-2 bg-white/5 border-blue-500/20 text-white"
                />
              </div>
            </div>

            <div className="flex items-center justify-between p-4 bg-white/5 border border-blue-500/20 rounded-lg">
              <div>
                <div className="font-medium text-white">Private Group</div>
                <div className="text-sm text-gray-400">Members can only join with invite code</div>
              </div>
              <Switch checked={isPrivate} onCheckedChange={setIsPrivate} />
            </div>

            <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
              <h3 className="font-semibold text-white mb-2">Group Features</h3>
              <ul className="space-y-1 text-sm text-gray-300">
                <li>• Share exclusive strategies with members</li>
                <li>• Group chat and discussions</li>
                <li>• Analytics dashboard for group performance</li>
                <li>• Custom invite codes</li>
                <li>• Revenue sharing options</li>
              </ul>
            </div>

            <div className="flex justify-end gap-3 pt-4">
              <Button
                variant="outline"
                className="bg-white/5 border-blue-500/20 text-white"
                onClick={() => router.push('/groups')}
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreate}
                className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700"
              >
                Create Group
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
