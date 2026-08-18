import { RefreshCw, FolderOpen, Trash2 } from 'lucide-react';
import { Switch, Dropdown, Input, Button, IconButton, Badge } from '../ui';
import { AppConfig, DropdownOption } from '../../types';
import PresetSlider from '../PresetSlider';
import { PresetKey } from '../../constants/presets';

export interface RecordingTabProps {
  config: AppConfig;
  windowOptions: DropdownOption<string>[];
  audioDeviceOptions: DropdownOption<string>[];
  fpsOptions: DropdownOption<number>[];
  countdownOptions: DropdownOption<number>[];
  onUpdateConfig: (key: keyof AppConfig, value: unknown) => void;
  onPresetChange: (presetKey: PresetKey) => void;
  onManualDurationChange: (val: number) => void;
  onManualFpsChange: (val: number) => void;
  onRefreshWindows?: () => void;
  onRefreshAudio?: () => void;
  onOpenAppData: () => void;
  onOpenClearModal: () => void;
}

export default function RecordingTab({
  config,
  windowOptions,
  audioDeviceOptions,
  fpsOptions,
  countdownOptions,
  onUpdateConfig,
  onPresetChange,
  onManualDurationChange,
  onManualFpsChange,
  onRefreshWindows,
  onRefreshAudio,
  onOpenAppData,
  onOpenClearModal,
}: RecordingTabProps) {
  const handleToggle = (key: keyof AppConfig) => {
    onUpdateConfig(key, !config[key]);
  };

  return (
    <>
      <div className="setting-row">
        <div className="setting-info">
          <span className="setting-label">目標遊戲視窗</span>
          <span className="setting-desc">鎖定並擷取畫面之 Windows 視窗</span>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ width: '260px', minWidth: '200px' }}>
            <Dropdown<string>
              options={windowOptions}
              value={config.selected_window_title || '新楓之谷：經典版 (1920x1080)'}
              onChange={(val) => onUpdateConfig('selected_window_title', val)}
            />
          </div>
          {onRefreshWindows && (
            <IconButton
              icon={RefreshCw}
              size="md"
              variant="ghost"
              tooltip="重新整理視窗清單"
              onClick={onRefreshWindows}
            />
          )}
        </div>
      </div>

      <div className="setting-row">
        <div style={{ width: '100%' }}>
          <PresetSlider
            preset={config.recording_preset}
            duration={config.record_duration_sec}
            fps={config.record_fps}
            replay={config.replay_buffer_sec}
            onChangePreset={onPresetChange}
          />
        </div>
      </div>

      <div className="setting-row">
        <div className="setting-info">
          <span className="setting-label">錄製短片秒數</span>
          <span className="setting-desc">一般短片錄影持續長度 (1 ~ 60 秒)</span>
        </div>
        <div style={{ width: '140px', minWidth: '120px' }}>
          <Input
            type="number"
            min="1"
            max="60"
            value={String(config.record_duration_sec || 8)}
            onChange={(e) => {
              const val = Math.max(1, Math.min(60, parseInt(e.target.value) || 8));
              onManualDurationChange(val);
            }}
          />
        </div>
      </div>

      <div className="setting-row">
        <div className="setting-info">
          <span className="setting-label">錄影流暢度 (FPS)</span>
          <span className="setting-desc">影格幀率，建議 20 ~ 30 FPS 兼顧效能與順暢度</span>
        </div>
        <div style={{ width: '140px', minWidth: '120px' }}>
          <Dropdown<number>
            options={fpsOptions}
            value={config.record_fps || 20}
            onChange={(val) => onManualFpsChange(val)}
          />
        </div>
      </div>

      <div className="setting-row">
        <div className="setting-info">
          <span className="setting-label">錄影前倒數時間</span>
          <span className="setting-desc">按下錄影後預留之準備倒數</span>
        </div>
        <div style={{ width: '180px', minWidth: '140px' }}>
          <Dropdown<number>
            options={countdownOptions}
            value={config.record_countdown_sec || 0}
            onChange={(val) => onUpdateConfig('record_countdown_sec', val)}
          />
        </div>
      </div>

      <div className="setting-row">
        <div className="setting-info">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="setting-label">同步錄製系統聲音 (WASAPI Loopback)</span>
            <Badge variant="success" size="sm">推薦開啟</Badge>
          </div>
          <span className="setting-desc">
            同步錄製遊戲內音效與背景音樂。推薦開啟，可聽到怪物死亡聲音協助判斷。
          </span>
        </div>
        <Switch
          checked={config.record_audio !== false}
          onChange={() => handleToggle('record_audio')}
        />
      </div>

      {config.record_audio !== false && (
        <div className="setting-row">
          <div className="setting-info">
            <span className="setting-label">系統聲音錄製來源</span>
            <span className="setting-desc">選擇目前實際播放遊戲聲音的 Windows 輸出裝置</span>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ width: '260px', minWidth: '200px' }}>
              <Dropdown<string>
                options={audioDeviceOptions}
                value={config.audio_output_device_id || ''}
                onChange={(val) => onUpdateConfig('audio_output_device_id', val)}
              />
            </div>
            {onRefreshAudio && (
              <IconButton
                icon={RefreshCw}
                size="md"
                variant="ghost"
                tooltip="重新整理音訊裝置"
                onClick={onRefreshAudio}
              />
            )}
          </div>
        </div>
      )}

      <div className="setting-row no-border">
        <div className="setting-info">
          <span className="setting-label">本機資料夾與檔案清理</span>
          <span className="setting-desc">開啟儲存目錄或清理暫存錄影以釋放容量</span>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <Button variant="secondary" size="md" icon={FolderOpen} onClick={onOpenAppData}>
            開啟本機資料夾
          </Button>
          <Button variant="danger" size="md" icon={Trash2} onClick={onOpenClearModal}>
            清理暫存檔案
          </Button>
        </div>
      </div>
    </>
  );
}
