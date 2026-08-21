import { useState, useRef, useEffect } from 'react';
import { Download, History, Minus, RefreshCw, Settings, Square, Sun, Moon, X } from 'lucide-react';
import { IconButton, Badge, Button, CircularProgress } from './ui';
import { usePyWebViewEvents, useTheme } from '../hooks';
import { UpdateStatus, ViewType } from '../types';
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
  updateStatus?: UpdateStatus | null;
  updateBusy?: boolean;
  onStartUpdateDownload?: () => void;
  onRestartAndApplyUpdate?: () => void;
  onCancelUpdateDownload?: () => void;
  onOpenUpdateDetails?: () => void;
}

export default function Header({
  currentView,
  setCurrentView,
  isDevMode,
  theme: configTheme,
  onUpdateTheme,
  updateStatus,
  updateBusy = false,
  onStartUpdateDownload,
  onRestartAndApplyUpdate,
  onOpenUpdateDetails,
}: HeaderProps) {
  const { isDark, toggleTheme } = useTheme(configTheme, onUpdateTheme);
  const [isWindowMaximized, setIsWindowMaximized] = useState(false);
  const actionsRef = useRef<HTMLDivElement>(null);

  usePyWebViewEvents({
    WINDOW_MAXIMIZED: () => setIsWindowMaximized(true),
    WINDOW_RESTORED: () => setIsWindowMaximized(false),
  });

  useEffect(() => {
    const actionsEl = actionsRef.current;
    if (!actionsEl) return;
    const stopDragPropagation = (e: MouseEvent) => {
      e.stopPropagation();
    };
    actionsEl.addEventListener('mousedown', stopDragPropagation);
    actionsEl.addEventListener('dblclick', stopDragPropagation);
    return () => {
      actionsEl.removeEventListener('mousedown', stopDragPropagation);
      actionsEl.removeEventListener('dblclick', stopDragPropagation);
    };
  }, []);

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
      const target = e.target as HTMLElement;
      if (target.closest('.header-actions, button, a, input, select')) {
        return;
      }
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

  const handleHeaderDoubleClick = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.closest('.header-actions, button, a, input, select')) {
      return;
    }
    void handleToggleWindowMaximized();
  };

  const updateState = updateStatus?.state;
  const hasUpdateControl = Boolean(
    updateState &&
      !['idle', 'checking', 'up_to_date', 'applying'].includes(updateState)
  );
  const updateLabel = updateStatus?.target_version
    ? `更新至 v${updateStatus.target_version}`
    : '更新';
  const updatePercent = Math.max(0, Math.min(100, Math.round(updateStatus?.progress_percent || 0)));

  const renderUpdateControl = () => {
    if (!hasUpdateControl) return null;
    let icon = Download;
    let tooltip = updateLabel;
    let isSpinning = false;
    let active = false;

    if (updateState === 'downloading') {
      icon = RefreshCw;
      tooltip = `正在${updateLabel} (${updatePercent}%) - 點擊前往設定`;
      isSpinning = true;
      active = true;
    } else if (updateState === 'ready' || updateState === 'waiting_for_idle') {
      icon = RefreshCw;
      tooltip = `v${updateStatus?.target_version || ''} 已下載完成 - 點擊前往套用`;
      active = true;
    } else if (updateState === 'error' || updateState === 'insufficient_space') {
      icon = Download;
      tooltip = updateStatus?.error_message || '更新異常 - 點擊查看';
    } else if (updateState === 'available') {
      icon = Download;
      tooltip = `有可用更新：v${updateStatus?.target_version || ''} - 點擊前往查看`;
      active = true;
    }

    return (
      <IconButton
        icon={icon}
        size="md"
        variant={active ? 'primary' : 'ghost'}
        active={active}
        tooltip={tooltip}
        onClick={onOpenUpdateDetails}
        className={`header-update-icon ${isSpinning ? 'spin-reverse' : ''}`}
        aria-label={tooltip}
      />
    );
  };

  return (
    <header
      className="app-header pywebview-drag-region"
      onMouseDown={handleDragWindow}
      onDoubleClick={handleHeaderDoubleClick}
    >
      <div
        className="header-brand pywebview-drag-region"
        style={{ display: 'flex', alignItems: 'center', gap: '10px', userSelect: 'none' }}
      >
        <img
          src={appLogo}
          alt="Maple Classic Reporter Logo"
          className="header-logo pywebview-drag-region"
          draggable={false}
        />
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '1px',
            userSelect: 'none',
          }}
        >
          <button
            type="button"
            className="header-title header-home-button"
            onClick={() => setCurrentView('home')}
            aria-label="返回首頁"
          >
            新楓之谷：經典版《自動外掛檢舉工具》
          </button>
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

      <div
        className="header-spacer pywebview-drag-region"
        style={{ flex: 1, alignSelf: 'stretch', cursor: 'default' }}
      />

      <div
        ref={actionsRef}
        className="header-actions"
        onMouseDown={(e) => e.stopPropagation()}
        onDoubleClick={(e) => e.stopPropagation()}
      >
        {renderUpdateControl()}
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
