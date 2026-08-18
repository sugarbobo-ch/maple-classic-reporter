import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import StatusBar from '../src/components/StatusBar';
import ActionCards from '../src/components/ActionCards';

describe('StatusBar component', () => {
  it('renders idle state with synced dynamic window size and audio device', () => {
    render(
      <StatusBar
        statusState="idle"
        targetWindowTitle="MapleStory"
        windowSize="2560 × 1440"
        audioDevice="立體聲混音"
        quality="1440p 60 FPS"
      />
    );

    expect(screen.getByText('待命狀態 (就緒)')).toBeInTheDocument();
    expect(screen.getByText('立體聲混音')).toBeInTheDocument();
    expect(screen.getByText('MapleStory')).toBeInTheDocument();
    expect(screen.getByText('2560 × 1440')).toBeInTheDocument();
    expect(screen.getByText('1440p 60 FPS')).toBeInTheDocument();
    expect(screen.queryByText('REC')).not.toBeInTheDocument();
  });

  it('renders recording state with REC badge and cancel button', () => {
    const onCancel = vi.fn();
    render(
      <StatusBar
        statusState="recording"
        recordingTime={5}
        totalRecordingDuration={10}
        onCancelRecording={onCancel}
      />
    );

    expect(screen.getByText('REC')).toBeInTheDocument();
    expect(screen.getByText(/錄影中 00:05 \/ 00:10/)).toBeInTheDocument();
    const cancelBtn = screen.getByRole('button', { name: /取消錄影/i });
    expect(cancelBtn).toBeInTheDocument();
    fireEvent.click(cancelBtn);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('renders replaying state with REC badge and stop/save replay buttons', () => {
    const onStop = vi.fn();
    const onSave = vi.fn();
    render(
      <StatusBar
        statusState="replaying"
        replayTime={18}
        maxReplayBuffer={30}
        onStopReplay={onStop}
        onSaveReplay={onSave}
      />
    );

    expect(screen.getByText('REC')).toBeInTheDocument();
    expect(screen.getByText(/循環錄影中 \(18s \/ 30s 已緩衝\)/)).toBeInTheDocument();
    const stopBtn = screen.getByRole('button', { name: /停止循環錄影/i });
    const saveBtn = screen.getByRole('button', { name: /儲存片段/i });
    expect(stopBtn).toBeInTheDocument();
    expect(saveBtn).toBeInTheDocument();
    fireEvent.click(saveBtn);
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it('renders countdown state in StatusBar with countdown text and cancel action', () => {
    const onCancel = vi.fn();
    render(
      <StatusBar
        countdown={3}
        totalCountdown={3}
        onCancelRecording={onCancel}
      />
    );

    expect(screen.getByText('REC')).toBeInTheDocument();
    expect(screen.getByText('錄影準備中：倒數 3 秒')).toBeInTheDocument();
    const cancelBtn = screen.getByRole('button', { name: /取消錄影/i });
    expect(cancelBtn).toBeInTheDocument();
  });
});

describe('ActionCards component', () => {
  it('renders normal idle state for record video card', () => {
    const onRecord = vi.fn();
    render(
      <ActionCards
        onCaptureScreenshot={vi.fn()}
        onRecordVideo={onRecord}
        onToggleReplay={vi.fn()}
        onSelectFile={vi.fn()}
        isReplaying={false}
        isRecording={false}
      />
    );

    expect(screen.getByText('錄製短片')).toBeInTheDocument();
    expect(screen.getByText('錄製短片並自動辨識')).toBeInTheDocument();
  });

  it('renders countdown state with decreasing circular progress value and remaining seconds', () => {
    render(
      <ActionCards
        onCaptureScreenshot={vi.fn()}
        onRecordVideo={vi.fn()}
        onToggleReplay={vi.fn()}
        onSelectFile={vi.fn()}
        isReplaying={false}
        isRecording={true}
        countdown={2}
        totalCountdown={3}
      />
    );

    expect(screen.getByText('倒數準備中')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('倒數 2 秒 (點擊取消)')).toBeInTheDocument();
  });

  it('renders active recording state with filling circular progress and cancel title', () => {
    render(
      <ActionCards
        onCaptureScreenshot={vi.fn()}
        onRecordVideo={vi.fn()}
        onToggleReplay={vi.fn()}
        onSelectFile={vi.fn()}
        isReplaying={false}
        isRecording={true}
        countdown={0}
        recordingTime={4}
        totalRecordingDuration={8}
        recordingPercent={50}
      />
    );

    expect(screen.getByText('取消錄影')).toBeInTheDocument();
    expect(screen.getByText('錄製中 4s / 8s (點擊中斷)')).toBeInTheDocument();
  });
});
