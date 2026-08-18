import { createContext, ReactNode } from 'react';

export type ToastVariant = 'success' | 'error' | 'danger' | 'warning' | 'info' | 'default';

export interface ToastOptions {
  id?: string;
  title: ReactNode;
  description?: ReactNode;
  variant?: ToastVariant;
  duration?: number;
}

export interface ToastItemData extends ToastOptions {
  id: string;
}

export interface ToastContextType {
  toasts: ToastItemData[];
  toast: (options: ToastOptions | string) => string;
  removeToast: (id: string) => void;
}

export const ToastContext = createContext<ToastContextType | null>(null);
