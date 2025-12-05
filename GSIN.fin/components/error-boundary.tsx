'use client';

import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { AlertTriangle } from 'lucide-react';

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Card className="bg-red-500/10 border-red-500/30 m-6">
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle className="w-6 h-6 text-red-400" />
              <h3 className="text-lg font-semibold text-red-400">Something went wrong</h3>
            </div>
            <p className="text-gray-300 mb-4">
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>
            <div className="flex gap-3">
              <Button
                onClick={() => {
                  this.setState({ hasError: false, error: null });
                  window.location.reload();
                }}
                className="bg-blue-600 hover:bg-blue-700"
              >
                Reload Page
              </Button>
              <Button
                onClick={() => {
                  this.setState({ hasError: false, error: null });
                  window.location.href = '/dashboard';
                }}
                variant="outline"
                className="bg-white/5 border-blue-500/20 text-white"
              >
                Go to Dashboard
              </Button>
            </div>
          </CardContent>
        </Card>
      );
    }

    return this.props.children;
  }
}

