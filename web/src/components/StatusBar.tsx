import { RotateCcw, Shield, X, Save, Square } from 'lucide-react';
import { Button } from './ui';
import { StatusState } from '../types';

export interface StatusBarProps {
  statusState?: StatusState;
  recordingTime?: number;
  totalRecordingDuration?: number;
  recordingFraction?: number;
  recordingPercent?: number;
  countdown?: number;
  totalCountdown?: number;
  countdownFraction?: number;
  replayTime?: number;
  maxReplayBuffer?: number;
  targetWindowTitle?: string;
  windowSize?: string;
  audioDevice?: string;
  quality?: string;
  disabled?: boolean;
  onCancelRecording?: () => void;
  onStopReplay?: () => void;
  onSaveReplay?: () => void;
}

export default function StatusBar({
  statusState = 'idle',
  recordingTime = 0,
  totalRecordingDuration = 8,
  recordingFraction: propRecordingFraction,
  recordingPercent: _recordingPercent,
  countdown = 0,
  totalCountdown: _totalCountdown = 3,
  countdownFraction: propCountdownFraction,
  replayTime = 0,
  maxReplayBuffer = 30,
  targetWindowTitle = '新楓之谷：經典版',
  windowSize = '1920 × 1080',
  audioDevice = '系統預設',
  quality = '1080p 30 FPS',
  disabled = false,
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

  const isCountdownActive = countdown > 0;
  const isRecordingActive = statusState === 'recording' && !isCountdownActive;
  const isReplayingActive = statusState === 'replaying';
  const showRecBadge = isCountdownActive || isRecordingActive || isReplayingActive;

  // Exact continuous countdown fraction: 1.0 -> 0.0
  const activeCountdownFraction = isCountdownActive
    ? propCountdownFraction !== undefined
      ? propCountdownFraction
      : 1.0
    : 0;

  // Exact continuous recording fraction: 0.0 -> 1.0
  const activeRecordingFraction = isRecordingActive
    ? propRecordingFraction !== undefined
      ? propRecordingFraction
      : recordingTime / Math.max(1, totalRecordingDuration)
    : 0;

  return (
    <div className="status-bar">
      {/* Top Active Progress Bar Strip (聲音來源上方) */}
      {(isCountdownActive || isRecordingActive) && (
        <div className={`status-top-progress-track ${isCountdownActive ? 'countdown' : 'recording'}`}>
          <div
            className={`status-top-progress-bar ${isCountdownActive ? 'countdown' : 'recording'}`}
            style={{
              width: `${(isCountdownActive ? activeCountdownFraction : activeRecordingFraction) * 100}%`,
            }}
          />
        </div>
      )}

      {/* Top Details Grid */}
      <div className="status-details-grid">
        <div className="status-detail-item">
          <span className="status-detail-label">聲音來源</span>
          <span className="status-detail-value" title={audioDevice}>
            {audioDevice}
          </span>
        </div>
        <div className="status-detail-item">
          <span className="status-detail-label">目標視窗</span>
          <span className="status-detail-value" title={targetWindowTitle}>
            {targetWindowTitle}
          </span>
        </div>
        <div className="status-detail-item">
          <span className="status-detail-label">視窗大小</span>
          <span className="status-detail-value">{windowSize}</span>
        </div>
        <div className="status-detail-item">
          <span className="status-detail-label">錄影品質</span>
          <span className="status-detail-value">{quality}</span>
        </div>
      </div>

      {/* Bottom Row: Status Indicator on Left, Action Buttons on Right */}
      <div className="status-bar-bottom">
        <div className="status-pills">
          {isCountdownActive ? (
            <div className="status-pill countdown">
              <span className="status-rec-dot countdown" />
              <span>錄影準備中：倒數 {countdown} 秒</span>
            </div>
          ) : isRecordingActive ? (
            <div className="status-pill recording">
              <span className="status-rec-dot" />
              <span>
                錄影中 {formatSec(recordingTime)} / {formatSec(totalRecordingDuration)}
              </span>
            </div>
          ) : isReplayingActive ? (
            <div className="status-pill replay">
              <RotateCcw
                size={16}
                color="var(--color-primary)"
                className="spin-reverse"
                style={{ flexShrink: 0 }}
              />
              <span>
                循環錄影中 ({replayTime}s / {maxReplayBuffer}s 已緩衝)
              </span>
            </div>
          ) : (
            <div className="status-pill idle">
              <Shield size={16} color="var(--color-primary)" style={{ flexShrink: 0 }} />
              <span>待命狀態 (就緒)</span>
            </div>
          )}
        </div>

        {/* Right side Action Buttons with REC Indicator (採用中等大小按鈕) */}
        <div className="status-actions-group">
          {showRecBadge && (
            <div className="status-rec-badge" title="錄影狀態指示">
              <span className="status-rec-dot" />
              <span>REC</span>
            </div>
          )}

          {isReplayingActive ? (
            <>
              <Button
                variant="outline"
                size="md"
                icon={Square}
                disabled={disabled}
                onClick={onStopReplay || onCancelRecording}
                title="停止背景循環錄影"
              >
                停止循環錄影
              </Button>

              <Button
                variant="primary"
                size="md"
                icon={Save}
                disabled={disabled}
                onClick={onSaveReplay}
                title="立即擷取並儲存過去片段進入檢舉流程"
              >
                儲存片段
              </Button>
            </>
          ) : (isRecordingActive || isCountdownActive) ? (
            <Button
              variant="danger"
              size="md"
              icon={X}
              disabled={disabled}
              onClick={onCancelRecording}
              title="中斷並捨棄目前錄製"
            >
              取消錄影
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
