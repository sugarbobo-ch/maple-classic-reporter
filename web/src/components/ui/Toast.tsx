import { useState, useCallback, ReactNode } from 'react';
import ReactDOM from 'react-dom';
import { X } from 'lucide-react';
import { ToastContext, ToastItemData, ToastOptions } from './ToastContext';
import Badge, { BadgeVariant } from './Badge';

export function ToastItem({
  toast,
  onDismiss,
}: {
  toast: ToastItemData;
  onDismiss: (id: string) => void;
}) {
  const [isExiting, setIsExiting] = useState(false);

  const handleClose = useCallback(() => {
    if (isExiting) return;
    setIsExiting(true);
    setTimeout(() => {
      onDismiss(toast.id);
    }, 200);
  }, [isExiting, onDismiss, toast.id]);

  const getBadgeInfo = (): { variant: BadgeVariant; label: string } => {
    switch (toast.variant) {
      case 'success':
        return { variant: 'update', label: '更新' };
      case 'error':
      case 'danger':
        return { variant: 'event', label: '異常' };
      case 'warning':
        return { variant: 'warning', label: '提醒' };
      case 'info':
        return { variant: 'important', label: '重要' };
      default:
        return { variant: 'primary', label: '通知' };
    }
  };

  const badgeInfo = getBadgeInfo();

  return (
    <div
      className={`ui-toast ui-toast-${toast.variant || 'default'} ${isExiting ? 'is-exiting' : ''}`}
      role="status"
    >
      <div className="ui-toast-content">
        <div className="ui-toast-title">
          <Badge variant={badgeInfo.variant} size="sm" className="ui-toast-badge">
            {badgeInfo.label}
          </Badge>
          <span className="ui-toast-title-text">{toast.title}</span>
        </div>
        {toast.description && <div className="ui-toast-description">{toast.description}</div>}
      </div>
      <button type="button" className="ui-toast-close" onClick={handleClose} aria-label="關閉通知">
        <X size={14} />
      </button>
    </div>
  );
}

export function ToastContainer({
  toasts,
  onDismiss,
}: {
  toasts: ToastItemData[];
  onDismiss: (id: string) => void;
}) {
  if (toasts.length === 0) return null;

  return ReactDOM.createPortal(
    <div className="ui-toast-container">
      {toasts.map((item) => (
        <ToastItem key={item.id} toast={item} onDismiss={onDismiss} />
      ))}
    </div>,
    document.body
  );
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItemData[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (options: ToastOptions | string) => {
      const id =
        typeof options === 'object' && options.id
          ? options.id
          : `toast-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
      const normalized: ToastItemData =
        typeof options === 'string'
          ? { id, title: options, variant: 'default', duration: 3500 }
          : {
              id,
              title: options.title,
              description: options.description,
              variant: options.variant || 'default',
              duration: options.duration ?? 3500,
            };

      setToasts((prev) => {
        // If adding an error toast, remove any existing error toast so only one is shown at a time
        if (normalized.variant === 'error') {
          const nonErrors = prev.filter((t) => t.variant !== 'error');
          return [...nonErrors, normalized];
        }
        // Deduplicate if identical toast is already active
        const isDuplicate = prev.some(
          (t) =>
            t.variant === normalized.variant &&
            t.title === normalized.title &&
            t.description === normalized.description
        );
        if (isDuplicate) {
          return prev;
        }
        return [...prev, normalized];
      });

      if (normalized.duration && normalized.duration > 0) {
        setTimeout(() => {
          removeToast(id);
        }, normalized.duration);
      }

      return id;
    },
    [removeToast]
  );

  return (
    <ToastContext.Provider value={{ toasts, toast: addToast, removeToast }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </ToastContext.Provider>
  );
}

export default ToastItem;
