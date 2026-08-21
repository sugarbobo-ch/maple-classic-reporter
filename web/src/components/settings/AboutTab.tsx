import { useState } from 'react';
import { AlertTriangle, CheckCircle2, Download, ExternalLink, FileText, FolderOpen, RefreshCw } from 'lucide-react';
import { Button, Badge, CircularProgress, Dropdown, Switch } from '../ui';
import { AppConfig, UpdateStatus } from '../../types';
import { APP_VERSION } from '../../constants/version';

export interface AboutTabProps {
  config: AppConfig;
  onUpdateConfig: (key: keyof AppConfig, value: unknown) => void;
  onOpenGitHub: () => void;
  onOpenLogFile: () => void;
  onOpenLogFolder: () => void;
  updateStatus?: UpdateStatus | null;
  onCheckForUpdates?: () => void;
  onStartUpdateDownload?: () => void;
  onCancelUpdateDownload?: () => void;
  onRestartAndApplyUpdate?: () => void;
  updateBusy?: boolean;
}

export default function AboutTab({
  config,
  onUpdateConfig,
  onOpenGitHub,
  onOpenLogFile,
  onOpenLogFolder,
  updateStatus = null,
  onCheckForUpdates,
  onStartUpdateDownload,
  onCancelUpdateDownload,
  onRestartAndApplyUpdate,
  updateBusy = false,
}: AboutTabProps) {
  const [isApplying, setIsApplying] = useState(false);

  const handleToggle = (key: keyof AppConfig) => {
    onUpdateConfig(key, !config[key]);
  };

  const handleRestartClick = () => {
    setIsApplying(true);
    onRestartAndApplyUpdate?.();
  };

  const updateState = updateStatus?.state;
  const StatusIcon =
    updateState === 'up_to_date'
      ? CheckCircle2
      : updateState === 'error' || updateState === 'insufficient_space'
        ? AlertTriangle
        : updateState === 'available' || updateState === 'downloading' || updateState === 'ready'
          ? Download
          : updateState === 'waiting_for_idle'
            ? RefreshCw
          : null;

  return (
    <div className="about-page" style={{ fontSize: '0.88rem', color: 'var(--color-text)', lineHeight: 1.8 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px', marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <strong>Maple Classic Reporter</strong>
          <Badge variant="primary">v{APP_VERSION}</Badge>
        </div>
        <Button
          variant="outline"
          size="md"
          icon={ExternalLink}
          onClick={onOpenGitHub}
        >
          前往 GitHub 專案
        </Button>
      </div>

      <section
        className="about-update-panel"
        aria-labelledby="update-settings-heading"
        style={{
          padding: '14px 16px',
          backgroundColor: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-sm)',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <div>
            <div id="update-settings-heading" style={{ fontWeight: 700, color: 'var(--color-text-heading)' }}>
              應用程式更新
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
              啟動時檢查；開啟後會在背景下載，完成後由你決定何時重啟。
            </div>
          </div>
          <Switch
            checked={config.auto_update_enabled !== false}
            onChange={() => handleToggle('auto_update_enabled')}
            aria-label="開啟自動下載更新"
          />
        </div>

        <div className="setting-row no-border" style={{ paddingBlock: '4px' }}>
          <div className="setting-info">
            <span className="setting-label">更新頻道</span>
            <span className="setting-desc">穩定版或預覽版</span>
          </div>
          <div className="about-update-channel-control" style={{ width: '150px', minWidth: '140px' }}>
            <Dropdown<string>
              ariaLabel="更新頻道"
              options={[
                { value: 'stable', label: '穩定版' },
                { value: 'preview', label: '預覽版' },
              ]}
              value={config.update_channel || 'preview'}
              onChange={(value) => onUpdateConfig('update_channel', value)}
            />
          </div>
        </div>

        <div className="about-update-status-row">
          <div className="about-update-status" data-state={updateState || 'idle'}>
            {updateStatus?.state === 'downloading' && (
              <CircularProgress
                value={(updateStatus.progress_percent || 0) / 100}
                size={36}
                ariaLabel="更新下載進度"
                ariaValueNow={updateStatus.progress_percent || 0}
              >
                <span style={{ fontSize: '0.62rem', fontVariantNumeric: 'tabular-nums', fontWeight: 700 }}>
                  {Math.round(updateStatus.progress_percent || 0)}%
                </span>
              </CircularProgress>
            )}
            {StatusIcon && <StatusIcon size={16} aria-hidden="true" />}
            <span>
              {updateStatus?.state === 'up_to_date'
                ? '目前已是最新版'
                : updateStatus?.state === 'ready'
                ? `v${updateStatus.target_version || ''} 已下載完成`
                : updateStatus?.state === 'downloading'
                  ? `正在下載 v${updateStatus.target_version || ''}`
                  : updateStatus?.state === 'error' || updateStatus?.state === 'insufficient_space'
                    ? updateStatus.error_message || '更新失敗'
                    : updateStatus?.target_version
                      ? `有可用更新：v${updateStatus.target_version}`
                      : `目前版本 v${APP_VERSION}`}
            </span>
          </div>
          <div className="about-update-actions">
            <Button variant="outline" size="sm" onClick={onCheckForUpdates} disabled={updateStatus?.state === 'checking' || isApplying}>
              檢查更新
            </Button>
            {updateStatus?.state === 'available' && (
              <Button variant="primary" size="sm" icon={Download} onClick={onStartUpdateDownload} disabled={isApplying}>
                立即下載
              </Button>
            )}
            {updateStatus?.state === 'downloading' && (
              <Button variant="outline" size="sm" onClick={onCancelUpdateDownload} disabled={isApplying}>
                取消下載
              </Button>
            )}
            {(updateStatus?.state === 'ready' || updateStatus?.state === 'waiting_for_idle' || updateStatus?.state === 'applying') && (
              <Button
                variant="success"
                size="sm"
                icon={RefreshCw}
                onClick={handleRestartClick}
                disabled={isApplying || updateBusy || updateStatus.state === 'waiting_for_idle' || updateStatus.state === 'applying'}
              >
                {isApplying || updateStatus.state === 'applying'
                  ? '重啟中…'
                  : updateBusy || updateStatus.state === 'waiting_for_idle'
                    ? '完成後重啟'
                    : '重啟應用'}
              </Button>
            )}
          </div>
        </div>
        {updateStatus?.release_notes && updateStatus.target_version && (
          <details className="update-release-notes">
            <summary>查看 v{updateStatus.target_version} 更新內容</summary>
            <div style={{ whiteSpace: 'pre-wrap', color: 'var(--color-text-secondary)', fontSize: '0.78rem', lineHeight: 1.6 }}>
              {updateStatus.release_notes}
            </div>
          </details>
        )}
      </section>

      <p className="about-intro" style={{ color: 'var(--color-text-secondary)' }}>
        專為《新楓之谷：經典版》打造之外掛自動化檢舉與檢舉證據錄影桌面輔助工具。整合 RapidOCR 本地文字辨識、背景自動填表、WASAPI 系統音訊錄音與 Google Drive 雲端備份。本工具僅協助玩家錄影檢舉證據與送出官方檢舉表單，請勿用於任何違反遊戲服務條款之用途。
      </p>

      {/* 進階 / 開發者專用設定區塊 */}
      <div
        className="about-developer-panel"
        style={{
          padding: '14px 16px',
          backgroundColor: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-sm)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px',
        }}
      >
        <div>
          <div style={{ fontWeight: 600, color: 'var(--color-text-heading)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>開發者模式 (Dry-Run 模擬送出)</span>
            {config.dev_mode && <Badge variant="event" size="sm">已啟用</Badge>}
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
            開啟後，送出檢舉時不會真正提交官方表單，只會在系統瀏覽器開啟網頁並記錄檢舉證據供檢視與測試。
          </div>
        </div>
        <Switch
          checked={config.dev_mode || false}
          onChange={() => handleToggle('dev_mode')}
        />
      </div>

      {config.dev_mode && (
        <div
          className="about-dev-details"
          style={{
            padding: '12px 14px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--color-surface-hover)',
            border: '1px solid var(--color-border)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--color-text-heading)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>🛠️ 開發者除錯與 LOG 即時檢視</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
            • <strong>F12 / 右鍵「檢查」</strong>：視窗內已啟用 DevTools 控制台，可即時查看 Console 輸出與 Network 請求。<br />
            • <strong>後端 Python 日誌</strong>：包含文字辨識、官方處分比對、系統快捷鍵的完整除錯訊息。
          </div>
          <div style={{ display: 'flex', gap: '8px', marginTop: '4px', flexWrap: 'wrap' }}>
            <Button
              variant="secondary"
              size="sm"
              icon={FileText}
              onClick={onOpenLogFile}
            >
              開啟即時日誌 (reporter.log)
            </Button>
            <Button
              variant="outline"
              size="sm"
              icon={FolderOpen}
              onClick={onOpenLogFolder}
            >
              開啟 Log 資料夾
            </Button>
          </div>
        </div>
      )}

      <div className="about-license" style={{ fontSize: '0.78rem', color: 'var(--color-text-tertiary)' }}>
        版權所有 © 2026. 遵循 MIT 開源協議。
      </div>
    </div>
  );
}
