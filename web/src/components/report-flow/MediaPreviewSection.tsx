import React, { RefObject } from 'react';
import {
  Film,
  Image as ImageIcon,
  ExternalLink,
  FolderOpen,
  Scissors,
  RotateCcw,
  Clock,
} from 'lucide-react';
import { Button, Badge } from '../ui';

export interface MediaPreviewSectionProps {
  currentMediaPath: string;
  mediaStreamUrl: string;
  previewUrl: string;
  originalBackupPath: string | null;
  isVideo: boolean;
  isTrimOpen: boolean;
  videoDuration: number;
  currentPlaybackTime: number;
  cutStart: number;
  cutEnd: number;
  isTrimming: boolean;
  trimFeedback: { type: 'success' | 'error'; message: string } | null;
  videoRef: RefObject<HTMLVideoElement>;
  formatTime: (seconds: number) => string;
  onLoadedMetadata: () => void;
  onTimeUpdate: () => void;
  onTimelineMouseDown: (e: React.MouseEvent<HTMLDivElement>) => void;
  onSetCutStart: () => void;
  onSetCutEnd: () => void;
  onClearCut: () => void;
  onExecuteCut: () => void;
  onRestoreOriginal: () => void;
  onToggleTrimOpen: () => void;
  onOpenFilePath?: (path: string) => void;
  onOpenFileLocation?: (path: string) => void;
}

