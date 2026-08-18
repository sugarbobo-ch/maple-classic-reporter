import { useContext, useMemo, ReactNode } from 'react';
import { ToastContext, ToastOptions } from '../components/ui/ToastContext';

export function useToast() {
  const context = useContext(ToastContext);

  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }

  const { toast: addToast, removeToast, toasts } = context;

  const toastHelpers = useMemo(() => {
    const fn = (options: ToastOptions | string) => addToast(options);

    fn.success = (title: ReactNode, description?: ReactNode, duration?: number) =>
      addToast({ title, description, variant: 'success', duration });

    fn.error = (title: ReactNode, description?: ReactNode, duration?: number) =>
      addToast({ title, description, variant: 'error', duration });

    fn.warning = (title: ReactNode, description?: ReactNode, duration?: number) =>
      addToast({ title, description, variant: 'warning', duration });

    fn.info = (title: ReactNode, description?: ReactNode, duration?: number) =>
      addToast({ title, description, variant: 'info', duration });

    return fn;
  }, [addToast]);

  return {
    toast: toastHelpers,
    removeToast,
    toasts,
  };
}

export default useToast;
