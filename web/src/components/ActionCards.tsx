import { Camera, Video, RotateCcw, FolderOpen, XCircle } from 'lucide-react';
import { Card } from './ui';

export interface ActionCardsProps {
  onCaptureScreenshot: () => void;
  onRecordVideo: () => void;
  onToggleReplay: () => void;
  onSelectFile: () => void;
  isReplaying: boolean;
  isRecording?: boolean;
  recordingLabel?: string;
}

export default function ActionCards({
  onCaptureScreenshot,
  onRecordVideo,
  onToggleReplay,
  onSelectFile,
  isReplaying,
  isRecording = false,
  recordingLabel,
}: ActionCardsProps) {
  return (
    <div className="core-actions-grid">
      {/* 1. Capture Screenshot */}
      <Card
        variant={isRecording ? 'default' : 'interactive'}
        onClick={isRecording ? undefined : onCaptureScreenshot}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          gap: '6px',
          opacity: isRecording ? 0.45 : 1,
          cursor: isRecording ? 'not-allowed' : 'pointer',
        }}
        title={isRecording ? '錄影進行中，無法同時截圖' : undefined}
      >
        <Camera size={28} color="var(--color-primary)" />
        <div className="action-card-title">擷取圖片</div>
        <div className="action-card-desc">擷取目前遊戲畫面並自動辨識</div>
      </Card>

      {/* 2. Record Short Video / Cancel Recording */}
      <Card
        variant={isReplaying ? 'default' : 'interactive'}
        onClick={isReplaying ? undefined : onRecordVideo}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          gap: '6px',
          borderColor: isRecording ? 'var(--color-status-danger)' : undefined,
          backgroundColor: isRecording ? 'rgba(239, 68, 68, 0.08)' : undefined,
          opacity: isReplaying ? 0.45 : 1,
          cursor: isReplaying ? 'not-allowed' : 'pointer',
        }}
        title={
          isReplaying
            ? '循環錄影運行中，無法同時進行手動錄影'
            : isRecording
            ? '點擊以取消目前錄影'
            : undefined
        }
      >
        {isRecording ? (
          <XCircle size={28} color="var(--color-status-danger)" className="pulse" />
        ) : (
          <Video size={28} color="var(--color-primary)" />
        )}
        <div
          className="action-card-title"
          style={{ color: isRecording ? 'var(--color-status-danger)' : undefined }}
        >
          {isRecording ? '取消錄影' : '錄製短片'}
        </div>
        <div className="action-card-desc">
          {isRecording ? (recordingLabel || '點擊中斷') : '錄製短片並自動辨識'}
        </div>
      </Card>

      {/* 3. Toggle Replay Buffer */}
      <Card
        variant={isRecording ? 'default' : 'interactive'}
        onClick={isRecording ? undefined : onToggleReplay}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          gap: '6px',
          borderColor: isReplaying ? 'var(--color-primary)' : undefined,
          backgroundColor: isReplaying ? 'rgba(249, 115, 22, 0.08)' : undefined,
          opacity: isRecording ? 0.45 : 1,
          cursor: isRecording ? 'not-allowed' : 'pointer',
        }}
        title={
          isRecording
            ? '手動錄影進行中，無法切換循環錄影'
            : isReplaying
            ? '循環錄影記錄中，點擊可停止'
            : undefined
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
          {isReplaying ? '停止循環錄影' : '循環錄影'}
        </div>
        <div className="action-card-desc">
          {isReplaying ? '記錄中 (點擊停止)' : '啟動背景循環錄影，保留最近影像'}
        </div>
      </Card>

      {/* 4. Select Local File */}
      <Card
        variant={isRecording ? 'default' : 'interactive'}
        onClick={isRecording ? undefined : onSelectFile}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          gap: '6px',
          opacity: isRecording ? 0.45 : 1,
          cursor: isRecording ? 'not-allowed' : 'pointer',
        }}
        title={isRecording ? '錄影進行中，無法選取檔案' : undefined}
      >
        <FolderOpen size={28} color="var(--color-primary)" />
        <div className="action-card-title">選擇檔案</div>
        <div className="action-card-desc">選取本機截圖或錄影進行辨識</div>
      </Card>
    </div>
  );
}
