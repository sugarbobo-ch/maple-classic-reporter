import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import PresetSlider from '../src/components/PresetSlider';
import { detectPresetKey } from '../src/constants/presets';

describe('PresetSlider Component & Helpers', () => {
  it('detects standard presets correctly', () => {
    expect(detectPresetKey(5, 15, 10)).toBe('ultra_fast');
    expect(detectPresetKey(6, 20, 15)).toBe('smooth');
    expect(detectPresetKey(8, 20, 20)).toBe('balanced');
    expect(detectPresetKey(8, 30, 25)).toBe('high_fps');
    expect(detectPresetKey(10, 30, 30)).toBe('extreme');
    expect(detectPresetKey(7, 20, 20)).toBe('custom');
  });

  it('renders balanced preset by default and calls onChangePreset on slider change', () => {
    const onChangePreset = vi.fn();
    render(
      <PresetSlider
        preset="balanced"
        duration={8}
        fps={20}
        replay={20}
        onChangePreset={onChangePreset}
      />
    );

    expect(screen.getByText('平衡 (推薦)')).toBeInTheDocument();
    expect(screen.getByText('8秒')).toBeInTheDocument();
    expect(screen.getByText('20 FPS')).toBeInTheDocument();
    expect(screen.getByText('循環 20秒')).toBeInTheDocument();
    expect(screen.getByText('較快 (省資源)')).toBeInTheDocument();
    expect(screen.getByText('更流暢 (高影格)')).toBeInTheDocument();

    const rangeInput = screen.getByLabelText('效能與畫質設定檔滑桿');
    fireEvent.change(rangeInput, { target: { value: '0' } });

    expect(onChangePreset).toHaveBeenCalledWith('ultra_fast');
  });

  it('displays custom mode tag when custom values are passed', () => {
    const onChangePreset = vi.fn();
    render(
      <PresetSlider
        preset="custom"
        duration={12}
        fps={45}
        replay={50}
        onChangePreset={onChangePreset}
      />
    );

    expect(screen.getByText('自訂模式')).toBeInTheDocument();
    expect(screen.getByText('12秒')).toBeInTheDocument();
    expect(screen.getByText('45 FPS')).toBeInTheDocument();
    expect(screen.getByText('循環 50秒')).toBeInTheDocument();
  });
});
