import { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Download,
  ExternalLink,
  FileText,
  FolderOpen,
  RefreshCw,
  Wrench,
} from 'lucide-react';
import { Button, Badge, CircularProgress, Dropdown, MarkdownContent, Switch } from '../ui';
import { AppConfig, UpdateStatus } from '../../types';
import { APP_VERSION } from '../../constants/version';

export interface AboutTabProps {
  config: AppConfig;
  onUpdateConfig: (key: keyof AppConfig, value: unknown) => void;
  onOpenGitHub: () => void;
  onOpenExternalUrl?: (url: string) => void;
  onOpenLogFile: () => void;
  onOpenLogFolder: () => void;
  updateStatus?: UpdateStatus | null;
  onCheckForUpdates?: () => void;
  onStartUpdateDownload?: () => void;
  onCancelUpdateDownload?: () => void;
  onRestartAndApplyUpdate?: () => void;
  updateBusy?: boolean;
  onReplayOnboarding?: () => void;
}

export default function AboutTab({
  config,
  onUpdateConfig,
  onOpenGitHub,
  onOpenExternalUrl,
  onOpenLogFile,
  onOpenLogFolder,
  updateStatus = null,
  onCheckForUpdates,
  onStartUpdateDownload,
  onCancelUpdateDownload,
  onRestartAndApplyUpdate,
  updateBusy = false,
  onReplayOnboarding,
}: AboutTabProps) {
  const [isApplying, setIsApplying] = useState(false);

  const formatBytes = (bytes: number) => {
    if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const unitIndex = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / 1024 ** unitIndex;
    const fractionDigits = unitIndex === 0 ? 0 : value >= 10 ? 0 : 1;
    return `${value.toFixed(fractionDigits)} ${units[unitIndex]}`;
  };

  const packageLabel = updateStatus?.package_kind === 'delta' ? '差分包' : '完整包';

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
    <div className="about-page">
      <div className="about-identity-header">
        <div className="about-identity">
          <h2 className="about-product-title">Maple Classic Reporter</h2>
          <Badge variant="primary">v{APP_VERSION}</Badge>
        </div>
        <Button variant="outline" size="md" icon={ExternalLink} onClick={onOpenGitHub}>
          前往 GitHub 專案
        </Button>
      </div>

      <p className="about-intro">
        專為《新楓之谷：經典版》打造之外掛自動化檢舉與檢舉證據錄影桌面輔助工具。整合 RapidOCR
        本機文字辨識、背景靜默送出檢舉、可選擇的錄音來源與 Google Drive
        雲端備份。本工具僅協助玩家建立檢舉證據與送出官方檢舉表單，請勿用於任何違反遊戲服務條款之用途。
      </p>

      {onReplayOnboarding && (
        <section className="about-tutorial-panel" aria-labelledby="tutorial-heading">
          <div>
            <h2 id="tutorial-heading">設定教學</h2>
            <p>重新查看蒐證流程，並依序檢查錄影、辨識、上傳與檢舉設定。</p>
          </div>
          <Button variant="secondary" size="md" onClick={onReplayOnboarding}>
            重新開啟設定教學
          </Button>
        </section>
      )}

      <section
        className="about-update-panel"
        aria-labelledby="update-settings-heading"
      >
        <div className="about-update-header">
          <div>
            <h2 id="update-settings-heading" className="about-update-title">
              應用程式更新
            </h2>
            <div className="about-update-description">
              啟動時檢查；開啟後會在背景下載，完成後由你決定何時重啟。
            </div>
          </div>
          <Switch
            checked={config.auto_update_enabled !== false}
            onChange={() => handleToggle('auto_update_enabled')}
            aria-label="開啟自動下載更新"
          />
        </div>

        <div className="setting-row no-border about-update-channel-row">
          <div className="setting-info">
            <span className="setting-label">更新頻道</span>
            <span className="setting-desc">穩定版或預覽版</span>
          </div>
          <div className="about-update-channel-control">
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
                <span className="about-update-progress-value">
                  {Math.round(updateStatus.progress_percent || 0)}%
                </span>
              </CircularProgress>
            )}
            {StatusIcon && <StatusIcon size={16} aria-hidden="true" />}
            <span>
              {updateStatus?.state === 'checking'
                ? '正在檢查更新'
                : updateStatus?.state === 'up_to_date'
                  ? '目前已是最新版'
                  : updateStatus?.state === 'ready'
                    ? `v${updateStatus.target_version || ''} 已下載完成`
                    : updateStatus?.state === 'downloading'
                      ? `正在下載 v${updateStatus.target_version || ''}`
                      : updateStatus?.state === 'error' ||
                          updateStatus?.state === 'insufficient_space'
                        ? updateStatus.error_message || '更新失敗'
                        : updateStatus?.target_version
                          ? `有可用更新：v${updateStatus.target_version}`
                          : `目前版本 v${APP_VERSION}`}
            </span>
          </div>
          <div className="about-update-actions">
            <Button
              variant="outline"
              size="sm"
              onClick={onCheckForUpdates}
              disabled={
                updateStatus?.state === 'checking' ||
                updateStatus?.state === 'downloading' ||
                updateStatus?.state === 'applying' ||
                updateStatus?.state === 'waiting_for_idle' ||
                isApplying
              }
              loading={updateStatus?.state === 'checking'}
            >
              檢查更新
            </Button>
            {updateStatus?.state === 'available' && (
              <Button
                variant="primary"
                size="sm"
                icon={Download}
                onClick={onStartUpdateDownload}
                disabled={isApplying}
              >
                立即下載
              </Button>
            )}
            {updateStatus?.state === 'downloading' && (
              <Button
                variant="outline"
                size="sm"
                onClick={onCancelUpdateDownload}
                disabled={isApplying}
              >
                取消下載
              </Button>
            )}
            {(updateStatus?.state === 'ready' ||
              updateStatus?.state === 'waiting_for_idle' ||
              updateStatus?.state === 'applying') && (
              <Button
                variant="success"
                size="sm"
                icon={RefreshCw}
                onClick={handleRestartClick}
                disabled={
                  isApplying ||
                  updateBusy ||
                  updateStatus.state === 'waiting_for_idle' ||
                  updateStatus.state === 'applying'
                }
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
        {updateStatus?.target_version && (
          <div className="about-update-metadata" role="group" aria-label="更新詳細資料">
            {updateStatus.package_kind && <span>套件：{packageLabel}</span>}
            {updateStatus.total_bytes > 0 && (
              <span>
                下載：{formatBytes(updateStatus.downloaded_bytes)} /{' '}
                {formatBytes(updateStatus.total_bytes)}
              </span>
            )}
            {(updateStatus.required_bytes > 0 || updateStatus.available_bytes > 0) && (
              <span>
                空間：需要 {formatBytes(updateStatus.required_bytes)}，可用{' '}
                {formatBytes(updateStatus.available_bytes)}
              </span>
            )}
          </div>
        )}
        {updateStatus?.target_version && (
          <details className="update-release-notes">
            <summary>
              <span className="update-release-notes-summary-copy">
                <span>更新內容</span>
                <span className="update-release-notes-version">v{updateStatus.target_version}</span>
              </span>
              <ChevronRight className="update-release-notes-chevron" size={16} aria-hidden="true" />
            </summary>
            <div className="update-release-notes-body">
              <MarkdownContent source={updateStatus.release_notes} onOpenLink={onOpenExternalUrl} />
              {updateStatus.release_url && (
                <a
                  className="update-release-link"
                  href={updateStatus.release_url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(event) => {
                    if (!onOpenExternalUrl) return;
                    event.preventDefault();
                    onOpenExternalUrl(updateStatus.release_url!);
                  }}
                >
                  在 GitHub 查看完整 Release
                  <ExternalLink size={14} aria-hidden="true" />
                </a>
              )}
            </div>
          </details>
        )}
      </section>

      {/* 進階 / 開發者專用設定區塊 */}
      <div className="about-developer-panel">
        <div>
          <div className="about-developer-label">
            <span>開發者模式 (Dry-Run 模擬送出)</span>
            {config.dev_mode && (
              <Badge variant="event" size="sm">
                已啟用
              </Badge>
            )}
          </div>
          <div className="about-developer-description">
            開啟後，送出檢舉時不會真正提交官方表單，只會在系統瀏覽器開啟網頁並記錄檢舉證據供檢視與測試。
          </div>
        </div>
        <Switch checked={config.dev_mode || false} onChange={() => handleToggle('dev_mode')} />
      </div>

      {config.dev_mode && (
        <div className="about-dev-details">
          <div className="about-dev-details-title">
            <Wrench size={14} aria-hidden="true" />
            <span>開發者除錯與 LOG 即時檢視</span>
          </div>
          <div className="about-dev-details-description">
            • <strong>F12 / 右鍵「檢查」</strong>：視窗內已啟用 DevTools 控制台，可即時查看 Console
            輸出與 Network 請求。
            <br />• <strong>後端 Python 日誌</strong>
            ：包含文字辨識、官方處分比對、系統快捷鍵的完整除錯訊息。
          </div>
          <div className="about-dev-actions">
            <Button variant="secondary" size="sm" icon={FileText} onClick={onOpenLogFile}>
              開啟即時日誌 (reporter.log)
            </Button>
            <Button variant="outline" size="sm" icon={FolderOpen} onClick={onOpenLogFolder}>
              開啟 Log 資料夾
            </Button>
          </div>
        </div>
      )}

      <div className="about-license">
        版權所有 © 2026. 遵循 MIT 開源協議。
      </div>
    </div>
  );
}
