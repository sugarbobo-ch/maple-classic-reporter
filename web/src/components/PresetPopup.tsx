import React, { useRef, useMemo } from 'react';
import ReactDOM from 'react-dom';
import { SlidersHorizontal, ChevronDown } from 'lucide-react';
import { useAnchorPosition, useClickOutside, useDisclosure } from '../hooks';
import { RECORDING_PRESETS, detectPresetKey, PresetKey } from '../constants/presets';
import PresetSlider from './PresetSlider';

export interface PresetPopupProps {
  preset?: string;
  duration?: number;
  fps?: number;
  replay?: number;
  onChangePreset: (presetKey: PresetKey) => void;
  className?: string;
}

export const PresetPopup: React.FC<PresetPopupProps> = ({
  preset,
  duration,
  fps,
  replay,
  onChangePreset,
  className = '',
}) => {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);

  const { isOpen, toggle, close } = useDisclosure();

  const detectedKey = useMemo(() => {
    return detectPresetKey(duration, fps, replay);
  }, [duration, fps, replay]);

  const activeKey = preset || detectedKey;
  const isCustom = activeKey === 'custom' || detectedKey === 'custom';
  const activePreset = RECORDING_PRESETS.find((p) => p.key === activeKey) || RECORDING_PRESETS[2];

  const { position } = useAnchorPosition(triggerRef, {
    enabled: isOpen,
    estimatedHeight: 180,
    autoFlip: true,
  });

  useClickOutside([triggerRef, popupRef], close, isOpen);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      close();
    } else if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
      e.preventDefault();
      toggle();
    }
  };

  const labelText = isCustom ? '自訂' : activePreset.label;

  return (
    <div className={`preset-popup-wrapper ${className}`.trim()}>
      <button
        type="button"
        ref={triggerRef}
        className={`preset-popup-trigger ${isOpen ? 'open' : ''}`}
        onClick={toggle}
        onKeyDown={handleKeyDown}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        title="點擊展開錄製檔位調整滑桿"
      >
        <SlidersHorizontal size={14} color="var(--color-primary)" />
        <span className="preset-trigger-text">檔位：{labelText}</span>
        <ChevronDown size={13} className={`preset-trigger-chevron ${isOpen ? 'open' : ''}`} />
      </button>

      {isOpen &&
        ReactDOM.createPortal(
          <div
            ref={popupRef}
            className="preset-popup-content"
            style={{
              position: 'fixed',
              top: `${position.top}px`,
              left: `${Math.max(10, Math.min(position.left, window.innerWidth - 370))}px`,
              width: '360px',
              zIndex: 9999,
            }}
          >
            <PresetSlider
              preset={preset}
              duration={duration}
              fps={fps}
              replay={replay}
              onChangePreset={onChangePreset}
            />
          </div>,
          document.body
        )}
    </div>
  );
};

export default PresetPopup;
