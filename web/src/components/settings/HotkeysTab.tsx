import { Keyboard } from 'lucide-react';
import { Switch, Dropdown } from '../ui';
import { AppConfig, DropdownOption } from '../../types';

export interface HotkeysTabProps {
  config: AppConfig;
  listeningForHotkey: 'save_replay' | 'record_video' | null;
  hotkeyKeyOptions: DropdownOption<string>[];
  saveReplayKey: string;
  recordVideoKey: string;
  onUpdateConfig: (key: keyof AppConfig, value: unknown) => void;
  onUpdateHotkey?: (key: 'save_replay_hotkey' | 'record_video_hotkey', value: string) => void;
  onSetListeningForHotkey: (val: 'save_replay' | 'record_video' | null) => void;
}

export default function HotkeysTab({
  config,
  listeningForHotkey,
  hotkeyKeyOptions,
  saveReplayKey,
  recordVideoKey,
  onUpdateConfig,
  onUpdateHotkey,
  onSetListeningForHotkey,
}: HotkeysTabProps) {
  const handleToggle = (key: keyof AppConfig) => {
    onUpdateConfig(key, !config[key]);
  };

  return (
    <>
      <div className="setting-row">
        <div className="setting-info">
          <span className="setting-label">啟用快捷鍵</span>
          <span className="setting-desc">遊戲視窗在前景時依然有效（Ctrl 與 Shift 固定）</span>
        </div>
        <Switch
          checked={config.global_hotkeys_enabled !== false}
          onChange={() => handleToggle('global_hotkeys_enabled')}
        />
      </div>

      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
          opacity: config.global_hotkeys_enabled !== false ? 1 : 0.4,
          pointerEvents: config.global_hotkeys_enabled !== false ? 'auto' : 'none',
          transition: 'opacity 0.2s ease',
        }}
      >
        <div className="setting-row">
          <div className="setting-info">
            <span className="setting-label">儲存循環影片快捷鍵</span>
            <span className="setting-desc">
              {listeningForHotkey === 'save_replay'
                ? '請在鍵盤上按下任意按鍵（如 F9、S、R 等，按 Esc 取消）'
                : '點擊按鈕後直接按下鍵盤按鍵即可自動偵測設定'}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <button
              type="button"
              disabled={config.global_hotkeys_enabled === false}
              className={`ui-btn ui-btn-md ${
                listeningForHotkey === 'save_replay' ? 'ui-btn-primary' : 'ui-btn-outline'
              }`}
              style={{
                minWidth: '160px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                justifyContent: 'center',
              }}
              onClick={() =>
                onSetListeningForHotkey(
                  listeningForHotkey === 'save_replay' ? null : 'save_replay'
                )
              }
            >
              <Keyboard size={16} />
              <span>
                {listeningForHotkey === 'save_replay'
                  ? '聆聽按鍵中...'
                  : config.save_replay_hotkey || 'Ctrl+Shift+F9'}
              </span>
            </button>
            <div style={{ width: '100px' }}>
              <Dropdown<string>
                disabled={config.global_hotkeys_enabled === false}
                options={hotkeyKeyOptions}
                value={saveReplayKey}
                onChange={(val) => {
                  const shortcut = `Ctrl+Shift+${val}`;
                  if (onUpdateHotkey) {
                    onUpdateHotkey('save_replay_hotkey', shortcut);
                  } else {
                    onUpdateConfig('save_replay_hotkey', shortcut);
                  }
                }}
              />
            </div>
          </div>
        </div>

        <div className="setting-row">
          <div className="setting-info">
            <span className="setting-label">開始一般錄影快捷鍵</span>
            <span className="setting-desc">
              {listeningForHotkey === 'record_video'
                ? '請在鍵盤上按下任意按鍵（如 F10、R、V 等，按 Esc 取消）'
                : '點擊按鈕後直接按下鍵盤按鍵即可自動偵測設定'}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <button
              type="button"
              disabled={config.global_hotkeys_enabled === false}
              className={`ui-btn ui-btn-md ${
                listeningForHotkey === 'record_video' ? 'ui-btn-primary' : 'ui-btn-outline'
              }`}
              style={{
                minWidth: '160px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                justifyContent: 'center',
              }}
              onClick={() =>
                onSetListeningForHotkey(
                  listeningForHotkey === 'record_video' ? null : 'record_video'
                )
              }
            >
              <Keyboard size={16} />
              <span>
                {listeningForHotkey === 'record_video'
                  ? '聆聽按鍵中...'
                  : config.record_video_hotkey || 'Ctrl+Shift+F10'}
              </span>
            </button>
            <div style={{ width: '100px' }}>
              <Dropdown<string>
                disabled={config.global_hotkeys_enabled === false}
                options={hotkeyKeyOptions}
                value={recordVideoKey}
                onChange={(val) => {
                  const shortcut = `Ctrl+Shift+${val}`;
                  if (onUpdateHotkey) {
                    onUpdateHotkey('record_video_hotkey', shortcut);
                  } else {
                    onUpdateConfig('record_video_hotkey', shortcut);
                  }
                }}
              />
            </div>
          </div>
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
          快捷鍵使用說明：
        </div>
        Windows 系統快捷鍵會在遊戲視窗前景時保持有效，不會攔截遊戲內的其他操作。建議使用 <code>Ctrl + Shift + S</code> 儲存影片片段與 <code>Ctrl + Shift + R</code> 開始錄影，以避免單鍵衝突。
      </div>
    </>
  );
}
