import { useState } from 'react';
import { History, Minus, Settings, Square, Sun, Moon, X } from 'lucide-react';
import { IconButton, Badge } from './ui';
import { usePyWebViewEvents, useTheme } from '../hooks';
import { ViewType } from '../types';
import appLogo from '../assets/icon.png';
import { APP_VERSION } from '../constants/version';

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

export interface HeaderProps {
  currentView: ViewType;
  setCurrentView: (view: ViewType) => void;
  alertUnconfigured?: boolean;
  isDevMode?: boolean;
  theme?: string;
  onUpdateTheme?: (theme: 'light' | 'dark') => void;
}

export default function Header({
  currentView,
  setCurrentView,
  isDevMode,
  theme: configTheme,
  onUpdateTheme,
}: HeaderProps) {
  const { isDark, toggleTheme } = useTheme(configTheme, onUpdateTheme);
  const [isWindowMaximized, setIsWindowMaximized] = useState(false);

  usePyWebViewEvents({
    WINDOW_MAXIMIZED: () => setIsWindowMaximized(true),
    WINDOW_RESTORED: () => setIsWindowMaximized(false),
  });

  const handleMinimizeWindow = async () => {
    try {
      await window.pywebview?.api?.minimize_window?.();
    } catch (error) {
      console.warn('Failed to minimize window:', error);
    }
  };

  const handleToggleWindowMaximized = async () => {
    try {
      const maximized = await window.pywebview?.api?.toggle_window_maximized?.();
      if (typeof maximized === 'boolean') setIsWindowMaximized(maximized);
    } catch (error) {
      console.warn('Failed to toggle window state:', error);
    }
  };

  const handleCloseWindow = async () => {
    try {
      await window.pywebview?.api?.close_window?.();
    } catch (error) {
      console.warn('Failed to close window:', error);
    }
  };

  const handleDragWindow = (e: React.MouseEvent) => {
    if (e.button === 0) {
      const header = e.currentTarget.closest('.app-header');
      const brand = header?.querySelector('.header-brand');
      const actions = header?.querySelector('.header-actions');
      const brandBounds = brand?.getBoundingClientRect();
      const actionsBounds = actions?.getBoundingClientRect();
      const edgeGap = 48;

      let anchorMode: 'left' | 'right' | 'proportional' = 'proportional';
      if (brandBounds && e.clientX <= brandBounds.right + edgeGap) {
        anchorMode = 'left';
      } else if (actionsBounds && e.clientX >= actionsBounds.left - edgeGap) {
        anchorMode = 'right';
      }

      window.pywebview?.api?.drag_window?.(anchorMode);
    }
  };

  return (
    <header className="app-header">
      <div
        className="app-header-drag-region pywebview-drag-region"
        onMouseDown={handleDragWindow}
        onDoubleClick={() => void handleToggleWindowMaximized()}
      >
        <div
          className="header-brand"
          onClick={() => setCurrentView('home')}
          style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '10px' }}
        >
          <img
            src={appLogo}
            alt="Maple Classic Reporter Logo"
            className="header-logo"
          />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
            <span className="header-title" style={{ fontSize: '1rem', fontWeight: 700 }}>
              新楓之谷：經典版《自動外掛檢舉工具》
            </span>
            <span
              style={{
                fontSize: '0.72rem',
                color: 'var(--color-text-secondary)',
                fontWeight: 500,
                letterSpacing: '0.3px',
                lineHeight: 1,
              }}
            >
              Maple Classic Reporter
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginLeft: '-6px' }}>
            <Badge variant="primary" size="sm">
              v{APP_VERSION}
            </Badge>
            {isDevMode && (
              <Badge variant="event" size="sm">
                DEV 測試模式
              </Badge>
            )}
          </div>
        </div>
      </div>

      <div className="header-actions">
        <IconButton
          icon={isDark ? Sun : Moon}
          size="md"
          variant="ghost"
          tooltip={isDark ? '切換為淺色模式' : '切換為深色模式'}
          onClick={toggleTheme}
        />

        <IconButton
          icon={History}
          size="md"
          variant={currentView === 'history' ? 'primary' : 'ghost'}
          active={currentView === 'history'}
          tooltip="歷史紀錄"
          onClick={() => setCurrentView(currentView === 'history' ? 'home' : 'history')}
        />

        <IconButton
          icon={Settings}
          size="md"
          variant={currentView === 'settings' ? 'primary' : 'ghost'}
          active={currentView === 'settings'}
          tooltip="設定"
          onClick={() => setCurrentView(currentView === 'settings' ? 'home' : 'settings')}
        />
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
      </div>
    </header>
  );
}
