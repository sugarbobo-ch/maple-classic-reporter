import { useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';

export interface OverlayProps {
  isOpen?: boolean;
  onClose?: () => void;
  children?: React.ReactNode;
  className?: string;
  dismissOnClick?: boolean;
}

export default function Overlay({
  isOpen = false,
  onClose,
  children,
  className = '',
  dismissOnClick = true,
}: OverlayProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    restoreFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;

    const getFocusableElements = () => {
      const selector =
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
      return Array.from(overlayRef.current?.querySelectorAll<HTMLElement>(selector) || []).filter(
        (element) => element.getClientRects().length > 0
      );
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && onClose) {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === 'Tab') {
        const focusable = getFocusableElements();
        if (focusable.length === 0) {
          e.preventDefault();
          overlayRef.current?.focus();
          return;
        }

        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', handleKeyDown);
    const focusFrame = requestAnimationFrame(() => {
      getFocusableElements()[0]?.focus();
    });

    return () => {
      cancelAnimationFrame(focusFrame);
      document.body.style.overflow = '';
      document.removeEventListener('keydown', handleKeyDown);
      restoreFocusRef.current?.focus({ preventScroll: true });
      restoreFocusRef.current = null;
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget && dismissOnClick && onClose) {
      onClose();
    }
  };

  return ReactDOM.createPortal(
    <div
      ref={overlayRef}
      className={`ui-overlay ${className}`.trim()}
      onClick={handleBackdropClick}
      tabIndex={-1}
    >
      {children}
    </div>,
    document.body
  );
}
