import React, { useState, useEffect, useRef } from 'react';
import { ArrowRight, FileCheck } from 'lucide-react';
import { Dialog, Button, Badge } from './ui';
import { useClipboard } from '../hooks';
import { AppConfig, HistoryRecord, OcrResultData, SubmissionStatusData } from '../types';
import {
  ProgressStage,
  MediaPreviewSection,
  SuspectSelector,
  ReportFormSection,
} from './report-flow';

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
    default_map: '',
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
    audio_capture_mode: 'process',
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
  const existingWhitelist = Array.isArray(config.whitelist) ? config.whitelist : [];

  // Form State - auto-populate suspect ID from OCR candidate if enabled
  const initialSuspectId =
    config.ocr_autofill_id !== false &&
    Array.isArray(ocrResults.suspect_ids) &&
    ocrResults.suspect_ids.length > 0
      ? ocrResults.suspect_ids.find((id) => !existingWhitelist.includes(id)) ||
        ocrResults.suspect_ids[0] ||
        ''
      : '';
  const [suspectId, setSuspectId] = useState(initialSuspectId);
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
  const isVideo =
    ocrResults.media_type === 'video' || /\.(mp4|mkv|avi|mov)$/i.test(currentMediaPath);
  const [isTrimOpen, setIsTrimOpen] = useState(false);
  const [videoDuration, setVideoDuration] = useState(0);
  const [currentPlaybackTime, setCurrentPlaybackTime] = useState(0);
  const [cutStart, setCutStart] = useState(0);
  const [cutEnd, setCutEnd] = useState(0);
  const [isTrimming, setIsTrimming] = useState(false);
  const [trimFeedback, setTrimFeedback] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);

  // Clipboard hook
  const { read: readClipboard } = useClipboard();

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
  const sortedHistory = [...history].sort((a, b) => {
    const tA = String(a.time || a.timestamp || '').trim();
    const tB = String(b.time || b.timestamp || '').trim();
    if (tA && tB) {
      return tB.localeCompare(tA);
    }
    return 0;
  });
  const allHistoricalMaps = Array.from(
    new Set(
      sortedHistory
        .map((record) => String(record.map_name || record.map || '').trim())
        .filter(Boolean)
    )
  );
  const historicalMaps = (
    ocrMapName ? allHistoricalMaps.filter((m) => m !== ocrMapName) : allHistoricalMaps
  ).slice(0, 5);

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
      if (
        config.ocr_autofill_id !== false &&
        Array.isArray(ocrResults.suspect_ids) &&
        ocrResults.suspect_ids.length > 0
      ) {
        const topCandidate =
          ocrResults.suspect_ids.find((id) => !existingWhitelist.includes(id)) ||
          ocrResults.suspect_ids[0];
        if (topCandidate) {
          setSuspectId((prev) => prev || topCandidate);
        }
      }
      const activePath = ocrResults.media_path;
      if (activePath) {
        setCurrentMediaPath(activePath);

        // Fetch streaming URL for video
        if (window.pywebview && window.pywebview.api && window.pywebview.api.get_media_stream_url) {
          window.pywebview.api
            .get_media_stream_url(activePath)
            .then((streamUrl) => {
              if (streamUrl) setMediaStreamUrl(streamUrl);
            })
            .catch((e) => {
              console.debug('Failed to get media stream url:', e);
            });
        }

        // Fetch fallback thumbnail
        if (window.pywebview && window.pywebview.api && window.pywebview.api.get_media_preview) {
          window.pywebview.api
            .get_media_preview(activePath)
            .then((dataUrl) => {
              if (dataUrl) setPreviewUrl(dataUrl);
            })
            .catch((e) => {
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
            message: `剪輯成功！已刪除該區段，新長度為 ${formatTime(res.duration || 0)}`,
          });
        } else {
          setTrimFeedback({ type: 'error', message: res.error || '剪輯失敗' });
        }
      } else {
        // Fallback for browser mock mode
        setTimeout(() => {
          if (!originalBackupPath) setOriginalBackupPath(currentMediaPath + '.backup.mp4');
          setTrimFeedback({
            type: 'success',
            message: `（模擬）成功剪輯片段！刪除 ${(cutEnd - cutStart).toFixed(1)} 秒。`,
          });
          setCutStart(0);
          setCutEnd(0);
          setIsTrimming(false);
        }, 600);
        return;
      }
    } catch (err: any) {
      setTrimFeedback({ type: 'error', message: err?.message || String(err) });
    }
    setIsTrimming(false);
  };

  // Restore original video before trimming
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
      } else {
        setOriginalBackupPath(null);
        setTrimFeedback({ type: 'success', message: '（模擬）已成功還原為原始錄影影片！' });
      }
    } catch (err: any) {
      setTrimFeedback({ type: 'error', message: err?.message || String(err) });
    }
    setIsTrimming(false);
  };

  const handlePasteClipboard = async () => {
    const text = await readClipboard();
    if (text) {
      setSuspectId(text.trim());
    }
  };

  const handleToggleWhitelistChip = (id: string) => {
    if (existingWhitelist.includes(id)) return;
    if (selectedForWhitelist.includes(id)) {
      setSelectedForWhitelist(selectedForWhitelist.filter((i) => i !== id));
    } else {
      setSelectedForWhitelist([...selectedForWhitelist, id]);
    }
  };

  const handleFinishWhitelistMode = () => {
    if (selectedForWhitelist.length > 0) {
      const newItems = selectedForWhitelist.filter((id) => !existingWhitelist.includes(id));
      if (newItems.length > 0) {
        onUpdateWhitelist([...existingWhitelist, ...newItems]);
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
          <span>{stage === 'progress' ? '檢舉證據辨識進度' : '檢舉證據回報表單'}</span>
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
                  : '送出檢舉證據'}
            </Button>
          </>
        )
      }
    >
      {stage === 'progress' ? (
        /* Stage 1: Recognition Progress State */
        <ProgressStage progressPercent={progressPercent} progressStatus={progressStatus} />
      ) : (
        /* Stage 2: Report Confirmation Form State (Steps 1 to 5) */
        <form onSubmit={handleSubmit} className="report-flow-form">
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
          <MediaPreviewSection
            currentMediaPath={currentMediaPath}
            mediaStreamUrl={mediaStreamUrl}
            previewUrl={previewUrl}
            originalBackupPath={originalBackupPath}
            isVideo={isVideo}
            isTrimOpen={isTrimOpen}
            videoDuration={videoDuration}
            currentPlaybackTime={currentPlaybackTime}
            cutStart={cutStart}
            cutEnd={cutEnd}
            isTrimming={isTrimming}
            trimFeedback={trimFeedback}
            videoRef={videoRef}
            formatTime={formatTime}
            onLoadedMetadata={handleLoadedMetadata}
            onTimeUpdate={handleTimeUpdate}
            onTimelineMouseDown={handleTimelineMouseDown}
            onSetCutStart={handleSetCutStart}
            onSetCutEnd={handleSetCutEnd}
            onClearCut={handleClearCut}
            onExecuteCut={handleExecuteCut}
            onRestoreOriginal={handleRestoreOriginal}
            onToggleTrimOpen={() => {
              setIsTrimOpen(!isTrimOpen);
              setTrimFeedback(null);
            }}
            onOpenFilePath={onOpenFilePath}
            onOpenFileLocation={onOpenFileLocation}
          />

          {/* Step 2: Suspect ID & Whitelist Selection */}
          <SuspectSelector
            suspectId={suspectId}
            whitelistMode={whitelistMode}
            ocrResults={ocrResults}
            existingWhitelist={existingWhitelist}
            selectedForWhitelist={selectedForWhitelist}
            idOcrEnabled={config.ocr_autofill_id !== false}
            onSuspectIdChange={setSuspectId}
            onPasteClipboard={handlePasteClipboard}
            onToggleWhitelistChip={handleToggleWhitelistChip}
            onEnterWhitelistMode={() => setWhitelistMode(true)}
            onCancelWhitelistMode={() => setWhitelistMode(false)}
            onFinishWhitelistMode={handleFinishWhitelistMode}
          />

          {/* Steps 3, 4, 5: Server, Map, Notes & Headless Toggle */}
          <ReportFormSection
            server={server}
            mapName={mapName}
            note={note}
            formSubmitHeadless={formSubmitHeadless}
            mapOcrEnabled={mapOcrEnabled}
            ocrMapName={ocrMapName}
            historicalMaps={historicalMaps}
            templates={config.violation_templates || []}
            onServerChange={setServer}
            onMapNameChange={setMapName}
            onNoteChange={setNote}
            onFormSubmitHeadlessChange={setFormSubmitHeadless}
          />
        </form>
      )}
    </Dialog>
  );
}
