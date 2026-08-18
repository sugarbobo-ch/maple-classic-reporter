import { ExternalLink, FileText, FolderOpen } from 'lucide-react';
import { Button, Badge, Switch } from '../ui';
import { AppConfig } from '../../types';
import { APP_VERSION } from '../../constants/version';

export interface AboutTabProps {
  config: AppConfig;
  onUpdateConfig: (key: keyof AppConfig, value: unknown) => void;
  onOpenGitHub: () => void;
  onOpenLogFile: () => void;
  onOpenLogFolder: () => void;
}

export default function AboutTab({
  config,
  onUpdateConfig,
  onOpenGitHub,
  onOpenLogFile,
  onOpenLogFolder,
}: AboutTabProps) {
  const handleToggle = (key: keyof AppConfig) => {
    onUpdateConfig(key, !config[key]);
  };

  return (
    <div style={{ fontSize: '0.88rem', color: 'var(--color-text)', lineHeight: 1.8 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px', marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <strong>Maple Classic Reporter</strong>
          <Badge variant="success">v{APP_VERSION} 最新版</Badge>
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

      <p style={{ color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
        專為《新楓之谷：經典版》打造之外掛自動化檢舉與事證錄製桌面輔助工具。整合 RapidOCR 本地高精準度文字辨識、Playwright 自動填表送出、WASAPI 系統音訊錄製與 Google Drive 雲端備份。本工具僅協助玩家錄製事證與送出官方檢舉表單，請勿用於任何違反遊戲服務條款之用途。
      </p>

      {/* 進階 / 開發者專用設定區塊 */}
      <div
        style={{
          marginTop: '16px',
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
            開啟後，送出檢舉時不會真正透過 Playwright 提交官方表單，僅在系統瀏覽器開啟網頁並記錄事證以供檢視與測試。
          </div>
        </div>
        <Switch
          checked={config.dev_mode || false}
          onChange={() => handleToggle('dev_mode')}
        />
      </div>

      {config.dev_mode && (
        <div
          style={{
            marginTop: '12px',
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
            • <strong>後端 Python 日誌</strong>：包含 OCR 辨識、公告制裁比對、系統熱鍵之完整 Debug 訊息。
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

      <div style={{ marginTop: '16px', fontSize: '0.78rem', color: 'var(--color-text-tertiary)' }}>
        版權所有 © 2026. 遵循 MIT 開源協議。
      </div>
    </div>
  );
}
