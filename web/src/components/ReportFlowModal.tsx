import React, { useState, useEffect, useRef } from 'react';
import {
  FolderOpen,
  Clipboard,
  Check,
  ArrowRight,
  ShieldCheck,
  Film,
  Image as ImageIcon,
  FileCheck,
  AlertCircle,
  ExternalLink,
  Zap,
  Scissors,
  RotateCcw,
  Clock,
} from 'lucide-react';
import { Dialog, Button, Input, Textarea, RadioGroup, Badge, Switch } from './ui';
import { useClipboard } from '../hooks';
import { AppConfig, HistoryRecord, OcrResultData, SubmissionStatusData } from '../types';

export interface ReportFlowModalProps {
  stage?: 'progress' | 'form';
  progressPercent?: number;
  progressStatus?: string;
  isSubmitting?: boolean;
  submissionStatus?: SubmissionStatusData | null;
  ocrResults?: OcrResultData;
  config?: AppConfig;
  history?: HistoryRecord[];
  onClose: () => void;
  onSkipOcr?: () => void;
  onSubmitReport: (formData: Record<string, unknown>) => Promise<void> | void;
  onOpenFilePath?: (path: string) => void;
  onOpenFileLocation?: (path: string) => void;
  onUpdateWhitelist: (newWhitelist: string[]) => void;
}

