import { useState, useCallback, useLayoutEffect, RefObject } from 'react';

export type Placement = 'top' | 'bottom' | 'left' | 'right';

export interface AnchorPositionOptions {
  placement?: Placement;
  offset?: number;
  estimatedHeight?: number;
  autoFlip?: boolean;
  enabled?: boolean;
  centerHorizontal?: boolean;
}

export interface PositionResult {
  top: number;
  left: number;
  width: number;
  placement: Placement;
}

export function useAnchorPosition(
  anchorRef: RefObject<HTMLElement | null>,
  options: AnchorPositionOptions = {}
) {
  const {
    placement = 'bottom',
    offset = 4,
    estimatedHeight = 220,
    autoFlip = true,
    enabled = true,
    centerHorizontal = false,
  } = options;

  const [position, setPosition] = useState<PositionResult>({
    top: 0,
    left: 0,
    width: 0,
    placement,
  });

  const updatePosition = useCallback(() => {
    if (!enabled || !anchorRef.current) return;

    const rect = anchorRef.current.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    const viewportWidth = window.innerWidth;

    let computedTop = 0;
    let computedLeft = centerHorizontal ? rect.left + rect.width / 2 : rect.left;
    let computedPlacement = placement;

    if (centerHorizontal) {
      // Logic for Tooltip / Centered elements (which use CSS transforms for self-offset)
      if (placement === 'top') {
        if (autoFlip && rect.top < 45 && viewportHeight - rect.bottom > 45) {
          computedPlacement = 'bottom';
          computedTop = rect.bottom + offset;
        } else {
          computedPlacement = 'top';
          computedTop = rect.top - offset;
        }
      } else if (placement === 'bottom') {
        if (autoFlip && viewportHeight - rect.bottom < 45 && rect.top > 45) {
          computedPlacement = 'top';
          computedTop = rect.top - offset;
        } else {
          computedPlacement = 'bottom';
          computedTop = rect.bottom + offset;
        }
      }
    } else {
      // Logic for Dropdowns / Menus
      if (placement === 'bottom' || placement === 'top') {
        const spaceBelow = viewportHeight - rect.bottom;
        const spaceAbove = rect.top;

        if (autoFlip && spaceBelow < estimatedHeight && spaceAbove > spaceBelow) {
          computedTop = rect.top - estimatedHeight - offset;
          computedPlacement = 'top';
        } else if (placement === 'top') {
          computedTop = rect.top - estimatedHeight - offset;
          computedPlacement = 'top';
        } else {
          computedTop = rect.bottom + offset;
          computedPlacement = 'bottom';
        }

        // Horizontal clamp for dropdown menus
        if (computedLeft + rect.width > viewportWidth - 10) {
          computedLeft = Math.max(10, viewportWidth - rect.width - 10);
        }
      } else if (placement === 'left') {
        computedLeft = rect.left - offset;
        computedTop = rect.top + rect.height / 2;
      } else if (placement === 'right') {
        computedLeft = rect.right + offset;
        computedTop = rect.top + rect.height / 2;
      }
    }

    setPosition({
      top: Math.max(5, computedTop),
      left: Math.max(5, computedLeft),
      width: rect.width,
      placement: computedPlacement,
    });
  }, [anchorRef, placement, offset, estimatedHeight, autoFlip, enabled, centerHorizontal]);

  useLayoutEffect(() => {
    if (!enabled) return;

    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);

    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [enabled, updatePosition]);

  return { position, updatePosition };
}
