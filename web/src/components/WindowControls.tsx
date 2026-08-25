import { useState } from 'react';
import { Minus, Square, X } from 'lucide-react';
import { usePyWebViewEvents } from '../hooks';
import { getReporterBridge } from '../bridge/reporterBridge';

function RestoreWindowIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M6 2.5h7.5V10H11" />
      <path d="M2.5 6h8v7.5h-8z" />
    </svg>
  );
}

export default function WindowControls() {
  const [isWindowMaximized, setIsWindowMaximized] = useState(false);

  usePyWebViewEvents({
    WINDOW_MAXIMIZED: () => setIsWindowMaximized(true),
    WINDOW_RESTORED: () => setIsWindowMaximized(false),
  });

  const handleMinimizeWindow = async () => {
    try {
      await getReporterBridge()?.window.minimize();
    } catch (error) {
      console.warn('Failed to minimize window:', error);
    }
  };

  const handleToggleWindowMaximized = async () => {
    try {
      const maximized = await getReporterBridge()?.window.toggleMaximized();
      if (typeof maximized === 'boolean') setIsWindowMaximized(maximized);
    } catch (error) {
      console.warn('Failed to toggle window state:', error);
    }
  };

  const handleCloseWindow = async () => {
    try {
      await getReporterBridge()?.window.close();
    } catch (error) {
      console.warn('Failed to close window:', error);
    }
  };

  return (
    <div className="window-controls" role="group" aria-label="視窗控制">
      <button
        type="button"
        className="window-control-button"
        aria-label="最小化"
        title="最小化"
        onClick={handleMinimizeWindow}
      >
        <Minus size={16} aria-hidden="true" />
      </button>
      <button
        type="button"
        className="window-control-button"
        aria-label={isWindowMaximized ? '還原' : '最大化'}
        title={isWindowMaximized ? '還原' : '最大化'}
        onClick={handleToggleWindowMaximized}
      >
        {isWindowMaximized ? <RestoreWindowIcon /> : <Square size={15} aria-hidden="true" />}
      </button>
      <button
        type="button"
        className="window-control-button window-control-close"
        aria-label="關閉"
        title="關閉"
        onClick={handleCloseWindow}
      >
        <X size={20} strokeWidth={1.8} aria-hidden="true" />
      </button>
    </div>
  );
}
