import { Camera, Video, RotateCcw, FolderOpen } from 'lucide-react';
import { Card, CircularProgress } from './ui';

export interface ActionCardsProps {
  onCaptureScreenshot: () => void;
  onRecordVideo: () => void;
  onToggleReplay: () => void;
  onSelectFile: () => void;
  isReplaying: boolean;
  isRecording?: boolean;
  recordingLabel?: string;
  countdown?: number;
  totalCountdown?: number;
  countdownFraction?: number;
  recordingTime?: number;
  totalRecordingDuration?: number;
  recordingFraction?: number;
  recordingPercent?: number;
  disabled?: boolean;
}

export default function ActionCards({
  onCaptureScreenshot,
  onRecordVideo,
  onToggleReplay,
  onSelectFile,
  isReplaying,
  isRecording = false,
  recordingLabel,
  countdown = 0,
  countdownFraction: propCountdownFraction,
  recordingTime = 0,
  totalRecordingDuration = 8,
  recordingFraction: propRecordingFraction,
  disabled = false,
}: ActionCardsProps) {
  const isCountdownActive = countdown > 0;
  const isRecordingActive = isRecording && !isCountdownActive;

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
    <div className="core-actions-grid">
      {/* 1. Capture Screenshot */}
      <Card
        className="action-card action-card-capture"
        variant="interactive"
        onClick={onCaptureScreenshot}
        disabled={isRecording || disabled}
        aria-label={
          disabled
            ? '截圖，目前無法使用：系統正在重置狀態中'
            : isRecording
              ? '截圖，目前無法使用：錄影進行中'
              : undefined
        }
        style={{
          opacity: isRecording || disabled ? 0.45 : 1,
          cursor: isRecording || disabled ? 'not-allowed' : 'pointer',
        }}
        title={
          disabled
            ? '系統正在重置狀態中，請稍候...'
            : isRecording
              ? '錄影進行中，無法同時截圖'
              : '截取目前遊戲畫面並自動辨識'
        }
      >
        <Camera size={28} color="var(--color-primary)" />
        <div className="action-card-title">截圖</div>
        <div className="action-card-desc">截取目前遊戲畫面並自動辨識</div>
      </Card>

      {/* 2. Record Short Video / Countdown / Cancel Recording */}
      <Card
        className="action-card action-card-record"
        variant="interactive"
        onClick={onRecordVideo}
        disabled={isReplaying || disabled}
        aria-label={
          disabled
            ? '錄影，目前無法使用：系統正在重置狀態中'
            : isReplaying
              ? '錄影，目前無法使用：循環錄影進行中'
              : undefined
        }
        style={{
          borderColor: isCountdownActive
            ? 'var(--color-primary)'
            : isRecordingActive
              ? 'var(--color-danger)'
              : undefined,
          backgroundColor: isCountdownActive
            ? 'rgba(255, 135, 17, 0.08)'
            : isRecordingActive
              ? 'rgba(239, 68, 68, 0.08)'
              : undefined,
          opacity: isReplaying || disabled ? 0.45 : 1,
          cursor: isReplaying || disabled ? 'not-allowed' : 'pointer',
        }}
        title={
          disabled
            ? '系統正在重置狀態中，請稍候...'
            : isReplaying
              ? '循環錄影運行中，無法同時進行手動錄影'
              : isRecording
                ? '點擊以取消目前錄影'
                : '錄影並自動辨識'
        }
      >
        {isCountdownActive ? (
          <CircularProgress
            value={activeCountdownFraction}
            size={36}
            strokeWidth={3.5}
            trackColor="rgba(255, 135, 17, 0.2)"
            progressColor="var(--color-primary)"
            transitionDuration="0.05s linear"
          >
            <span
              style={{
                fontSize: '1.1rem',
                fontWeight: 800,
                color: 'var(--color-primary)',
                fontFamily: 'monospace',
                lineHeight: 1,
              }}
            >
              {countdown}
            </span>
          </CircularProgress>
        ) : isRecordingActive ? (
          <CircularProgress
            value={activeRecordingFraction}
            size={36}
            strokeWidth={3.5}
            trackColor="rgba(239, 68, 68, 0.2)"
            progressColor="var(--color-danger)"
            isCancelIcon={true}
            transitionDuration="0.05s linear"
          />
        ) : (
          <Video size={28} color="var(--color-primary)" />
        )}

        <div
          className="action-card-title"
          style={{
            color: isCountdownActive
              ? 'var(--color-primary)'
              : isRecordingActive
                ? 'var(--color-danger)'
                : undefined,
          }}
        >
          {disabled
            ? '處理中...'
            : isCountdownActive
              ? '倒數準備中'
              : isRecordingActive
                ? '取消錄影'
                : '錄影'}
        </div>

        <div className="action-card-desc">
          {disabled
            ? '重置中，請稍候'
            : isCountdownActive
              ? `倒數 ${countdown} 秒 (點擊取消)`
              : isRecordingActive
                ? recordingLabel ||
                  `錄影中 ${recordingTime}s / ${totalRecordingDuration}s (點擊中斷)`
                : isReplaying
                  ? '循環錄影進行中'
                  : '錄影並自動辨識'}
        </div>
      </Card>

      {/* 3. Toggle Replay Buffer */}
      <Card
        className="action-card action-card-replay"
        variant="interactive"
        onClick={onToggleReplay}
        disabled={isRecording || disabled}
        aria-label={
          disabled
            ? '循環錄影，目前無法使用：系統正在重置狀態中'
            : isRecording
              ? '循環錄影，目前無法使用：手動錄影進行中'
              : undefined
        }
        style={{
          borderColor: isReplaying ? 'var(--color-primary)' : undefined,
          backgroundColor: isReplaying ? 'rgba(249, 115, 22, 0.08)' : undefined,
          opacity: isRecording || disabled ? 0.45 : 1,
          cursor: isRecording || disabled ? 'not-allowed' : 'pointer',
        }}
        title={
          disabled
            ? '系統正在重置狀態中，請稍候...'
            : isRecording
              ? '手動錄影進行中，無法切換循環錄影'
              : isReplaying
                ? '循環錄影記錄中，點擊可停止'
                : '啟動背景循環錄影，保留最近影像'
        }
      >
        <RotateCcw
          size={28}
          color="var(--color-primary)"
          className={isReplaying ? 'spin-reverse' : ''}
        />
        <div
          className="action-card-title"
          style={{ color: isReplaying ? 'var(--color-primary)' : undefined }}
        >
          {disabled ? '處理中...' : isReplaying ? '停止循環錄影' : '循環錄影'}
        </div>
        <div className="action-card-desc">
          {disabled
            ? '重置中，請稍候'
            : isReplaying
              ? '記錄中 (點擊停止)'
              : isRecording
                ? '手動錄影進行中'
                : '啟動背景循環錄影，保留最近影像'}
        </div>
      </Card>

      {/* 4. Select Local File */}
      <Card
        className="action-card action-card-file"
        variant="interactive"
        onClick={onSelectFile}
        disabled={isRecording || disabled}
        aria-label={
          disabled
            ? '選擇檔案，目前無法使用：系統正在重置狀態中'
            : isRecording
              ? '選擇檔案，目前無法使用：錄影進行中'
              : undefined
        }
        style={{
          opacity: isRecording || disabled ? 0.45 : 1,
          cursor: isRecording || disabled ? 'not-allowed' : 'pointer',
        }}
        title={
          disabled
            ? '系統正在重置狀態中，請稍候...'
            : isRecording
              ? '錄影進行中，無法選取檔案'
              : '選取本機截圖或影片進行辨識'
        }
      >
        <FolderOpen size={28} color="var(--color-primary)" />
        <div className="action-card-title">選擇檔案</div>
        <div className="action-card-desc">選取本機截圖或影片進行辨識</div>
      </Card>
    </div>
  );
}
