'use client';

import Link from 'next/link';
import { FileText, Shield, AlertTriangle } from 'lucide-react';

export function ComplianceFooter() {
  return (
    <footer className="border-t border-blue-500/20 bg-black/40 backdrop-blur-xl mt-auto">
      <div className="container mx-auto px-6 py-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="text-sm text-gray-400">
            © {new Date().getFullYear()} GSIN. All rights reserved.
          </div>
          <div className="flex items-center gap-6">
            <Link
              href="/compliance/privacy"
              className="text-sm text-gray-400 hover:text-blue-400 transition-colors flex items-center gap-1"
            >
              <Shield className="w-4 h-4" />
              Privacy Policy
            </Link>
            <Link
              href="/compliance/terms"
              className="text-sm text-gray-400 hover:text-blue-400 transition-colors flex items-center gap-1"
            >
              <FileText className="w-4 h-4" />
              Terms of Service
            </Link>
            <Link
              href="/compliance/disclaimer"
              className="text-sm text-gray-400 hover:text-blue-400 transition-colors flex items-center gap-1"
            >
              <AlertTriangle className="w-4 h-4" />
              Trading Disclaimer
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}

