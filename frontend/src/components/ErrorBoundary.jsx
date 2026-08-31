import React from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

/**
 * Global Error Boundary — catches unhandled React errors and shows a
 * recovery UI instead of a blank screen.
 *
 * Wrap the <App /> or route-level components with this.
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    // Log to console for debugging
    console.error('[ErrorBoundary]', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleGoHome = () => {
    window.location.href = '/';
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#0a0f1a] flex items-center justify-center p-8">
          <div className="bg-[#0f172a] border border-red-500/20 rounded-3xl p-10 max-w-lg w-full text-center space-y-6">
            <div className="w-16 h-16 rounded-2xl bg-red-500/10 flex items-center justify-center border border-red-500/20 mx-auto">
              <AlertTriangle className="w-8 h-8 text-red-400" />
            </div>
            <div>
              <h2 className="text-xl font-black text-white uppercase tracking-tight">
                Something Went Wrong
              </h2>
              <p className="text-sm text-slate-400 mt-2">
                An unexpected error occurred. Your data is safe.
              </p>
            </div>
            {this.state.error && (
              <div className="bg-slate-950/60 border border-white/5 rounded-xl p-4 text-left">
                <p className="text-[11px] font-mono text-red-400 break-all">
                  {this.state.error.message || String(this.state.error)}
                </p>
              </div>
            )}
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={this.handleRetry}
                className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-xl text-[11px] font-black uppercase tracking-wider hover:bg-indigo-500 transition-all cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Try Again
              </button>
              <button
                onClick={this.handleGoHome}
                className="flex items-center gap-2 px-5 py-2.5 bg-white/5 text-slate-300 rounded-xl text-[11px] font-black uppercase tracking-wider hover:bg-white/10 transition-all cursor-pointer border border-white/10"
              >
                <Home className="w-3.5 h-3.5" /> Home
              </button>
              <button
                onClick={this.handleReload}
                className="flex items-center gap-2 px-5 py-2.5 bg-white/5 text-slate-400 rounded-xl text-[11px] font-black uppercase tracking-wider hover:bg-white/10 transition-all cursor-pointer border border-white/10"
              >
                Reload
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
