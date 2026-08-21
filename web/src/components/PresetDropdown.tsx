import React, { useMemo } from 'react';
import { Dropdown } from './ui';
import { RECORDING_PRESETS, detectPresetKey, PresetKey } from '../constants/presets';
import { DropdownOption } from '../types';

export interface PresetDropdownProps {
  preset?: string;
  duration?: number;
  fps?: number;
  replay?: number;
  onChangePreset: (presetKey: PresetKey) => void;
  label?: React.ReactNode;
}

export const PresetDropdown: React.FC<PresetDropdownProps> = ({
  preset,
  duration,
  fps,
  replay,
  onChangePreset,
  label = '錄影模式',
}) => {
  const detectedKey = useMemo(() => {
    return detectPresetKey(duration, fps, replay);
  }, [duration, fps, replay]);

  const activeKey = preset || detectedKey;
  const isCustom = activeKey === 'custom' || detectedKey === 'custom';

  const options = useMemo<DropdownOption<string>[]>(() => {
    const list: DropdownOption<string>[] = RECORDING_PRESETS.map((p) => ({
      value: p.key,
      label: `${p.label} (${p.description})`,
      // Explicitly no icon on the left for all options including balanced
    }));

    if (isCustom) {
      list.push({
        value: 'custom',
        label: `自訂模式 (${duration ?? 8}秒 / ${fps ?? 20} FPS / 循環 ${replay ?? 20}秒)`,
      });
    }

    return list;
  }, [isCustom, duration, fps, replay]);

  const handleChange = (val: string) => {
    if (val !== 'custom') {
      onChangePreset(val as PresetKey);
    }
  };

  const activePreset = RECORDING_PRESETS.find((p) => p.key === activeKey);

  return (
    <div className="preset-dropdown-container">
      {label && <label className="ui-input-label">{label}</label>}
      <Dropdown
        options={options}
        value={activeKey}
        onChange={handleChange}
        placeholder="選擇錄影模式..."
      />
      <div className="preset-params-tags" style={{ marginTop: '6px' }}>
        <span className="preset-param-tag">{duration ?? activePreset?.duration ?? 8}秒</span>
        <span className="preset-param-tag">{fps ?? activePreset?.fps ?? 20} FPS</span>
        <span className="preset-param-tag">循環 {replay ?? activePreset?.replay ?? 20}秒</span>
        {isCustom && <span className="preset-param-tag preset-tag-custom">自訂</span>}
      </div>
    </div>
  );
};

export default PresetDropdown;
