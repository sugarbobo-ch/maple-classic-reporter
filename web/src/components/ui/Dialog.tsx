import { X, LucideIcon } from 'lucide-react';
import Overlay from './Overlay';
import IconButton from './IconButton';

export interface DialogProps {
  isOpen?: boolean;
  onClose?: () => void;
  title?: React.ReactNode;
  titleIcon?: LucideIcon;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?: string;
  className?: string;
  dismissOnBackdropClick?: boolean;
}

export default function Dialog({
  isOpen = false,
  onClose,
  title,
  titleIcon: TitleIcon,
  children,
  footer = null,
  maxWidth = '580px',
  className = '',
  dismissOnBackdropClick = false,
}: DialogProps) {
  const handleDialogHeaderMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.button === 0 && !(e.target as HTMLElement).closest('button, input, select, a, [role="button"]')) {
      window.pywebview?.api?.drag_window?.('proportional');
    }
  };

  return (
    <Overlay
      isOpen={isOpen}
      onClose={onClose}
      dismissOnClick={dismissOnBackdropClick}
    >
      <div className={`ui-dialog ${className}`.trim()} style={{ maxWidth }}>
        {(title || onClose) && (
          <div
            className="ui-dialog-header pywebview-drag-region"
            onMouseDown={handleDialogHeaderMouseDown}
          >
            <div className="ui-dialog-title">
              {TitleIcon && <TitleIcon size={20} color="var(--color-primary)" />}
              <span>{title}</span>
            </div>
            {onClose && (
              <IconButton icon={X} size="md" variant="ghost" tooltip="關閉" onClick={onClose} />
            )}
          </div>
        )}

        <div className="ui-dialog-body">{children}</div>

        {footer && <div className="ui-dialog-footer">{footer}</div>}
      </div>
    </Overlay>
  );
}
