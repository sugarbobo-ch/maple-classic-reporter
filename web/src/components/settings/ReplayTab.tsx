import { Dropdown } from '../ui';
import { AppConfig, DropdownOption } from '../../types';
import PresetSlider from '../PresetSlider';
import SettingRow from './SettingRow';
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
      <SettingRow>
        <PresetSlider
          preset={config.recording_preset}
          duration={config.record_duration_sec}
          fps={config.record_fps}
          replay={config.replay_buffer_sec}
          onChangePreset={onPresetChange}
        />
      </SettingRow>

      <div className="setting-row">
        <div className="setting-info">
          <span className="setting-label">循環錄影保留秒數</span>
          <span className="setting-desc">持續在記憶體與背景循環保留最近一段遊戲畫面 (最多 30 秒)</span>
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
          循環錄影運作機制說明：
        </div>
        啟動後會像行車記錄器般持續維護滑動時間線，自動循環保留最近一段畫面與聲音；超過設定秒數的內容會自動釋放。按下「儲存循環錄影」或全域快捷鍵僅會導出當下時間窗影片並加密採樣最後
        5 秒影格進行 OCR 辨識，背景循環錄影不會中斷。
      </div>
    </>
  );
}
