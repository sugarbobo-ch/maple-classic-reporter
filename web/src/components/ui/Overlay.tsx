import { useEffect } from 'react';
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
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && onClose) {
        onClose();
      }
    };

    if (isOpen) {
      document.body.style.overflow = 'hidden';
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.body.style.overflow = '';
      document.removeEventListener('keydown', handleKeyDown);
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
      className={`ui-overlay ${className}`.trim()}
      onClick={handleBackdropClick}
    >
      {children}
    </div>,
    document.body
  );
}
