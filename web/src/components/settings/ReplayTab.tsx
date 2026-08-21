import { Dropdown } from '../ui';
import { AppConfig, DropdownOption } from '../../types';
import PresetSlider from '../PresetSlider';
import { PresetKey } from '../../constants/presets';

export interface ReplayTabProps {
  config: AppConfig;
  replayPresetOptions: DropdownOption<number>[];
  onPresetChange: (presetKey: PresetKey) => void;
  onManualReplayChange: (val: number) => void;
}

export default function ReplayTab({
  config,
  replayPresetOptions,
  onPresetChange,
  onManualReplayChange,
}: ReplayTabProps) {
  return (
    <>
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
          <span className="setting-label">循環錄影保留秒數</span>
          <span className="setting-desc">
          持續在背景保留最近一段遊戲畫面（最多 30 秒）
          </span>
        </div>
        <div style={{ width: '160px', minWidth: '140px' }}>
          <Dropdown<number>
            options={replayPresetOptions}
            value={config.replay_buffer_sec || 20}
            onChange={(val) => onManualReplayChange(val)}
          />
        </div>
      </div>

      <div
        style={{
          padding: '12px 16px',
          backgroundColor: 'var(--color-surface-card)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-md)',
          fontSize: '0.82rem',
          lineHeight: 1.6,
          color: 'var(--color-text-secondary)',
          marginTop: '4px',
        }}
      >
        <div style={{ fontWeight: 700, color: 'var(--color-text-heading)', marginBottom: '4px' }}>
          循環錄影運作方式：
        </div>
        啟動後會像行車記錄器一樣持續保留最近一段畫面與聲音；超過設定秒數的內容會自動刪除。按下「儲存循環錄影」或快捷鍵只會輸出目前時間範圍的影片，並分析最後
        5 秒畫面，背景循環錄影不會中斷。
      </div>
    </>
  );
}
