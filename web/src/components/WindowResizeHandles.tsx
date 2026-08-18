import React, { useState } from 'react';
import { usePyWebViewEvents } from '../hooks';

const HANDLES = [
  { dir: 'top', className: 'resize-handle-top' },
  { dir: 'bottom', className: 'resize-handle-bottom' },
  { dir: 'left', className: 'resize-handle-left' },
  { dir: 'right', className: 'resize-handle-right' },
  { dir: 'top-left', className: 'resize-handle-top-left' },
  { dir: 'top-right', className: 'resize-handle-top-right' },
  { dir: 'bottom-left', className: 'resize-handle-bottom-left' },
  { dir: 'bottom-right', className: 'resize-handle-bottom-right' },
];

export default function WindowResizeHandles() {
  const [isMaximized, setIsMaximized] = useState(false);

  usePyWebViewEvents({
    WINDOW_MAXIMIZED: () => setIsMaximized(true),
    WINDOW_RESTORED: () => setIsMaximized(false),
  });

  if (isMaximized) {
    return null;
  }

  const handlePointerDown = (dir: string) => (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0 || !e.isPrimary) return;

    const resizeWindow = window.pywebview?.api?.resize_window;
    if (!resizeWindow) return;

    e.preventDefault();
    e.stopPropagation();
    void resizeWindow(dir).catch((error: unknown) => {
      console.debug('Native window resize failed:', error);
    });
  };

  return (
    <div className="window-resize-overlay" aria-hidden="true">
      {HANDLES.map(({ dir, className }) => (
        <div
          key={dir}
          className={`resize-handle ${className}`}
          onPointerDown={handlePointerDown(dir)}
        />
      ))}
    </div>
  );
}
