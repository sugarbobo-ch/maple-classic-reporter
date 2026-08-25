import { useState, useRef, useEffect } from 'react';
import { Download, History, MoreHorizontal, RefreshCw, Settings, Sun, Moon } from 'lucide-react';
import { IconButton, Badge, Button, CircularProgress } from './ui';
import { useTheme } from '../hooks';
import { getReporterBridge } from '../bridge/reporterBridge';
import { UpdateStatus, ViewType } from '../types';
import appLogo from '../assets/icon.png';
import { APP_VERSION } from '../constants/version';
import WindowControls from './WindowControls';

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
  const [isApplying, setIsApplying] = useState(false);
  const { isDark, toggleTheme } = useTheme(configTheme, onUpdateTheme);
  const actionsRef = useRef<HTMLDivElement>(null);
  const mobileMenuRef = useRef<HTMLDivElement>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

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

  useEffect(() => {
    if (!isMobileMenuOpen) return;

    const handleOutsidePointer = (event: MouseEvent) => {
      if (!actionsRef.current?.contains(event.target as Node)) {
        setIsMobileMenuOpen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsMobileMenuOpen(false);
    };

    document.addEventListener('mousedown', handleOutsidePointer);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleOutsidePointer);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isMobileMenuOpen]);

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

      void getReporterBridge()?.window.drag(anchorMode);
    }
  };

  const handleToggleWindowMaximized = async () => {
    try {
      await getReporterBridge()?.window.toggleMaximized();
    } catch (error) {
      console.warn('Failed to toggle window state:', error);
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

    if (updateState === 'downloading') {
      return (
        <button
          type="button"
          className="header-update-progress"
          onClick={onOpenUpdateDetails}
          aria-label={`正在${updateLabel}，進度 ${updatePercent}%`}
          title={`正在${updateLabel} (${updatePercent}%) - 點擊查看詳細資料`}
          aria-describedby="header-update-status"
        >
          <CircularProgress
            value={updatePercent / 100}
            size={32}
            strokeWidth={3}
            progressColor="var(--color-primary)"
            trackColor="var(--color-border)"
            ariaLabel={`正在${updateLabel}`}
            ariaValueNow={updatePercent}
          >
            <span aria-hidden="true">{updatePercent}%</span>
          </CircularProgress>
          <span id="header-update-status" className="sr-only" role="status" aria-live="polite">
            {`正在${updateLabel}，進度 ${updatePercent}%`}
          </span>
        </button>
      );
    }

    if (updateState === 'ready' || updateState === 'waiting_for_idle' || updateState === 'applying') {
      const waiting = isApplying || updateState === 'applying' || updateState === 'waiting_for_idle' || updateBusy;
      const label = isApplying || updateState === 'applying'
        ? '重啟中…'
        : waiting
          ? '完成後重啟'
          : '重啟應用';

      return (
        <Button
          variant="success"
          size="sm"
          icon={RefreshCw}
          onClick={() => {
            setIsApplying(true);
            onRestartAndApplyUpdate?.();
          }}
          disabled={waiting}
          title={waiting ? '目前工作完成後會自動重啟更新' : '關閉並套用更新'}
          aria-label={waiting ? '目前工作完成後重啟更新' : '重啟應用並套用更新'}
          className="header-update-button"
        >
          {label}
        </Button>
      );
    }

    if (updateState === 'insufficient_space') {
      return (
        <Button
          variant="danger"
          size="sm"
          icon={Download}
          onClick={onOpenUpdateDetails}
          title={updateStatus?.error_message || '可用空間不足'}
          aria-label="更新空間不足，查看詳細資料"
          className="header-update-button"
        >
          空間不足
        </Button>
      );
    }

    if (updateState === 'error') {
      return (
        <Button
          variant="danger"
          size="sm"
          icon={Download}
          onClick={onOpenUpdateDetails}
          title={updateStatus?.error_message || '更新失敗，點擊重試'}
          aria-label="更新失敗，查看詳細資料並重試"
          className="header-update-button"
        >
          更新失敗
        </Button>
      );
    }

    return (
      <Button
        variant="primary"
        size="sm"
        icon={Download}
        onClick={onStartUpdateDownload}
        title={`有可用更新：v${updateStatus?.target_version || ''} - 點擊立即下載`}
        aria-label={`有可用更新：v${updateStatus?.target_version || ''}，點擊立即下載`}
        className="header-update-button"
      >
        有可用更新
      </Button>
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
        <div className="header-navigation-actions">
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
        </div>
        <IconButton
          className="header-mobile-menu-toggle"
          icon={MoreHorizontal}
          size="md"
          variant={isMobileMenuOpen ? 'primary' : 'ghost'}
          active={isMobileMenuOpen}
          tooltip="更多功能"
          aria-label="更多功能"
          aria-expanded={isMobileMenuOpen}
          aria-controls="header-mobile-menu"
          onClick={() => setIsMobileMenuOpen((open) => !open)}
        />
        {isMobileMenuOpen && (
          <div ref={mobileMenuRef} id="header-mobile-menu" className="header-mobile-menu" role="menu" aria-label="更多功能">
            <div className="header-mobile-update" aria-live="polite">
              {renderUpdateControl()}
            </div>
            <button
              type="button"
              role="menuitem"
              className="header-mobile-menu-item"
              onClick={() => {
                toggleTheme();
                setIsMobileMenuOpen(false);
              }}
            >
              {isDark ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
              <span>{isDark ? '切換為淺色模式' : '切換為深色模式'}</span>
            </button>
            <button
              type="button"
              role="menuitem"
              className="header-mobile-menu-item"
              onClick={() => {
                setCurrentView(currentView === 'history' ? 'home' : 'history');
                setIsMobileMenuOpen(false);
              }}
            >
              <History size={16} aria-hidden="true" />
              <span>歷史紀錄</span>
            </button>
            <button
              type="button"
              role="menuitem"
              className="header-mobile-menu-item"
              onClick={() => {
                setCurrentView(currentView === 'settings' ? 'home' : 'settings');
                setIsMobileMenuOpen(false);
              }}
            >
              <Settings size={16} aria-hidden="true" />
              <span>設定</span>
            </button>
          </div>
        )}
        <WindowControls />
      </div>
    </header>
  );
}