export default function MediaPreviewSection({
  currentMediaPath,
  mediaStreamUrl,
  previewUrl,
  originalBackupPath,
  isVideo,
  isTrimOpen,
  videoDuration,
  currentPlaybackTime,
  cutStart,
  cutEnd,
  isTrimming,
  trimFeedback,
  videoRef,
  formatTime,
  onLoadedMetadata,
  onTimeUpdate,
  onTimelineMouseDown,
  onSetCutStart,
  onSetCutEnd,
  onClearCut,
  onExecuteCut,
  onRestoreOriginal,
  onToggleTrimOpen,
  onOpenFilePath,
  onOpenFileLocation,
}: MediaPreviewSectionProps) {
  return (
    <div className="step-block">
      <div className="step-title-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="step-number">1</span>
          <span>確認事證媒體預覽</span>
        </div>
        {originalBackupPath && (
          <Badge variant="success" size="sm">
            已剪輯片段
          </Badge>
        )}
      </div>

      <div className="media-preview-container">
        {/* Left Column: 16:9 Media Player & Expandable Trim Panel */}
        <div className="media-player-column">
          <div className="media-player-box">
            {isVideo && mediaStreamUrl ? (
              <video
                ref={videoRef}
                key={mediaStreamUrl || currentMediaPath}
                src={mediaStreamUrl}
                controls
                preload="auto"
                onLoadedMetadata={onLoadedMetadata}
                onTimeUpdate={onTimeUpdate}
                className="media-video-element"
                playsInline
              />
            ) : previewUrl ? (
              <img
                src={previewUrl}
                alt="事證畫面預覽"
                className="media-image-element"
              />
            ) : isVideo ? (
              <div className="media-placeholder">
                <Film size={36} color="var(--color-primary)" />
                <span>{currentMediaPath ? '正在載入影片播放器...' : '正在儲存循環錄影，完成後將自動載入影片...'}</span>
              </div>
            ) : (
              <div className="media-placeholder">
                <ImageIcon size={36} color="var(--color-primary)" />
                <span>正在載入圖片預覽...</span>
              </div>
            )}
          </div>

          {/* Media filename label */}
          <div className="media-filename-row" title={currentMediaPath}>
            <span className="media-filename-text">
              {currentMediaPath ? currentMediaPath.split(/[\\/]/).pop() : '未選取檔案'}
            </span>
            {videoDuration > 0 && (
              <span className="media-duration-text">
                時長: {formatTime(videoDuration)}
              </span>
            )}
          </div>

          {/* Expandable Video Segment Trim Panel */}
          {isVideo && isTrimOpen && (
            <div className="video-trim-panel">
              <div className="trim-header-row">
                <div className="trim-time-indicator">
                  <Clock size={13} />
                  <span>播放時間: {formatTime(currentPlaybackTime)} / {formatTime(videoDuration)}</span>
                </div>
                <div className="trim-marker-buttons">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={onSetCutStart}
                    aria-label="設定影片剪輯起點"
                    title="將當前播放時間設為刪除起點"
                    style={{ fontSize: '0.75rem', padding: '3px 8px' }}
                  >
                    設為起點 [{cutStart > 0 || cutEnd > cutStart ? ` ${formatTime(cutStart)}` : ''}
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={onSetCutEnd}
                    aria-label="設定影片剪輯終點"
                    title="將當前播放時間設為刪除終點"
                    style={{ fontSize: '0.75rem', padding: '3px 8px' }}
                  >
                    設為終點 ]{cutEnd > 0 ? ` ${formatTime(cutEnd)}` : ''}
                  </Button>
                  {(cutStart > 0 || cutEnd > 0) && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={onClearCut}
                      aria-label="清除影片剪輯標記"
                      title="清除選取的剪輯區段"
                      style={{ fontSize: '0.75rem', padding: '3px 8px' }}
                    >
                      清除選取
                    </Button>
                  )}
                </div>
              </div>

              {/* Visual Interactive Timeline Track */}
              <div className="trim-timeline-wrapper">
                <div
                  className="trim-timeline-track"
                  onMouseDown={onTimelineMouseDown}
                  title="點選或拖曳時間軸跳轉播放時間"
                >
                  {/* Cut region highlight */}
                  {videoDuration > 0 && cutEnd > cutStart && (
                    <div
                      className="trim-cut-highlight"
                      style={{
                        left: `${Math.max(0, Math.min(100, (cutStart / videoDuration) * 100))}%`,
                        width: `${Math.max(0, Math.min(100, ((cutEnd - cutStart) / videoDuration) * 100))}%`,
                      }}
                      title={`即將刪除: ${formatTime(cutStart)} ~ ${formatTime(cutEnd)}`}
                    >
                      <span className="trim-cut-label">✂️ 刪除區段</span>
                    </div>
                  )}
                  {/* Playhead position */}
                  {videoDuration > 0 && (
                    <div
                      className="trim-playhead"
                      style={{
                        left: `${Math.max(0, Math.min(100, (currentPlaybackTime / videoDuration) * 100))}%`,
                      }}
                    />
                  )}
                </div>
              </div>

              {/* Trim Action Footer */}
              <div className="trim-action-row">
                <div className="trim-range-summary">
                  {cutEnd > cutStart ? (
                    <>
                      <span>預計移除：</span>
                      <strong style={{ color: 'var(--color-status-danger, #ef5350)' }}>
                        {formatTime(cutStart)} ~ {formatTime(cutEnd)}
                      </strong>
                      <span style={{ opacity: 0.8 }}>
                        （長度 {(Math.max(0, cutEnd - cutStart)).toFixed(1)} 秒）
                      </span>
                    </>
                  ) : (
                    <span style={{ color: 'var(--color-text-secondary)' }}>
                      尚未選定剪輯區段（請在時間軸選取起點與終點）
                    </span>
                  )}
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  icon={Scissors}
                  onClick={onExecuteCut}
                  disabled={isTrimming || cutEnd <= cutStart}
                  aria-label="套用影片剪輯"
                  style={{
                    backgroundColor: cutEnd > cutStart ? '#d32f2f' : undefined,
                    opacity: cutEnd <= cutStart ? 0.6 : 1,
                  }}
                >
                  {isTrimming ? '剪輯處理中...' : '刪除此區段'}
                </Button>
              </div>

              {/* Feedback message */}
              {trimFeedback && (
                <div
                  className={`trim-feedback-msg ${
                    trimFeedback.type === 'success' ? 'success' : 'error'
                  }`}
                >
                  {trimFeedback.message}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Action Buttons */}
        <div className="media-actions-column">
          <Button
            variant="outline"
            size="md"
            icon={ExternalLink}
            onClick={() => onOpenFilePath && onOpenFilePath(currentMediaPath)}
            disabled={!currentMediaPath}
            style={{ width: '100%', justifyContent: 'flex-start' }}
          >
            系統播放器開啟
          </Button>

          <Button
            variant="outline"
            size="md"
            icon={FolderOpen}
            onClick={() => onOpenFileLocation && onOpenFileLocation(currentMediaPath)}
            disabled={!currentMediaPath}
            style={{ width: '100%', justifyContent: 'flex-start' }}
          >
            開啟檔案位置
          </Button>

          {isVideo && (
            <Button
              variant={isTrimOpen ? 'primary' : 'outline'}
              size="md"
              icon={Scissors}
              onClick={onToggleTrimOpen}
              data-testid="video-trim-toggle"
              style={{ width: '100%', justifyContent: 'flex-start' }}
            >
              {isTrimOpen ? '收合剪輯工具' : '區段剪輯'}
            </Button>
          )}

          {originalBackupPath && (
            <Button
              variant="outline"
              size="md"
              icon={RotateCcw}
              onClick={onRestoreOriginal}
              disabled={isTrimming}
              style={{
                width: '100%',
                justifyContent: 'flex-start',
                borderColor: 'var(--color-warning, #f59e0b)',
                color: 'var(--color-warning, #f59e0b)',
              }}
            >
              還原原始影片
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
