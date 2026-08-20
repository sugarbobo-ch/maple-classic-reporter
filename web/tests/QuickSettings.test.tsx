import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import QuickSettings from '../src/components/QuickSettings';
import { TEST_CONFIG, TEST_AUDIO_DEVICES, TEST_WINDOWS } from './mockPyWebViewApi';

describe('QuickSettings audio source', () => {
  it('keeps the endpoint selector hidden for process and off modes', () => {
    const { container, rerender } = render(
      <QuickSettings
        config={{ ...TEST_CONFIG, audio_capture_mode: 'process' }}
        windows={TEST_WINDOWS}
        audioDevices={TEST_AUDIO_DEVICES}
        onUpdateConfig={vi.fn()}
      />
    );

    expect(container.querySelector('.audio-device-row')).not.toBeInTheDocument();
    expect(screen.getByText('跟隨錄影視窗：MapleStory Classic')).toBeInTheDocument();

    rerender(
      <QuickSettings
        config={{ ...TEST_CONFIG, audio_capture_mode: 'off' }}
        windows={TEST_WINDOWS}
        audioDevices={TEST_AUDIO_DEVICES}
        onUpdateConfig={vi.fn()}
      />
    );
    expect(container.querySelector('.audio-device-row')).not.toBeInTheDocument();
    expect(screen.getByText('影片將不包含聲音。')).toBeInTheDocument();
  });

  it('reveals the full-width endpoint row only for system audio', () => {
    const onUpdateConfig = vi.fn();
    const { container, rerender } = render(
      <QuickSettings
        config={{ ...TEST_CONFIG, audio_capture_mode: 'process' }}
        windows={TEST_WINDOWS}
        audioDevices={TEST_AUDIO_DEVICES}
        onUpdateConfig={onUpdateConfig}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: '僅遊戲聲音' }));
    fireEvent.click(screen.getByRole('option', { name: '所有系統聲音' }));
    expect(onUpdateConfig).toHaveBeenCalledWith('audio_capture_mode', 'system');

    rerender(
      <QuickSettings
        config={{ ...TEST_CONFIG, audio_capture_mode: 'system' }}
        windows={TEST_WINDOWS}
        audioDevices={TEST_AUDIO_DEVICES}
        onUpdateConfig={onUpdateConfig}
      />
    );
    expect(container.querySelector('.audio-device-row')).toBeInTheDocument();
    expect(screen.getByText('系統聲音輸出裝置')).toBeInTheDocument();
  });
});
