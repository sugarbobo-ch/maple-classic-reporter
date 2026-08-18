import { Circle, Clock, RotateCcw, Shield, X, Save, Square } from 'lucide-react';
import { Button } from './ui';
import { StatusState } from '../types';

export interface StatusBarProps {
  statusState?: StatusState;
  recordingTime?: number;
  totalRecordingDuration?: number;
  countdown?: number;
  replayTime?: number;
  maxReplayBuffer?: number;
  targetWindowTitle?: string;
  audioDevice?: string;
  quality?: string;
  onCancelRecording?: () => void;
  onStopReplay?: () => void;
  onSaveReplay?: () => void;
}

export default function StatusBar({
  statusState = 'idle',
  recordingTime = 0,
  totalRecordingDuration = 8,
  countdown = 0,
  replayTime = 0,
  maxReplayBuffer = 30,
  targetWindowTitle = '新楓之谷：經典版',
  audioDevice = 'Realtek Digital Output',
  quality = '1080p · 30 FPS',
  onCancelRecording,
  onStopReplay,
  onSaveReplay,
}: StatusBarProps) {
  const formatSec = (sec: number) => {
    const m = Math.floor(sec / 60)
      .toString()
      .padStart(2, '0');
    const s = Math.floor(sec % 60)
      .toString()
      .padStart(2, '0');
    return `${m}:${s}`;
  };

  return (
    <div className="status-bar">
      {/* Top Status Indicators Row */}
      <div className="status-bar-header">
        <div className="status-pills">
          {countdown > 0 && (
            <div className="status-pill" style={{ color: 'var(--color-primary)', borderColor: 'var(--color-primary)' }}>
              <Clock size={14} className="pulse" />
              <span>錄影準備中：倒數 {countdown} 秒</span>
            </div>
          )}

          {statusState === 'recording' && countdown === 0 && (
            <div className="status-pill recording">
              <Circle size={10} fill="var(--color-status-danger)" color="var(--color-status-danger)" className="pulse" />
              <span>錄影中 {formatSec(recordingTime)} / {formatSec(totalRecordingDuration)}</span>
            </div>
          )}

          {statusState === 'replaying' && (
            <div className="status-pill replay">
              <RotateCcw size={14} className="spin-reverse" />
              <span>循環錄影中 ({replayTime}s / {maxReplayBuffer}s 已緩衝)</span>
            </div>
          )}

          {statusState === 'idle' && countdown === 0 && (
            <div className="status-pill" style={{ color: 'var(--color-text-secondary)' }}>
              <Shield size={14} color="var(--color-primary)" />
              <span>待命狀態 (就緒)</span>
            </div>
          )}

          <div
            style={{
              color: 'var(--color-text-secondary)',
              fontSize: '0.8rem',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: '260px',
            }}
          >
            {targetWindowTitle}
          </div>
        </div>
      </div>

      {/* Permanently Visible Details Grid */}
      <div className="status-bar-expanded">
        <div className="status-details-grid">
          <span style={{ color: 'var(--color-text-secondary)' }}>聲音來源</span>
          <span>{audioDevice}</span>

          <span style={{ color: 'var(--color-text-secondary)' }}>目標視窗</span>
          <span>{targetWindowTitle}</span>

          <span style={{ color: 'var(--color-text-secondary)' }}>視窗大小</span>
          <span>1920 × 1080</span>

          <span style={{ color: 'var(--color-text-secondary)' }}>錄影品質</span>
          <span>{quality}</span>
        </div>
      </div>

      {/* Action Buttons Row */}
      <div className="status-actions">
        {statusState === 'replaying' ? (
          <>
            <Button
              variant="outline"
              size="md"
              icon={Square}
              onClick={onStopReplay || onCancelRecording}
              title="停止背景循環錄影"
            >
              停止循環錄影
            </Button>

            <Button
              variant="primary"
              size="md"
              icon={Save}
              onClick={onSaveReplay}
              title="立即擷取並儲存過去片段進入檢舉流程"
            >
              儲存片段
            </Button>
          </>
        ) : statusState === 'recording' || countdown > 0 ? (
          <Button
            variant="danger"
            size="md"
            icon={X}
            onClick={onCancelRecording}
            title="中斷並捨棄目前錄製"
          >
            取消錄影
          </Button>
        ) : (
          <>
            <Button
              variant="outline"
              size="md"
              icon={RotateCcw}
              onClick={onStopReplay}
              disabled={true}
            >
              無進行中錄影
            </Button>

            <Button
              variant="primary"
              size="md"
              icon={Save}
              onClick={onSaveReplay}
              disabled={true}
            >
              儲存片段
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
