import React, { useEffect, useState } from 'react';
import { CheckCircle, XCircle, X, AlertTriangle, Info } from 'lucide-react';

export interface ToastData {
  id: number;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
}

const icons = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const styles = {
  success: 'border-emerald-200/60 bg-emerald-50 text-emerald-800',
  error: 'border-red-200/60 bg-red-50 text-red-800',
  warning: 'border-amber-200/60 bg-amber-50 text-amber-800',
  info: 'border-blue-200/60 bg-blue-50 text-blue-800',
};

const iconStyles = {
  success: 'text-emerald-500',
  error: 'text-red-500',
  warning: 'text-amber-500',
  info: 'text-blue-500',
};

const Toast: React.FC<{ toast: ToastData; onDismiss: (id: number) => void }> = ({ toast, onDismiss }) => {
  const [phase, setPhase] = useState<'enter' | 'visible' | 'exit'>('enter');
  const Icon = icons[toast.type];

  useEffect(() => {
    requestAnimationFrame(() => setPhase('visible'));
    const timer = setTimeout(() => {
      setPhase('exit');
      setTimeout(() => onDismiss(toast.id), 250);
    }, 5000);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  return (
    <div
      className={`flex items-start gap-3 rounded-xl border px-4 py-3 shadow-lg backdrop-blur-sm ${styles[toast.type]} ${
        phase === 'enter' ? 'toast-enter' : phase === 'exit' ? 'toast-exit' : ''
      }`}
    >
      <Icon size={18} className={`mt-0.5 shrink-0 ${iconStyles[toast.type]}`} />
      <p className="flex-1 text-sm font-medium">{toast.message}</p>
      <button
        onClick={() => { setPhase('exit'); setTimeout(() => onDismiss(toast.id), 250); }}
        className="shrink-0 rounded-md p-0.5 opacity-40 transition-opacity hover:opacity-100"
      >
        <X size={14} />
      </button>
    </div>
  );
};

export const ToastContainer: React.FC<{ toasts: ToastData[]; onDismiss: (id: number) => void }> = ({ toasts, onDismiss }) => {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2.5 w-96">
      {toasts.map((t) => (
        <Toast key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
};

export default Toast;
