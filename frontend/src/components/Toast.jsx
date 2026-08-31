import React, { useEffect, useCallback } from 'react';
import { CheckCircle, AlertCircle, Info, X } from 'lucide-react';

/**
 * Toast notification component.
 * 
 * Usage:
 *   const [toast, setToast] = useState(null);
 *   // Show:  setToast({ type: 'success', message: 'Saved!' })
 *   // Error: setToast({ type: 'error', message: err.response?.data?.detail || 'Failed' })
 *   // Auto-dismiss after 5s
 * 
 *   {toast && <Toast toast={toast} onClose={() => setToast(null)} />}
 */
export function Toast({ toast, onClose }) {
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => onClose(), toast.duration || 5000);
    return () => clearTimeout(timer);
  }, [toast, onClose]);

  if (!toast) return null;

  const config = {
    success: {
      bg: 'bg-emerald-500/10 border-emerald-500/30',
      icon: <CheckCircle className="w-4 h-4 text-emerald-400" />,
      text: 'text-emerald-300',
    },
    error: {
      bg: 'bg-red-500/10 border-red-500/30',
      icon: <AlertCircle className="w-4 h-4 text-red-400" />,
      text: 'text-red-300',
    },
    info: {
      bg: 'bg-blue-500/10 border-blue-500/30',
      icon: <Info className="w-4 h-4 text-blue-400" />,
      text: 'text-blue-300',
    },
    warning: {
      bg: 'bg-amber-500/10 border-amber-500/30',
      icon: <AlertCircle className="w-4 h-4 text-amber-400" />,
      text: 'text-amber-300',
    },
  };

  const c = config[toast.type] || config.info;

  return (
    <div className="fixed bottom-6 right-6 z-[9999] animate-in slide-in-from-bottom-5 duration-300">
      <div className={`flex items-center gap-3 px-5 py-3 rounded-xl border backdrop-blur-xl shadow-2xl ${c.bg}`}>
        {c.icon}
        <span className={`text-[12px] font-bold ${c.text}`}>
          {toast.message}
        </span>
        <button onClick={onClose} className="ml-2 text-slate-500 hover:text-white transition-colors cursor-pointer">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

/**
 * Hook version for easier integration.
 * 
 * Usage:
 *   const { toast, showSuccess, showError, showInfo, dismissToast } = useToast();
 */
export function useToast() {
  const [toast, setToast] = React.useState(null);

  const show = useCallback((type, message, duration) => {
    setToast({ type, message, duration });
  }, []);

  const showSuccess = useCallback((msg) => show('success', msg), [show]);
  const showError = useCallback((msg) => show('error', msg, 7000), [show]);
  const showInfo = useCallback((msg) => show('info', msg), [show]);
  const showWarning = useCallback((msg) => show('warning', msg), [show]);
  const dismissToast = useCallback(() => setToast(null), []);

  return { toast, showSuccess, showError, showInfo, showWarning, dismissToast };
}
