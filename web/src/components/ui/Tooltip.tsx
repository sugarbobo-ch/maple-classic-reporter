import React, { useRef, useEffect } from 'react';
import ReactDOM from 'react-dom';
import { useAnchorPosition, useDisclosure, Placement } from '../../hooks';

export interface TooltipProps {
  content?: React.ReactNode;
  children: React.ReactElement;
  placement?: Placement;
  delay?: number;
  className?: string;
}

export default function Tooltip({
  content,
  children,
  placement = 'bottom',
  delay = 150,
  className = '',
}: TooltipProps) {
  const triggerRef = useRef<HTMLSpanElement>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { isOpen, open, close } = useDisclosure();

  const { position: coords } = useAnchorPosition(triggerRef, {
    placement,
    offset: 8,
    enabled: isOpen,
    autoFlip: true,
    centerHorizontal: true,
  });

  const handleMouseEnter = () => {
    timeoutRef.current = setTimeout(() => {
      open();
    }, delay);
  };

  const handleMouseLeave = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    close();
  };

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  if (!content) return children;

  return (
    <span
      ref={triggerRef}
      className={`ui-tooltip-trigger-wrapper ${className}`.trim()}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocus={handleMouseEnter}
      onBlur={handleMouseLeave}
    >
      {children}
      {isOpen &&
        ReactDOM.createPortal(
          <div
            className={`ui-tooltip-box placement-${coords.placement || placement}`}
            style={{
              top: `${coords.top}px`,
              left: `${coords.left}px`,
            }}
            role="tooltip"
          >
            <span className="ui-tooltip-content">{content}</span>
            <span className="ui-tooltip-arrow" />
          </div>,
          document.body
        )}
    </span>
  );
}
