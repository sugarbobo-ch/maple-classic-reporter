import {
  Video,
  Sliders,
  Volume2,
  VolumeX,
  Monitor,
  RotateCcw,
  RefreshCw,
  ChevronRight,
} from 'lucide-react';
import { Card, Button, Dropdown, IconButton, Badge } from './ui';
import { AppConfig, WindowItem, AudioDeviceItem, AudioCaptureMode, DropdownOption } from '../types';
import PresetPopup from './PresetPopup';
import { RECORDING_PRESETS, detectPresetKey, PresetKey } from '../constants/presets';

export interface QuickSettingsProps {
  config: AppConfig;
  windows?: WindowItem[];
  audioDevices?: AudioDeviceItem[];
  isInitializing?: boolean;
  onUpdateConfig: (key: string, value: unknown) => void;
  onUpdateConfigBatch?: (updates: Partial<AppConfig>) => void;
  onRefreshWindows?: () => void;
  onRefreshAudio?: () => void;
  onOpenSettings?: () => void;
}

export default function QuickSettings({
  config,
  windows = [],
  audioDevices = [],
  isInitializing = false,
  onUpdateConfig,
  onUpdateConfigBatch,
  onRefreshWindows,
  onRefreshAudio,
  onOpenSettings,
}: QuickSettingsProps) {
  const windowOptions: DropdownOption<string>[] =
    windows && windows.length > 0
      ? windows.map((w) => ({
          value: w.title,
          label: `${w.title} (${w.width}x${w.height})`,
        }))
      : [
          {
            value: '新楓之谷：經典版 (1920x1080)',
            label: '新楓之谷：經典版 (1920x1080)',
          },
        ];

  const audioOptions: DropdownOption<string>[] =
    audioDevices && audioDevices.length > 0
      ? audioDevices.map((a) => ({
          value: a.id,
          label: a.name,
        }))
      : [
          {
            value: 'default',
            label: 'Realtek Digital Output (系統預設)',
          },
        ];

  const audioModeOptions: DropdownOption<AudioCaptureMode>[] = [
    { value: 'process', label: '僅遊戲聲音' },
    { value: 'system', label: '所有系統聲音' },
    { value: 'off', label: '不錄音' },
  ];

  const fpsOptions: DropdownOption<number>[] = [
    { value: 15, label: '15 FPS' },
    { value: 20, label: '20 FPS' },
    { value: 30, label: '30 FPS' },
    { value: 60, label: '60 FPS' },
  ];

  const handlePresetChange = (presetKey: PresetKey) => {
    const selectedPreset = RECORDING_PRESETS.find((p) => p.key === presetKey);
    if (selectedPreset) {
      if (onUpdateConfigBatch) {
        onUpdateConfigBatch({
          recording_preset: selectedPreset.key,
          record_duration_sec: selectedPreset.duration,
          record_fps: selectedPreset.fps,
          replay_buffer_sec: selectedPreset.replay,
        });
      } else {
        onUpdateConfig('recording_preset', selectedPreset.key);
        onUpdateConfig('record_duration_sec', selectedPreset.duration);
        onUpdateConfig('record_fps', selectedPreset.fps);
        onUpdateConfig('replay_buffer_sec', selectedPreset.replay);
      }
    }
  };

  const handleManualDurationChange = (val: number) => {
    const nextDuration = Math.max(1, Math.min(60, val));
    onUpdateConfig('record_duration_sec', nextDuration);
    const matched = detectPresetKey(nextDuration, config.record_fps, config.replay_buffer_sec);
    onUpdateConfig('recording_preset', matched);
  };

  const handleManualFpsChange = (val: number) => {
    onUpdateConfig('record_fps', val);
    const matched = detectPresetKey(config.record_duration_sec, val, config.replay_buffer_sec);
    onUpdateConfig('recording_preset', matched);
  };

  const handleManualReplayChange = (val: number) => {
    const nextReplay = Math.max(5, Math.min(120, val));
    onUpdateConfig('replay_buffer_sec', nextReplay);
    const matched = detectPresetKey(config.record_duration_sec, config.record_fps, nextReplay);
    onUpdateConfig('recording_preset', matched);
  };

  const matchedWindowOption = windowOptions.find(
    (opt) =>
      opt.value === config.selected_window_title ||
      (config.selected_window_title &&
        (opt.value.includes(config.selected_window_title) ||
          config.selected_window_title.includes(opt.value)))
  );
  const selectedWindowValue = matchedWindowOption
    ? matchedWindowOption.value
    : windowOptions[0]?.value || '';

  const matchedAudioOption = audioOptions.find(
    (opt) =>
      opt.value === config.audio_output_device_id ||
      (Boolean(!config.audio_output_device_id) && (opt.value === '' || opt.value === 'default'))
  );
  const selectedAudioValue = matchedAudioOption
    ? matchedAudioOption.value
    : audioOptions[0]?.value || '';
  const audioMode: AudioCaptureMode =
    config.audio_capture_mode || (config.record_audio === false ? 'off' : 'system');

  const currentWindowTitle =
    selectedWindowValue ||
    config.selected_window_title ||
    (windowOptions[0] ? windowOptions[0].value : '');
  const isMapleDetected = Boolean(
    currentWindowTitle &&
    (currentWindowTitle.includes('新楓之谷') || currentWindowTitle.toLowerCase().includes('maple'))
  );

  return (
    <Card
      title="快捷設定"
      titleIcon={Sliders}
      variant="raised"
      headerAction={
        onOpenSettings && (
          <Button
            variant="outline"
            size="sm"
            icon={ChevronRight}
            iconPosition="right"
            onClick={onOpenSettings}
            title="開啟完整偏好設定"
          >
            進階設定
          </Button>
        )
      }
    >
      <div className="quick-settings-grid">
        {/* Screenshot Window Dropdown with Refresh IconButton */}
        <div className="form-group">
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '4px',
              minHeight: '24px',
            }}
          >
            <label
              className="ui-input-label"
              style={{
                marginBottom: 0,
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <Monitor
                size={14}
                color={isMapleDetected ? 'var(--color-primary)' : 'currentColor'}
                style={{
                  color: isMapleDetected ? 'var(--color-primary)' : 'inherit',
                }}
              />
              <span>截圖視窗</span>
              {isMapleDetected && (
                <Badge variant="primary" size="sm">
                  已偵測
                </Badge>
              )}
            </label>
          </div>
          <div
            style={{
              display: 'flex',
              gap: '8px',
              alignItems: 'center',
              opacity: isInitializing ? 0.45 : 1,
              transition: 'opacity 0.2s ease',
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <Dropdown
                disabled={isInitializing}
                placeholder={isInitializing ? '正在偵測遊戲視窗...' : '請選擇遊戲視窗...'}
                options={windowOptions}
                value={selectedWindowValue}
                onChange={(val) => onUpdateConfig('selected_window_title', val)}
              />
            </div>
            <IconButton
              disabled={isInitializing}
              icon={RefreshCw}
              size="md"
              variant="outline"
              tooltip="重新整理視窗清單"
              onClick={onRefreshWindows}
            />
          </div>
          <div
            style={{
              fontSize: '0.75rem',
              color: 'var(--color-text-secondary)',
              marginTop: '4px',
              lineHeight: '1.4',
            }}
          >
            鎖定遊戲視窗以截圖與錄影
          </div>
        </div>

        {/* Audio source stays compact; the endpoint row is revealed only for system mode. */}
        <div className="form-group">
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '4px',
              minHeight: '24px',
            }}
          >
            <label
              className="ui-input-label"
              style={{
                marginBottom: 0,
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              {audioMode === 'off' ? (
                <VolumeX size={14} color="var(--color-text-secondary)" />
              ) : (
                <Volume2
                  size={14}
                  color="var(--color-primary)"
                  style={{ color: 'var(--color-primary)' }}
                />
              )}
              <span>錄音來源</span>
            </label>
          </div>
          <div
            style={{
              opacity: isInitializing ? 0.45 : 1,
              transition: 'opacity 0.2s ease',
            }}
          >
            <Dropdown<AudioCaptureMode>
              disabled={isInitializing}
              options={audioModeOptions}
              value={audioMode}
              onChange={(val) => onUpdateConfig('audio_capture_mode', val)}
            />
          </div>
          <div
            style={{
              fontSize: '0.75rem',
              color: 'var(--color-text-secondary)',
              marginTop: '4px',
              lineHeight: '1.4',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span>
              {audioMode === 'process'
                ? `跟隨錄影視窗：${currentWindowTitle || '尚未選擇'}`
                : audioMode === 'system'
                  ? '包含其他應用程式與系統通知。'
                  : '影片將不包含聲音。'}
            </span>
          </div>
        </div>

        {audioMode === 'system' && (
          <div className="form-group audio-device-row">
            <label className="ui-input-label">系統聲音輸出裝置</label>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <Dropdown
                  disabled={isInitializing}
                  placeholder={isInitializing ? '正在偵測音訊裝置...' : '請選擇音訊裝置...'}
                  options={audioOptions}
                  value={selectedAudioValue}
                  onChange={(val) => onUpdateConfig('audio_output_device_id', val)}
                />
              </div>
              <IconButton
                disabled={isInitializing}
                icon={RefreshCw}
                size="md"
                variant="outline"
                tooltip="重新整理音訊裝置"
                onClick={onRefreshAudio}
              />
            </div>
          </div>
        )}

        {/* Video duration, FPS, Replay buffer & Preset Popup inline row */}
        <div className="settings-inline-row">
          <PresetPopup
            preset={config.recording_preset}
            duration={config.record_duration_sec}
            fps={config.record_fps}
            replay={config.replay_buffer_sec}
            onChangePreset={handlePresetChange}
          />

          <div className="inline-field">
            <Video size={15} color="var(--color-primary)" />
            <span style={{ fontWeight: 500, fontSize: '0.875rem' }}>錄影</span>
            <input
              type="number"
              className="ui-input-field"
              style={{
                width: '72px',
                height: 'var(--size-md)',
                fontSize: '0.875rem',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-sm)',
                padding: '0 8px',
                backgroundColor: 'var(--color-surface-card)',
                color: 'var(--color-text)',
              }}
              value={config.record_duration_sec || 8}
              onChange={(e) => handleManualDurationChange(parseInt(e.target.value) || 1)}
              min="1"
              max="60"
            />
            <span style={{ fontWeight: 500, fontSize: '0.875rem' }}>秒</span>
          </div>

          <div className="inline-field" style={{ width: '120px' }}>
            <span style={{ fontWeight: 500, fontSize: '0.875rem' }}>FPS</span>
            <Dropdown<number>
              options={fpsOptions}
              value={config.record_fps || 20}
              onChange={handleManualFpsChange}
            />
          </div>

          <div className="inline-field" style={{ marginLeft: '12px' }}>
            <RotateCcw size={15} color="var(--color-primary)" />
            <span style={{ fontWeight: 500, fontSize: '0.875rem' }}>循環錄影</span>
            <input
              type="number"
              className="ui-input-field"
              style={{
                width: '72px',
                height: 'var(--size-md)',
                fontSize: '0.875rem',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-sm)',
                padding: '0 8px',
                backgroundColor: 'var(--color-surface-card)',
                color: 'var(--color-text)',
              }}
              value={config.replay_buffer_sec || 20}
              onChange={(e) => handleManualReplayChange(parseInt(e.target.value) || 1)}
              min="5"
              max="120"
            />
            <span style={{ fontWeight: 500, fontSize: '0.875rem' }}>秒</span>
          </div>
        </div>
      </div>
    </Card>
  );
}
