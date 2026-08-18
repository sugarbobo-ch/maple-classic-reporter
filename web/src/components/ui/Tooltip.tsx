import React, { useRef, useEffect, useState, useLayoutEffect, useCallback } from 'react';
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
  const tooltipBoxRef = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { isOpen, open, close } = useDisclosure();

  const { position: coords } = useAnchorPosition(triggerRef, {
    placement,
    offset: 8,
    enabled: isOpen,
    autoFlip: true,
    centerHorizontal: true,
  });

  const [coordsState, setCoordsState] = useState<{
    left: number;
    top: number;
    arrowLeft: number;
  }>({
    left: 0,
    top: 0,
    arrowLeft: 0,
  });

  const updateClampedPosition = useCallback(() => {
    if (!triggerRef.current) return;

    const triggerRect = triggerRef.current.getBoundingClientRect();
    const tooltipEl = tooltipBoxRef.current;
    const tooltipWidth = tooltipEl ? tooltipEl.offsetWidth : 120;
    const tooltipHeight = tooltipEl ? tooltipEl.offsetHeight : 28;
    const viewportWidth = window.innerWidth;
    const margin = 8;

    const anchorCenterX = triggerRect.left + triggerRect.width / 2;
    const idealLeft = anchorCenterX - tooltipWidth / 2;
    const clampedLeft = Math.max(margin, Math.min(viewportWidth - tooltipWidth - margin, idealLeft));
    const arrowLeft = Math.max(8, Math.min(tooltipWidth - 8, anchorCenterX - clampedLeft));

    const finalTop = coords.placement === 'top' ? coords.top - tooltipHeight : coords.top;

    setCoordsState({
      left: clampedLeft,
      top: finalTop,
      arrowLeft,
    });
  }, [coords.top, coords.placement]);

  useLayoutEffect(() => {
    if (isOpen) {
      updateClampedPosition();
    }
  }, [isOpen, coords, updateClampedPosition]);

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
            ref={tooltipBoxRef}
            className={`ui-tooltip-box placement-${coords.placement || placement}`}
            style={{
              top: `${coordsState.top}px`,
              left: `${coordsState.left}px`,
            }}
            role="tooltip"
          >
            <span className="ui-tooltip-content">{content}</span>
            <span
              className="ui-tooltip-arrow"
              style={
                coords.placement === 'top' || coords.placement === 'bottom' || !coords.placement
                  ? { left: `${coordsState.arrowLeft}px` }
                  : undefined
              }
            />
          </div>,
          document.body
        )}
    </span>
  );
}
