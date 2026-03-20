import React, { useEffect, useState } from 'react';
import { CheckCircle, XCircle, X } from 'lucide-react';

export interface ToastData {
  id: number;
  type: 'success' | 'error';
  message: string;
}

const Toast: React.FC<{ toast: ToastData; onDismiss: (id: number) => void }> = ({ toast, onDismiss }) => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onDismiss(toast.id), 300);
    }, 5000);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  const isSuccess = toast.type === 'success';

  return (
    <div
      className={`flex items-start gap-3 rounded-lg border px-4 py-3 shadow-lg transition-all duration-300 ${
        visible ? 'translate-x-0 opacity-100' : 'translate-x-full opacity-0'
      } ${
        isSuccess
          ? 'border-green-200 bg-green-50 text-green-800'
          : 'border-red-200 bg-red-50 text-red-800'
      }`}
    >
      {isSuccess ? <CheckCircle size={18} className="mt-0.5 shrink-0 text-green-600" /> : <XCircle size={18} className="mt-0.5 shrink-0 text-red-600" />}
      <p className="text-sm font-medium flex-1">{toast.message}</p>
      <button onClick={() => { setVisible(false); setTimeout(() => onDismiss(toast.id), 300); }} className="shrink-0 text-current opacity-50 hover:opacity-100">
        <X size={14} />
      </button>
    </div>
  );
};

export const ToastContainer: React.FC<{ toasts: ToastData[]; onDismiss: (id: number) => void }> = ({ toasts, onDismiss }) => {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 w-96">
      {toasts.map((t) => (
        <Toast key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
};

export default Toast;
