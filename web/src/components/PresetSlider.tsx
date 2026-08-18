import React, { useMemo } from 'react';
import { SlidersHorizontal } from 'lucide-react';
import { RECORDING_PRESETS, detectPresetKey, getPresetIndex, PresetKey } from '../constants/presets';

export interface PresetSliderProps {
  preset?: string;
  duration?: number;
  fps?: number;
  replay?: number;
  onChangePreset: (presetKey: PresetKey) => void;
}

export const PresetSlider: React.FC<PresetSliderProps> = ({
  preset,
  duration,
  fps,
  replay,
  onChangePreset,
}) => {
  // Detect whether the current values match a preset or are custom
  const detectedKey = useMemo(() => {
    return detectPresetKey(duration, fps, replay);
  }, [duration, fps, replay]);

  const activeKey = preset || detectedKey;
  const isCustom = activeKey === 'custom' || detectedKey === 'custom';

  const currentIndex = useMemo(() => {
    return getPresetIndex(activeKey);
  }, [activeKey]);

  const activePreset = RECORDING_PRESETS[currentIndex] || RECORDING_PRESETS[2];

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const nextIdx = parseInt(e.target.value, 10);
    if (!isNaN(nextIdx) && nextIdx >= 0 && nextIdx < RECORDING_PRESETS.length) {
      onChangePreset(RECORDING_PRESETS[nextIdx].key);
    }
  };

  const handleDotClick = (idx: number) => {
    if (idx >= 0 && idx < RECORDING_PRESETS.length) {
      onChangePreset(RECORDING_PRESETS[idx].key);
    }
  };

  // Calculate percentage for track (0%, 25%, 50%, 75%, 100%)
  const percentage = (currentIndex / (RECORDING_PRESETS.length - 1)) * 100;

  return (
    <div className="preset-slider-container">
      {/* Header Info */}
      <div className="preset-slider-header">
        <div className="preset-slider-title">
          <span>預設檔位</span>
        </div>
        <div className="preset-badge-wrap">
          {isCustom ? (
            <span className="preset-badge preset-badge-custom">
              <SlidersHorizontal size={12} /> 自訂模式
            </span>
          ) : (
            <span className="preset-badge preset-badge-active">
              {/* No icon on the left for balanced/presets */}
              {activePreset.label}
            </span>
          )}
          <div className="preset-params-tags">
            <span className="preset-param-tag">{duration ?? activePreset.duration}秒</span>
            <span className="preset-param-tag">{fps ?? activePreset.fps} FPS</span>
            <span className="preset-param-tag">循環 {replay ?? activePreset.replay}秒</span>
          </div>
        </div>
      </div>

      {/* Slider Interactive Area */}
      <div className="preset-track-wrapper">
        <div
          className={`preset-track-bg ${isCustom ? 'is-custom' : ''}`}
          style={{
            ['--preset-progress' as string]: `${percentage}%`,
          }}
        >
          {/* Active Flat Fill */}
          <div
            className={`preset-track-fill ${isCustom ? 'is-custom' : ''}`}
            style={{ width: `${percentage}%` }}
          />

          {/* Discrete Dots */}
          <div className="preset-dots-container">
            {RECORDING_PRESETS.map((p, idx) => {
              const dotPassed = idx <= currentIndex;
              const dotPercentage = (idx / (RECORDING_PRESETS.length - 1)) * 100;
              return (
                <button
                  key={p.key}
                  type="button"
                  className={`preset-dot ${dotPassed && !isCustom ? 'passed' : ''} ${
                    idx === currentIndex ? 'active' : ''
                  }`}
                  style={{ left: `${dotPercentage}%` }}
                  onClick={() => handleDotClick(idx)}
                  title={`${p.label} (${p.description})`}
                  aria-label={p.label}
                />
              );
            })}
          </div>

          {/* Visual Thumb */}
          <div
            className={`preset-visual-thumb ${isCustom ? 'is-custom' : ''}`}
            style={{ left: `${percentage}%` }}
          >
            <div className="preset-thumb-center-dot" />
          </div>

          {/* Native Hidden / Accessible Range Input */}
          <input
            type="range"
            min={0}
            max={RECORDING_PRESETS.length - 1}
            step={1}
            value={currentIndex}
            onChange={handleSliderChange}
            className="preset-range-input"
            aria-label="效能與畫質設定檔滑桿"
          />
        </div>
      </div>

      {/* Footer Labels */}
      <div className="preset-slider-footer">
        <span className="preset-label-side">較快 (省資源)</span>
        <span className="preset-label-side">更流暢 (高影格)</span>
      </div>
    </div>
  );
};

export default PresetSlider;