export default function ReportFlowModal({
  stage = 'progress',
  progressPercent = 37,
  progressStatus = '',
  isSubmitting = false,
  submissionStatus = null,
  ocrResults = {
    suspect_ids: [],
    map_name: '',
    media_path: '',
    media_type: 'video',
  },
  config = {
    default_server: '雪吉拉',
    default_map: '維多利亞島',
    default_note: '自動打怪/外掛行為',
    selected_window_title: '新楓之谷：經典版 (1920x1080)',
    record_duration_sec: 8,
    record_fps: 30,
    replay_buffer_sec: 30,
    upload_destination: 'gdrive',
    gdrive_folder_name: 'MapleClassic_Reports',
    discord_webhook_url: '',
    whitelist: ['player01', 'player02'],
    auto_delete_after_upload: false,
    record_audio: true,
    ocr_autofill_id: true,
    form_submit_headless: true,
    audio_output_device_id: '',
  },
  history = [],
  onClose,
  onSkipOcr,
  onSubmitReport,
  onOpenFilePath,
  onOpenFileLocation,
  onUpdateWhitelist,
}: ReportFlowModalProps) {
  // Form State
  const [suspectId, setSuspectId] = useState('');
  const [server, setServer] = useState(config.default_server || '雪吉拉');
  const [mapName, setMapName] = useState(ocrResults.map_name || '');
  const [note, setNote] = useState(config.default_note || '自動打怪/外掛行為');
  const [formSubmitHeadless, setFormSubmitHeadless] = useState(
    config.form_submit_headless !== false
  );

  // Whitelist Mode State (Step 2)
  const [whitelistMode, setWhitelistMode] = useState(false);
  const [selectedForWhitelist, setSelectedForWhitelist] = useState<string[]>([]);

  // Media State & Stream Player
  const [currentMediaPath, setCurrentMediaPath] = useState<string>(ocrResults.media_path || '');
  const [mediaStreamUrl, setMediaStreamUrl] = useState<string>('');
  const [previewUrl, setPreviewUrl] = useState<string>('');
  const [originalBackupPath, setOriginalBackupPath] = useState<string | null>(null);

  // Video playback & Trimming state
  const isVideo = ocrResults.media_type === 'video' || /\.(mp4|mkv|avi|mov)$/i.test(currentMediaPath);
  const [isTrimOpen, setIsTrimOpen] = useState(false);
  const [videoDuration, setVideoDuration] = useState(0);
  const [currentPlaybackTime, setCurrentPlaybackTime] = useState(0);
  const [cutStart, setCutStart] = useState(0);
  const [cutEnd, setCutEnd] = useState(0);
  const [isTrimming, setIsTrimming] = useState(false);
  const [trimFeedback, setTrimFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);

  // Clipboard hook
  const { read: readClipboard } = useClipboard();

  const existingWhitelist = Array.isArray(config.whitelist) ? config.whitelist : [];
  const mapOcrEnabled = config.ocr_autofill_map !== false;
  const legacyMapName = ocrResults.map_name.trim();
  const ocrMapName = mapOcrEnabled
    ? (
        ocrResults.ocr_map_name ||
        (ocrResults.map_name_source === 'ocr' ? ocrResults.map_name : '') ||
        // Keep older bridge payloads usable while the new source metadata rolls out.
        (ocrResults.map_name_source === undefined &&
        legacyMapName !== String(config.default_map || '').trim()
          ? legacyMapName
          : '')
      ).trim()
    : '';
  const historicalMaps = Array.from(
    new Set(
      history
        .map((record) => String(record.map_name || record.map || '').trim())
        .filter(Boolean)
    )
  );

  const formatTime = (seconds: number) => {
    if (isNaN(seconds) || seconds < 0) return '00:00.0';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 10);
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${ms}`;
  };

  useEffect(() => {
    if (ocrResults) {
      if (ocrResults.map_name) {
        setMapName(ocrResults.map_name);
      }
      const activePath = ocrResults.media_path;
      if (activePath) {
        setCurrentMediaPath(activePath);

        // Fetch streaming URL for video
        if (window.pywebview && window.pywebview.api && window.pywebview.api.get_media_stream_url) {
          window.pywebview.api.get_media_stream_url(activePath).then((streamUrl) => {
            if (streamUrl) setMediaStreamUrl(streamUrl);
          }).catch((e) => {
            console.debug('Failed to get media stream url:', e);
          });
        }

        // Fetch fallback thumbnail
        if (window.pywebview && window.pywebview.api && window.pywebview.api.get_media_preview) {
          window.pywebview.api.get_media_preview(activePath).then((dataUrl) => {
            if (dataUrl) setPreviewUrl(dataUrl);
          }).catch((e) => {
            console.debug('Failed to get media preview:', e);
          });
        }
      }
    }
  }, [ocrResults]);

  // Video metadata & time update
  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      const dur = videoRef.current.duration;
      if (dur && !isNaN(dur)) {
        setVideoDuration(dur);
        if (cutEnd > dur) {
          setCutEnd(dur);
        }
      }
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentPlaybackTime(videoRef.current.currentTime);
    }
  };

  // Timeline click / drag seek handler
  const handleTimelineSeek = (clientX: number, target: HTMLDivElement) => {
    if (!videoRef.current || videoDuration <= 0) return;
    const rect = target.getBoundingClientRect();
    const clickX = Math.max(0, Math.min(rect.width, clientX - rect.left));
    const targetTime = Number(((clickX / rect.width) * videoDuration).toFixed(2));
    videoRef.current.currentTime = targetTime;
    setCurrentPlaybackTime(targetTime);
  };

  const handleTimelineMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.currentTarget;
    handleTimelineSeek(e.clientX, target);

    const onMouseMove = (moveEvent: MouseEvent) => {
      handleTimelineSeek(moveEvent.clientX, target);
    };
    const onMouseUp = () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  };

  // Set cut start / end from current playback time
  const handleSetCutStart = () => {
    const val = Number(currentPlaybackTime.toFixed(1));
    setCutStart(val);
    if (cutEnd <= val) {
      setCutEnd(Math.min(videoDuration, Number((val + 1.0).toFixed(1))));
    }
  };

  const handleSetCutEnd = () => {
    const val = Number(currentPlaybackTime.toFixed(1));
    setCutEnd(val);
    if (cutStart >= val) {
      setCutStart(Math.max(0, Number((val - 1.0).toFixed(1))));
    }
  };

  const handleClearCut = () => {
    setCutStart(0);
    setCutEnd(0);
    setTrimFeedback(null);
  };

  // Execute segment cut
  const handleExecuteCut = async () => {
    if (cutEnd <= cutStart) {
      setTrimFeedback({ type: 'error', message: '刪除終點必須大於起點！' });
      return;
    }
    setIsTrimming(true);
    setTrimFeedback(null);
    try {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.trim_video_segment) {
        const res = await window.pywebview.api.trim_video_segment(
          currentMediaPath,
          cutStart,
          cutEnd,
          originalBackupPath || undefined
        );
        if (res.success && res.new_path) {
          setCurrentMediaPath(res.new_path);
          if (res.stream_url) {
            setMediaStreamUrl(`${res.stream_url}&_t=${Date.now()}`);
          }
          if (res.original_backup_path) {
            setOriginalBackupPath(res.original_backup_path);
          }
          if (res.duration) {
            setVideoDuration(res.duration);
            setCutStart(0);
            setCutEnd(0);
          }
          setTrimFeedback({
            type: 'success',
            message: `剪輯成功！已刪除該區段，剩餘長度：${formatTime(res.duration || 0)}`,
          });
        } else {
          setTrimFeedback({ type: 'error', message: res.error || '剪輯處理失敗' });
        }
      } else {
        // Mock fallback
        setTimeout(() => {
          setOriginalBackupPath(currentMediaPath);
          setCutStart(0);
          setCutEnd(0);
          setTrimFeedback({ type: 'success', message: '已刪除選定區段 (Mock 模擬)' });
          setIsTrimming(false);
        }, 600);
      }
    } catch (e: any) {
      setTrimFeedback({ type: 'error', message: e?.message || '剪輯處理發生異常' });
    } finally {
      setIsTrimming(false);
    }
  };

  // Restore original video
  const handleRestoreOriginal = async () => {
    if (!originalBackupPath) return;
    setIsTrimming(true);
    setTrimFeedback(null);
    try {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.restore_original_video) {
        const res = await window.pywebview.api.restore_original_video(
          currentMediaPath,
          originalBackupPath
        );
        if (res.success && res.restored_path) {
          setCurrentMediaPath(res.restored_path);
          if (res.stream_url) {
            setMediaStreamUrl(`${res.stream_url}&_t=${Date.now()}`);
          }
          setOriginalBackupPath(null);
          if (res.duration) {
            setVideoDuration(res.duration);
            setCutStart(0);
            setCutEnd(0);
          }
          setTrimFeedback({ type: 'success', message: '已還原為原始錄影影片！' });
        } else {
          setTrimFeedback({ type: 'error', message: res.error || '還原失敗' });
        }
      }
    } catch (e: any) {
      setTrimFeedback({ type: 'error', message: e?.message || '還原處理異常' });
    } finally {
      setIsTrimming(false);
    }
  };

  // Paste from clipboard using hook
  const handlePasteClipboard = async () => {
    const text = await readClipboard();
    if (text) setSuspectId(text.trim());
  };

  // Toggle whitelist chip selection
  const handleToggleWhitelistChip = (id: string) => {
    if (existingWhitelist.includes(id)) return;
    if (selectedForWhitelist.includes(id)) {
      setSelectedForWhitelist(selectedForWhitelist.filter((item) => item !== id));
    } else {
      setSelectedForWhitelist([...selectedForWhitelist, id]);
    }
  };

  const handleFinishWhitelistMode = () => {
    if (selectedForWhitelist.length > 0) {
      const updated = [...existingWhitelist, ...selectedForWhitelist];
      onUpdateWhitelist(updated);
      if (selectedForWhitelist.includes(suspectId)) {
        setSuspectId('');
      }
    }
    setWhitelistMode(false);
    setSelectedForWhitelist([]);
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e && e.preventDefault) e.preventDefault();
    if (isSubmitting || !suspectId.trim() || !mapName.trim()) return;

    await onSubmitReport({
      suspect_id: suspectId.trim(),
      server,
      map_name: mapName.trim(),
      note: note.trim(),
      media_path: currentMediaPath || ocrResults.media_path,
      file_path: currentMediaPath || ocrResults.media_path,
      form_submit_headless: formSubmitHeadless,
      dev_mode: Boolean(config.dev_mode),
    });
  };

  return (
    <Dialog
      isOpen={true}
      onClose={isSubmitting ? undefined : onClose}
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>{stage === 'progress' ? '事證辨識進度' : '檢舉事證回報表單'}</span>
          {config.dev_mode && stage === 'form' && (
            <Badge variant="event" size="sm">
              DEV 模擬送出
            </Badge>
          )}
        </div>
      }
      titleIcon={FileCheck}
      maxWidth={stage === 'progress' ? '500px' : '780px'}
      footer={
        stage === 'progress' ? (
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              width: '100%',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <Button variant="outline" size="md" onClick={onClose}>
              取消
            </Button>
            {onSkipOcr && (
              <Button
                variant="primary"
                size="md"
                onClick={onSkipOcr}
                icon={ArrowRight}
                iconPosition="right"
                data-testid="skip-ocr-button"
              >
                略過辨識，直接填表
              </Button>
            )}
          </div>
        ) : (
          <>
            <Button variant="outline" size="md" onClick={onClose} disabled={isSubmitting}>
              取消
            </Button>
            <Button
              variant="primary"
              size="md"
              icon={ArrowRight}
              iconPosition="right"
              onClick={handleSubmit}
              disabled={!suspectId.trim() || !mapName.trim() || isSubmitting}
              loading={isSubmitting}
              aria-busy={isSubmitting}
              data-testid="report-submit"
            >
              {isSubmitting
                ? '送出中…'
                : config.dev_mode
                  ? '模擬送出檢舉 (不實際送出)'
                  : '送出檢舉事證'}
            </Button>
          </>
        )
      }
    >
      {stage === 'progress' ? (
        /* Stage 1: Recognition Progress State */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--color-text-heading)' }}>
            正在分析事證...
          </div>

          <div
            style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.875rem' }}
          >
            {/* 1. Read recording */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: progressPercent >= 20 ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }}>
                讀取錄影片段
              </span>
              {progressPercent >= 20 ? (
                <Badge variant="success" size="sm">完成</Badge>
              ) : (
                <Badge variant="primary" size="sm" dot>處理中...</Badge>
              )}
            </div>

            {/* 2. Keyframes extraction */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: progressPercent >= 40 ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }}>
                擷取關鍵畫面
              </span>
              {progressPercent >= 40 ? (
                <Badge variant="success" size="sm">完成</Badge>
              ) : progressPercent >= 20 ? (
                <Badge variant="primary" size="sm" dot>處理中...</Badge>
              ) : (
                <Badge variant="default" size="sm">等待中</Badge>
              )}
            </div>

            {/* 3. Map recognition */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: progressPercent >= 60 ? 'var(--color-text-primary)' : 'var(--color-text-secondary)', fontWeight: progressPercent >= 40 && progressPercent < 60 ? 700 : 400 }}>
                辨識地圖名稱
              </span>
              {progressPercent >= 60 ? (
                <Badge variant="success" size="sm">完成</Badge>
              ) : progressPercent >= 40 ? (
                <Badge variant="primary" size="sm" dot>
                  {progressStatus.includes('地圖') && progressStatus.match(/\(([^)]+)\)/)
                    ? `處理中 ${progressStatus.match(/\(([^)]+)\)/)?.[0] || ''}`
                    : '處理中...'}
                </Badge>
              ) : (
                <Badge variant="default" size="sm">等待中</Badge>
              )}
            </div>

            {/* 4. Character ID recognition */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: progressPercent >= 85 ? 'var(--color-text-primary)' : 'var(--color-text-secondary)', fontWeight: progressPercent >= 60 && progressPercent < 85 ? 700 : 400 }}>
                辨識角色 ID
              </span>
              {progressPercent >= 85 ? (
                <Badge variant="success" size="sm">完成</Badge>
              ) : progressPercent >= 60 ? (
                <Badge variant="primary" size="sm" dot>
                  {progressStatus.includes('ID') && progressStatus.match(/\(([^)]+)\)/)
                    ? `處理中 ${progressStatus.match(/\(([^)]+)\)/)?.[0] || ''}`
                    : '處理中...'}
                </Badge>
              ) : (
                <Badge variant="default" size="sm">等待中</Badge>
              )}
            </div>

            {/* 5. Organize candidates */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                color: progressPercent >= 90 ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
              }}
            >
              <span>整理歷史與候選資料</span>
              {progressPercent >= 100 ? (
                <Badge variant="success" size="sm">完成</Badge>
              ) : progressPercent >= 85 ? (
                <Badge variant="primary" size="sm" dot>處理中...</Badge>
              ) : (
                <Badge variant="default" size="sm">等待中</Badge>
              )}
            </div>
          </div>

          <div style={{ marginTop: '12px' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: '0.8rem',
                color: 'var(--color-text-secondary)',
                marginBottom: '6px',
              }}
            >
              <span>
                {progressStatus || (progressPercent >= 100
                  ? '分析完成，載入回報表單中...'
                  : `正在分析關鍵畫面... (${progressPercent}%)`)}
              </span>
              <span style={{ fontSize: '0.75rem', opacity: 0.8 }}>可隨時略過</span>
            </div>
            <div
              style={{
                height: '8px',
                backgroundColor: 'var(--color-surface)',
                borderRadius: '4px',
                overflow: 'hidden',
                border: '1px solid var(--color-border)',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${progressPercent}%`,
                  backgroundColor: 'var(--color-primary)',
                  transition: 'width 0.3s ease',
                }}
              />
            </div>
          </div>
        </div>
      ) : (
        /* Stage 2: Report Confirmation Form State (Steps 1 to 5) */
        <form
          onSubmit={handleSubmit}
          style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}
        >
          {submissionStatus && (
            <div
              className={`submission-status-message ${submissionStatus.status || 'progress'}`}
              role={submissionStatus.status === 'error' ? 'alert' : 'status'}
              aria-live={submissionStatus.status === 'error' ? 'assertive' : 'polite'}
              aria-atomic="true"
            >
              {submissionStatus.message}
            </div>
          )}
          {/* Step 1: Media Confirmation with Direct 16:9 Preview & Right Actions */}
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
                      onLoadedMetadata={handleLoadedMetadata}
                      onTimeUpdate={handleTimeUpdate}
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
                          onClick={handleSetCutStart}
                          aria-label="設定影片剪輯起點"
                          title="將當前播放時間設為刪除起點"
                          style={{ fontSize: '0.75rem', padding: '3px 8px' }}
                        >
                          設為起點 [{cutStart > 0 || cutEnd > cutStart ? ` ${formatTime(cutStart)}` : ''}
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={handleSetCutEnd}
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
                            onClick={handleClearCut}
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
                        onMouseDown={handleTimelineMouseDown}
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
                        onClick={handleExecuteCut}
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
                    onClick={() => {
                      setIsTrimOpen(!isTrimOpen);
                      setTrimFeedback(null);
                    }}
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
                    onClick={handleRestoreOriginal}
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

          {/* Step 2: Suspect ID & Whitelist Selection */}
          <div className="step-block">
            <div className="step-title-row">
              <span className="step-number">2</span>
              <span>外掛玩家角色 ID</span>
            </div>

            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <Input
                placeholder="請輸入或點選下方候選角色 ID"
                value={suspectId}
                onChange={(e) => setSuspectId(e.target.value)}
                required
                data-testid="report-suspect-id"
              />
              <Button variant="secondary" size="md" icon={Clipboard} onClick={handlePasteClipboard}>
                貼上
              </Button>
            </div>

            {/* Suggestions Chips Area */}
            <div style={{ marginTop: '2px' }}>
              <div
                style={{
                  fontSize: '0.78rem',
                  color: whitelistMode
                    ? 'var(--color-status-success)'
                    : 'var(--color-text-secondary)',
                  marginBottom: '6px',
                  fontWeight: whitelistMode ? 700 : 400,
                }}
              >
                {whitelistMode
                  ? '選擇白名單：點選要排除的名稱；加入後，往後辨識將自動略過。'
                  : 'OCR 辨識結果：點選名稱即可帶入角色 ID（尚未自動選取）。'}
              </div>

              <div className={`chip-group ${whitelistMode ? 'whitelist-mode' : ''}`}>
                {ocrResults.suspect_ids && ocrResults.suspect_ids.length > 0 ? (
                  ocrResults.suspect_ids.map((id, idx) => {
                    const isAlreadyWhitelisted = existingWhitelist.includes(id);
                    const isSelectedForWhitelist = selectedForWhitelist.includes(id);
                    const isCurrentInputMatch = suspectId === id;

                    if (whitelistMode) {
                      return (
                        <div
                          key={idx}
                          className={`chip whitelist-chip ${isAlreadyWhitelisted ? 'disabled' : ''} ${
                            isSelectedForWhitelist ? 'success' : ''
                          }`}
                          onClick={() => handleToggleWhitelistChip(id)}
                        >
                          {isSelectedForWhitelist && <Check size={12} />}
                          <span>{id}</span>
                          {isAlreadyWhitelisted && (
                            <span style={{ fontSize: '0.7rem', opacity: 0.8 }}>(已加入)</span>
                          )}
                        </div>
                      );
                    }

                    return (
                      <div
                        key={idx}
                        className={`chip ${isCurrentInputMatch ? 'active' : ''}`}
                        onClick={() => setSuspectId(id)}
                      >
                        {id}
                      </div>
                    );
                  })
                ) : (
                  <span style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)' }}>
                    (未辨識到角色 ID，請手動輸入)
                  </span>
                )}
              </div>
            </div>

            {/* Whitelist Action Toolbar at Bottom of Section */}
            <div
              style={{
                marginTop: '4px',
                paddingTop: '8px',
                borderTop: '1px dashed var(--color-border)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              {!whitelistMode ? (
                <Button
                  variant="outline"
                  size="sm"
                  icon={ShieldCheck}
                  onClick={() => setWhitelistMode(true)}
                  style={{ fontSize: '0.8rem' }}
                >
                  從辨識結果管理白名單
                </Button>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                  <span style={{ fontSize: '0.78rem', color: 'var(--color-status-success)', fontWeight: 600 }}>
                    正在選取白名單名單
                  </span>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <Button variant="outline" size="sm" onClick={() => setWhitelistMode(false)}>
                      取消
                    </Button>
                    <Button
                      variant="success"
                      size="sm"
                      icon={Check}
                      onClick={handleFinishWhitelistMode}
                    >
                      完成設定
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Step 3: Game Server */}
          <div className="step-block">
            <div className="step-title-row">
              <span className="step-number">3</span>
              <span>外掛角色所在伺服器</span>
            </div>
            <div style={{ padding: '4px 0' }}>
              <RadioGroup
                name="server"
                value={server}
                onChange={(val) => setServer(val)}
                options={[
                  { value: '雪吉拉', label: '雪吉拉' },
                  { value: '菇菇寶貝', label: '菇菇寶貝' },
                ]}
              />
            </div>
          </div>

          {/* Step 4: Map Name */}
          <div className="step-block">
            <div className="step-title-row">
              <span className="step-number">4</span>
              <span>外掛角色所在地圖</span>
            </div>
            <Input
              placeholder="例如：地鐵一號線｜地區01"
              value={mapName}
              onChange={(e) => setMapName(e.target.value)}
              required
              data-testid="report-map-name"
            />

            {(!mapOcrEnabled || ocrMapName || historicalMaps.length > 0) && (
              <>
                {!mapOcrEnabled && (
                  <div
                    role="status"
                    data-testid="ocr-map-disabled-hint"
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '6px',
                      fontSize: '0.78rem',
                      color: 'var(--color-status-warning)',
                      marginTop: '8px',
                      lineHeight: 1.45,
                    }}
                  >
                    <AlertCircle size={14} style={{ flexShrink: 0, marginTop: '2px' }} />
                    <span>
                      尚未啟用地圖 OCR；地圖名稱不會自動辨識，請手動輸入或從歷史紀錄選擇。
                    </span>
                  </div>
                )}
                {(ocrMapName || historicalMaps.length > 0) && (
                  <>
                    <div
                      style={{
                        fontSize: '0.78rem',
                        color: 'var(--color-text-secondary)',
                        marginTop: '8px',
                      }}
                    >
                      建議地圖：
                    </div>
                    <div
                      className="chip-group"
                      data-testid="map-suggestion-group"
                      aria-label="地圖建議"
                    >
                      {ocrMapName && (
                        <div
                          className={`chip ${mapName === ocrMapName ? 'active' : ''}`}
                          onClick={() => setMapName(ocrMapName)}
                          data-testid="ocr-map-suggestion"
                        >
                          OCR：{ocrMapName}
                        </div>
                      )}
                      {historicalMaps.map((map, idx) => (
                        <div
                          key={`${map}-${idx}`}
                          className={`chip ${mapName === map ? 'active' : ''}`}
                          onClick={() => setMapName(map)}
                          data-testid={`history-map-suggestion-${idx}`}
                        >
                          {map}
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}
          </div>

          {/* Step 5: Notes */}
          <div className="step-block">
            <div className="step-title-row">
              <span className="step-number">5</span>
              <span>違規說明與備註</span>
            </div>
            <Textarea
              placeholder="自動打怪／疑似外掛行為"
              value={note}
              rows={2}
              onChange={(e) => setNote(e.target.value)}
              helperText={
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <AlertCircle size={14} style={{ flexShrink: 0 }} color="var(--color-warning)" />
                  <span>提醒：由於官方檢舉表單限制，送出時換行將自動縮減合併為一行。</span>
                </span>
              }
            />
          </div>

          {/* Submission Mode: Background Headless Switch */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 14px',
              backgroundColor: 'var(--color-surface)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Zap size={18} color="var(--color-primary)" />
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>背景靜默送出檢舉</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
                  {formSubmitHeadless
                    ? '已啟用背景模式：Playwright 將於後台靜默自動填表'
                    : '已關閉背景模式：將開啟可見瀏覽器視窗，展示填表與送出過程'}
                </div>
              </div>
            </div>
            <Switch
              checked={formSubmitHeadless}
              onChange={(val) => setFormSubmitHeadless(val)}
            />
          </div>
        </form>
      )}
    </Dialog>
  );
}
