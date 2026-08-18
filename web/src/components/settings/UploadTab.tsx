import { FolderOpen, Send, CheckCircle, AlertCircle } from 'lucide-react';
import { Dropdown, Input, Button, Badge } from '../ui';
import { AppConfig, DropdownOption } from '../../types';

export interface UploadTabProps {
  config: AppConfig;
  destinationOptions: DropdownOption<'gdrive' | 'discord'>[];
  gdriveFolder: string;
  discordWebhook: string;
  testingDiscord: boolean;
  gdriveAuthenticated: boolean | null;
  gdriveAuthLoading: boolean;
  onUpdateConfig: (key: keyof AppConfig, value: unknown) => void;
  onGdriveFolderChange: (val: string) => void;
  onDiscordWebhookChange: (val: string) => void;
  onAuthenticateDrive: () => void;
  onOpenDriveFolder: () => void;
  onTestDiscord: () => void;
}

export default function UploadTab({
  config,
  destinationOptions,
  gdriveFolder,
  discordWebhook,
  testingDiscord,
  gdriveAuthenticated,
  gdriveAuthLoading,
  onUpdateConfig,
  onGdriveFolderChange,
  onDiscordWebhookChange,
  onAuthenticateDrive,
  onOpenDriveFolder,
  onTestDiscord,
}: UploadTabProps) {
  return (
    <>
      <div className="setting-row">
        <div className="setting-info">
          <span className="setting-label">Google Drive 授權狀態</span>
          <span className="setting-desc">用於長期儲存高畫質檢舉影片與照片</span>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <Badge
            variant={gdriveAuthenticated ? 'success' : 'warning'}
            icon={gdriveAuthenticated ? CheckCircle : AlertCircle}
            data-testid="gdrive-auth-status"
            aria-live="polite"
          >
            {gdriveAuthenticated ? '已授權' : '尚未授權'}
          </Badge>
          <Button
            variant="outline"
            size="md"
            onClick={onAuthenticateDrive}
            loading={gdriveAuthLoading}
            disabled={gdriveAuthLoading}
          >
            {gdriveAuthLoading ? '授權中…' : gdriveAuthenticated ? '重新驗證' : '開始授權'}
          </Button>
        </div>
      </div>

      {/* 前往雲端資料夾整合於此 */}
      <div className="setting-row">
        <div className="setting-info">
          <span className="setting-label">Google Drive 資料夾名稱</span>
          <span className="setting-desc">雲端硬碟存放事證之目錄名稱</span>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ width: '220px', minWidth: '180px' }}>
            <Input
              placeholder="MapleClassic_Reports"
              value={gdriveFolder}
              onChange={(e) => onGdriveFolderChange(e.target.value)}
            />
          </div>
          <Button
            variant="secondary"
            size="md"
            icon={FolderOpen}
            onClick={onOpenDriveFolder}
          >
            前往雲端資料夾
          </Button>
        </div>
      </div>

      <div className="setting-row">
        <div className="setting-info">
          <span className="setting-label">Discord Webhook URL</span>
          <span className="setting-desc">頻道即時通報與短片快速分享</span>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ width: '220px', minWidth: '180px' }}>
            <Input
              type="password"
              placeholder="https://discord.com/api/webhooks/..."
              value={discordWebhook}
              onChange={(e) => onDiscordWebhookChange(e.target.value)}
            />
          </div>
          <Button
            variant="secondary"
            size="md"
            icon={Send}
            onClick={onTestDiscord}
            disabled={testingDiscord}
          >
            {testingDiscord ? '測試中...' : '測試連線'}
          </Button>
        </div>
      </div>

      <div className="setting-row no-border">
        <div className="setting-info">
          <span className="setting-label">優先上傳目的地</span>
          <span className="setting-desc">自動選擇預設上傳管道</span>
        </div>
        <div style={{ width: '200px', minWidth: '160px' }}>
          <Dropdown<'gdrive' | 'discord'>
            options={destinationOptions}
            value={config.upload_destination || 'gdrive'}
            onChange={(val) => onUpdateConfig('upload_destination', val)}
          />
        </div>
      </div>
    </>
  );
}
