'use client';

import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Checkbox } from '@/components/ui/checkbox';
import { AlertTriangle, FileText, Shield, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { apiRequest } from '@/lib/api-client';
import { useStore } from '@/lib/store';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface Agreement {
  type: string;
  version: string;
  title: string;
  content: string;
}

interface AgreementStatus {
  terms: boolean;
  privacy: boolean;
  risk_disclosure: boolean;
}

export function AgreementModal() {
  const user = useStore((state) => state.user);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [accepting, setAccepting] = useState(false);
  const [agreements, setAgreements] = useState<Agreement[]>([]);
  const [accepted, setAccepted] = useState<AgreementStatus>({
    terms: false,
    privacy: false,
    risk_disclosure: false,
  });

  useEffect(() => {
    if (!user?.id) return;
    checkAgreements();
  }, [user?.id]);

  async function checkAgreements() {
    try {
      setLoading(true);
      const response = await apiRequest<{
        needs_acceptance: boolean;
        agreements: Agreement[];
        accepted: AgreementStatus;
      }>(`/api/agreements/status`);
      
      if (response.needs_acceptance) {
        setAgreements(response.agreements || []);
        setAccepted(response.accepted || {
          terms: false,
          privacy: false,
          risk_disclosure: false,
        });
        setOpen(true);
      }
    } catch (error) {
      console.error('Error checking agreements:', error);
    } finally {
      setLoading(false);
    }
  }

  async function handleAccept() {
    if (!accepted.terms || !accepted.privacy || !accepted.risk_disclosure) {
      toast.error('Please accept all agreements to continue');
      return;
    }

    try {
      setAccepting(true);
      
      // Accept all three agreements
      const acceptPromises = [
        apiRequest(`/api/agreements/accept`, {
          method: 'POST',
          body: JSON.stringify({
            agreement_type: 'terms',
            agreement_version: agreements.find(a => a.type === 'terms')?.version || '1.0',
          }),
        }),
        apiRequest(`/api/agreements/accept`, {
          method: 'POST',
          body: JSON.stringify({
            agreement_type: 'privacy',
            agreement_version: agreements.find(a => a.type === 'privacy')?.version || '1.0',
          }),
        }),
        apiRequest(`/api/agreements/accept`, {
          method: 'POST',
          body: JSON.stringify({
            agreement_type: 'risk_disclosure',
            agreement_version: agreements.find(a => a.type === 'risk_disclosure')?.version || '1.0',
          }),
        }),
      ];

      await Promise.all(acceptPromises);
      
      toast.success('Agreements accepted successfully');
      setOpen(false);
    } catch (error: any) {
      console.error('Error accepting agreements:', error);
      toast.error(error.message || 'Failed to accept agreements. Please try again.');
    } finally {
      setAccepting(false);
    }
  }

  function getAgreementIcon(type: string) {
    switch (type) {
      case 'terms':
        return <FileText className="w-5 h-5" />;
      case 'privacy':
        return <Shield className="w-5 h-5" />;
      case 'risk_disclosure':
        return <AlertTriangle className="w-5 h-5" />;
      default:
        return <FileText className="w-5 h-5" />;
    }
  }

  function getAgreementTitle(type: string) {
    switch (type) {
      case 'terms':
        return 'Terms of Service';
      case 'privacy':
        return 'Privacy Policy';
      case 'risk_disclosure':
        return 'Risk Disclosure';
      default:
        return 'Agreement';
    }
  }

  if (loading || !open) return null;

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent className="max-w-4xl max-h-[90vh] bg-black/95 border-blue-500/20">
        <DialogHeader>
          <DialogTitle className="text-2xl text-white flex items-center gap-2">
            <AlertCircle className="w-6 h-6 text-yellow-500" />
            Legal Agreements Required
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Please review and accept the following agreements to continue using GSIN.TRADE
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-[60vh] pr-4">
          <div className="space-y-6">
            {agreements.map((agreement) => (
              <div key={agreement.type} className="space-y-4">
                <div className="flex items-center gap-3 pb-2 border-b border-blue-500/20">
                  {getAgreementIcon(agreement.type)}
                  <h3 className="text-xl font-semibold text-white">
                    {getAgreementTitle(agreement.type)}
                  </h3>
                  <span className="text-xs text-gray-500 ml-auto">
                    Version {agreement.version}
                  </span>
                </div>

                <div className="prose prose-invert max-w-none">
                  <div
                    className="text-gray-300 whitespace-pre-wrap"
                    dangerouslySetInnerHTML={{ __html: agreement.content }}
                  />
                </div>

                <div className="flex items-center space-x-2 pt-2">
                  <Checkbox
                    id={`accept-${agreement.type}`}
                    checked={accepted[agreement.type as keyof AgreementStatus]}
                    onCheckedChange={(checked) => {
                      setAccepted((prev) => ({
                        ...prev,
                        [agreement.type]: checked === true,
                      }));
                    }}
                    className="border-blue-500/50 data-[state=checked]:bg-blue-500 data-[state=checked]:border-blue-500"
                  />
                  <label
                    htmlFor={`accept-${agreement.type}`}
                    className="text-sm font-medium text-gray-300 cursor-pointer"
                  >
                    I have read and accept the {getAgreementTitle(agreement.type)}
                  </label>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>

        <div className="flex items-center justify-between pt-4 border-t border-blue-500/20">
          <p className="text-sm text-gray-400">
            You must accept all agreements to use GSIN.TRADE
          </p>
          <Button
            onClick={handleAccept}
            disabled={accepting || !accepted.terms || !accepted.privacy || !accepted.risk_disclosure}
            className="bg-blue-600 hover:bg-blue-700 text-white"
          >
            {accepting ? 'Accepting...' : 'Accept All Agreements'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

