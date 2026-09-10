import IndividualNoteEditor from './report-flow/IndividualNoteEditor';
import { appendSuspects } from '../domain/suspects';
import React, { useState, useEffect, useMemo, useRef } from 'react';
import { ArrowRight, FileCheck, Save } from 'lucide-react';
import { Dialog, Button, Badge, RadioGroup, Switch } from './ui';
import { useClipboard } from '../hooks';
import { getReporterBridge } from '../bridge/reporterBridge';
import { AppConfig, HistoryRecord, OcrResultData, SubmissionStatusData } from '../types';
import {
  ProgressStage,
  MediaPreviewSection,
  SuspectSelector,
  ReportFormSection,
  ManualReportAssistant,
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
  initialRecord?: HistoryRecord | null;
  isSavingDraft?: boolean;
  onClose: () => void;
  onSkipOcr?: () => void | Promise<void>;
  onSubmitReport: (formData: Record<string, unknown>) => Promise<void> | void;
  onSaveDraft?: (formData: Record<string, unknown>) => Promise<void> | void;
  onOpenFilePath?: (path: string) => void;
  onOpenFileLocation?: (path: string) => void;
  onRecognizeCurrentFrame?: (
    filePath: string,
    timestampSec: number
  ) => Promise<OcrResultData | null>;
  onUpdateWhitelist: (newWhitelist: string[]) => void;
  onPersistFormSubmitHeadless?: (enabled: boolean) => void;
  onPersistSubmissionMode?: (mode: 'manual' | 'automatic') => void;
  manualReport?: HistoryRecord | null;
  isConfirmingManual?: boolean;
  onOpenReportPage?: () => void;
  onConfirmManual?: (recordId: string) => void | Promise<void>;
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
    report_submission_mode: 'automatic',
    audio_output_device_id: '',
  },
  history = [],
  initialRecord = null,
  isSavingDraft = false,
  onClose,
  onSkipOcr,
  onSubmitReport,
  onSaveDraft,
  onOpenFilePath,
  onOpenFileLocation,
  onRecognizeCurrentFrame,
  onUpdateWhitelist,
  onPersistFormSubmitHeadless,
  onPersistSubmissionMode,
  manualReport = null,
  isConfirmingManual = false,
  onOpenReportPage,
  onConfirmManual,
}: ReportFlowModalProps) {
  const existingWhitelist = useMemo(
    () => (Array.isArray(config.whitelist) ? config.whitelist : []),
    [config.whitelist]
  );

  const targetBatchId = manualReport?.batch_id || initialRecord?.batch_id || submissionStatus?.batch_id;
  const batchRows = useMemo(() => {
    const historyRows = targetBatchId
      ? history.filter((r) => r.batch_id === targetBatchId)
      : [];
    const rows = submissionStatus?.records?.length
      ? submissionStatus.records
      : historyRows.length
        ? historyRows
        : manualReport && manualReport.batch_id === targetBatchId
          ? [manualReport]
          : [];
    return [...rows].sort((a, b) => (a.batch_order || 0) - (b.batch_order || 0));
  }, [history, manualReport, submissionStatus?.records, targetBatchId]);
  const activeBatchId = initialRecord?.batch_id || submissionStatus?.batch_id || batchRows[0]?.batch_id;
  const [names, setNames] = useState<string[]>(() =>
    batchRows.length
      ? batchRows.map((r) => r.suspect_id || '').filter(Boolean)
      : initialRecord?.suspect_id
        ? [initialRecord.suspect_id]
        : []
  );
  const [suspectId, setSuspectId] = useState('');
  const didAutofill = useRef(Boolean(initialRecord));
  useEffect(() => {
    if (didAutofill.current || config.ocr_autofill_id === false) return;
    const first = ocrResults.suspect_ids?.find((id) => !existingWhitelist.includes(id));
    if (!first) return;
    didAutofill.current = true;
    if (!names.length && !suspectId) setNames([first]);
  }, [config.ocr_autofill_id, existingWhitelist, ocrResults.suspect_ids, names.length, suspectId]);
  const [overrides, setOverrides] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      batchRows.filter((r) => r.note_override != null).map((r) => [r.suspect_id!, r.note_override!])
    )
  );
  const [resolving, setResolving] = useState(false);
  const [resolutionError, setResolutionError] = useState('');
  const getOverride = (name: string): string | undefined =>
    Object.prototype.hasOwnProperty.call(overrides, name) ? overrides[name] : undefined;
  const batchLocked = batchRows.some((r) => r.batch_phase !== 'draft');
  const effectiveNames = appendSuspects(names, suspectId);
  const commitNames = () => {
    setNames(effectiveNames);
    setSuspectId('');
    return effectiveNames;
  };
  const makeSuspects = (values: string[]) =>
    values.map((name) => ({
      suspect_id: name,
      note_override: getOverride(name) ?? null,
    }));
  const resolveResult = async (record: HistoryRecord, completed: boolean) => {
    const bridge = getReporterBridge();
    if (!bridge || !record.record_id) return;
    setResolving(true);
    setResolutionError('');
    try {
      const result = await bridge.reports.resolveResult({ record_id: record.record_id, completed });
      if (result.status === 'error') setResolutionError(result.message);
    } catch (error: unknown) {
      setResolutionError(error instanceof Error ? error.message : '無法更新送件結果，請稍後再試。');
    } finally {
      setResolving(false);
    }
  };
  const [server, setServer] = useState(initialRecord?.server || config.default_server || '雪吉拉');
  const [mapName, setMapName] = useState(
    initialRecord
      ? String(initialRecord.map_name || initialRecord.map || '')
      : ocrResults.map_name || ''
  );
  const [note, setNote] = useState(
    initialRecord
      ? String(initialRecord.batch_note ?? initialRecord.note ?? '')
      : config.default_note || '自動打怪/外掛行為'
  );
  const [formSubmitHeadless, setFormSubmitHeadless] = useState(
    config.form_submit_headless !== false
  );
  const [submissionMode, setSubmissionMode] = useState<'manual' | 'automatic'>(
    (initialRecord?.submission_mode || config.report_submission_mode) === 'manual'
      ? 'manual'
      : 'automatic'
  );
  const backgroundSettingRef = useRef<HTMLDivElement>(null);
  const shouldScrollToBackgroundRef = useRef(false);

  useEffect(() => {
    if (!shouldScrollToBackgroundRef.current || submissionMode !== 'automatic') return;
    shouldScrollToBackgroundRef.current = false;
    const frameId = requestAnimationFrame(() => {
      const element = backgroundSettingRef.current;
      if (!element || typeof element.scrollIntoView !== 'function') return;
      const reduceMotion =
        typeof window.matchMedia === 'function' &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      element.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'end' });
    });
    return () => cancelAnimationFrame(frameId);
  }, [submissionMode]);

  // Whitelist Mode State (Step 2)
  const [whitelistMode, setWhitelistMode] = useState(false);
  const [selectedForWhitelist, setSelectedForWhitelist] = useState<string[]>([]);

  // Media State & Stream Player
  const [currentMediaPath, setCurrentMediaPath] = useState<string>(
    initialRecord?.media_path || ocrResults.media_path || ''
  );
  const [mediaStreamUrl, setMediaStreamUrl] = useState<string>('');
  const [mediaError, setMediaError] = useState('');
  const [previewUrl, setPreviewUrl] = useState<string>('');
  const [originalBackupPath, setOriginalBackupPath] = useState<string | null>(null);

  // Video playback & Trimming state
  const isVideo =
    initialRecord?.media_type === 'video' ||
    ocrResults.media_type === 'video' ||
    /\.(mp4|mkv|avi|mov)$/i.test(currentMediaPath);
  const [isTrimOpen, setIsTrimOpen] = useState(false);
  const [videoDuration, setVideoDuration] = useState(0);
  const [currentPlaybackTime, setCurrentPlaybackTime] = useState(0);
  const [isVideoPaused, setIsVideoPaused] = useState(true);
  const [isRecognizingCurrentFrame, setIsRecognizingCurrentFrame] = useState(false);
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
    if (ocrResults?.map_name) {
      setMapName(ocrResults.map_name);
    }
  }, [ocrResults?.map_name]);

  useEffect(() => {
    const activePath =
      manualReport?.media_path || initialRecord?.media_path || ocrResults?.media_path || '';
    let cancelled = false;
    setCurrentMediaPath(activePath);
    setMediaStreamUrl('');
    setPreviewUrl('');
    setMediaError('');
    setVideoDuration(0);
    if (!activePath) return;
    const bridge = getReporterBridge();
    if (!bridge) return;
    void bridge.media
      .streamUrl(activePath)
      .then((url) => {
        if (cancelled) return;
        setMediaStreamUrl(url || '');
        if (!url) setMediaError('無法讀取本機證據，檔案可能已移動、刪除或無法開啟。');
      })
      .catch(() => {
        if (!cancelled) setMediaError('無法載入本機證據，請確認檔案是否仍存在。');
      });
    void bridge.media
      .preview(activePath)
      .then((url) => {
        if (!cancelled) setPreviewUrl(url || '');
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [initialRecord?.media_path, manualReport?.media_path, ocrResults?.media_path]);

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

  const handleRecognizeCurrentFrame = async () => {
    if (!onRecognizeCurrentFrame || !isVideo || !isVideoPaused || !currentMediaPath) return;

    const timestamp = Number((videoRef.current?.currentTime ?? currentPlaybackTime).toFixed(2));
    setIsRecognizingCurrentFrame(true);
    try {
      await onRecognizeCurrentFrame(currentMediaPath, timestamp);
    } finally {
      setIsRecognizingCurrentFrame(false);
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
      const bridge = getReporterBridge();
      if (bridge) {
        const res = await bridge.media.trim(
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
    } catch (error: unknown) {
      setTrimFeedback({
        type: 'error',
        message: error instanceof Error ? error.message : String(error),
      });
    }
    setIsTrimming(false);
  };

  // Restore original video before trimming
  const handleRestoreOriginal = async () => {
    if (!originalBackupPath) return;
    setIsTrimming(true);
    setTrimFeedback(null);
    try {
      const bridge = getReporterBridge();
      if (bridge) {
        const res = await bridge.media.restore(currentMediaPath, originalBackupPath);
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
    } catch (error: unknown) {
      setTrimFeedback({
        type: 'error',
        message: error instanceof Error ? error.message : String(error),
      });
    }
    setIsTrimming(false);
  };

  const handlePasteClipboard = async () => {
    const text = await readClipboard();
    if (text) {
      setNames(appendSuspects(names, text));
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
    if (isSubmitting || !effectiveNames.length || !mapName.trim()) return;
    const selected = commitNames();

    await onSubmitReport({
      suspect_id: selected[0],
      suspects: makeSuspects(selected),
      batch_id: activeBatchId,
      server,
      map_name: mapName.trim(),
      note: note.trim(),
      media_path: currentMediaPath || ocrResults.media_path,
      file_path: currentMediaPath || ocrResults.media_path,
      form_submit_headless: formSubmitHeadless,
      submission_mode: submissionMode,
      dev_mode: Boolean(config.dev_mode),
      record_id: initialRecord?.record_id,
      media_type: isVideo ? 'video' : 'image',
    });
  };

  const handleSaveDraft = async () => {
    if (!onSaveDraft || isSavingDraft || isSubmitting || !currentMediaPath) return;
    const fromProgress = stage === 'progress';
    const selected = commitNames();
    const isExistingBatch = Boolean(activeBatchId);
    await onSaveDraft({
      suspect_id: isExistingBatch
        ? selected[0] || initialRecord?.suspect_id || ''
        : fromProgress
          ? ''
          : selected[0] || '',
      suspects: isExistingBatch
        ? makeSuspects(selected)
        : fromProgress
          ? undefined
          : makeSuspects(selected),
      batch_id: activeBatchId,
      submission_mode: submissionMode,
      server: isExistingBatch ? server : fromProgress ? '' : server,
      map_name: isExistingBatch ? mapName.trim() : fromProgress ? '' : mapName.trim(),
      note: isExistingBatch ? note.trim() : fromProgress ? '' : note.trim(),
      media_path: currentMediaPath,
      file_path: currentMediaPath,
      media_type: isVideo ? 'video' : 'image',
      record_id: initialRecord?.record_id,
    });
  };

  if (manualReport) {
    return (
      <Dialog
        isOpen={true}
        onClose={isConfirmingManual ? undefined : onClose}
        title="手動檢舉"
        titleIcon={FileCheck}
        maxWidth="680px"
      >
        {manualReport.batch_id && (
          <p className="report-mode-description" role="status">
            本批已完成 {batchRows.filter((r) => r.submission_state === 'submitted').length} /{' '}
            {batchRows.length} 人；目前處理 {manualReport.suspect_id}
          </p>
        )}
        <ManualReportAssistant
          key={manualReport.record_id}
          record={manualReport}
          mediaStreamUrl={mediaStreamUrl}
          mediaPreviewUrl={previewUrl}
          mediaError={mediaError}
          onMediaError={() => setMediaError('影片無法播放，請確認本機檔案完整且格式受支援。')}
          isConfirming={isConfirmingManual}
          onOpenReportPage={() => onOpenReportPage?.()}
          onConfirm={(recordId) => onConfirmManual?.(recordId)}
          onLater={onClose}
        />
      </Dialog>
    );
  }

  return (
    <Dialog
      isOpen={true}
      onClose={isSubmitting || isSavingDraft ? undefined : onClose}
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>{stage === 'progress' ? '檢舉證據辨識進度' : '檢舉證據回報表單'}</span>
          {config.dev_mode && stage === 'form' && submissionMode === 'automatic' && (
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
            <Button variant="outline" size="md" onClick={onClose} disabled={isSavingDraft}>
              取消
            </Button>
            <div className="report-footer-actions">
              {onSaveDraft && !batchLocked && (!initialRecord || initialRecord.batch_id) && (
                <Button
                  variant="secondary"
                  size="md"
                  onClick={handleSaveDraft}
                  icon={Save}
                  loading={isSavingDraft}
                  disabled={!currentMediaPath || isSavingDraft}
                  data-testid="save-draft-progress"
                >
                  {isSavingDraft ? '儲存中…' : '先儲存，稍後檢舉'}
                </Button>
              )}
              {onSkipOcr && (
                <Button
                  variant="primary"
                  size="md"
                  onClick={onSkipOcr}
                  icon={ArrowRight}
                  iconPosition="right"
                  disabled={isSavingDraft}
                  data-testid="skip-ocr-button"
                >
                  略過辨識，直接填表
                </Button>
              )}
            </div>
          </div>
        ) : (
          <div className="report-form-footer">
            <Button
              variant="outline"
              size="md"
              onClick={onClose}
              disabled={isSubmitting || isSavingDraft}
            >
              取消
            </Button>
            <div className="report-footer-actions">
              {onSaveDraft && !batchLocked && (!initialRecord || initialRecord.batch_id) && (
                <Button
                  variant="secondary"
                  size="md"
                  icon={Save}
                  onClick={handleSaveDraft}
                  loading={isSavingDraft}
                  disabled={!currentMediaPath || isSavingDraft || isSubmitting}
                  data-testid="save-draft-form"
                >
                  {isSavingDraft ? '儲存中…' : '儲存，稍後檢舉'}
                </Button>
              )}
              <Button
                variant="primary"
                size="md"
                icon={ArrowRight}
                iconPosition="right"
                onClick={handleSubmit}
                disabled={
                  !effectiveNames.length ||
                  !mapName.trim() ||
                  isSubmitting ||
                  isSavingDraft ||
                  resolving ||
                  batchRows.some((r) => ['unknown', 'sending'].includes(r.batch_phase || ''))
                }
                loading={isSubmitting}
                aria-busy={isSubmitting}
                data-testid="report-submit"
              >
                {isSubmitting
                  ? submissionMode === 'manual'
                    ? '上傳中…'
                    : '送出中…'
                  : config.dev_mode && submissionMode === 'automatic'
                    ? `模擬檢舉 ${effectiveNames.length} 人（不實際送出）`
                    : submissionMode === 'manual'
                      ? `開始手動檢舉 ${effectiveNames.length} 人`
                      : batchLocked
                        ? '繼續未完成的檢舉'
                        : `開始檢舉 ${effectiveNames.length} 人`}
              </Button>
            </div>
          </div>
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

          {resolutionError && (
            <div className="submission-status-message error" role="alert">
              {resolutionError}
            </div>
          )}
          {batchRows.length > 0 && (
            <div className="batch-progress" aria-label="逐人檢舉進度">
              <p>
                已完成 {batchRows.filter((r) => r.submission_state === 'submitted').length} /{' '}
                {batchRows.length} 人
                <span className="batch-progress-caption">每人分開儲存紀錄</span>
              </p>
              {batchRows.map((row) => (
                <div className="batch-progress-row" key={row.record_id}>
                  <span>{row.suspect_id}</span>
                  <span>
                    {row.submission_state === 'submitted'
                      ? '已完成'
                      : row.batch_phase === 'sending' && isSubmitting
                        ? '送出中'
                        : ['unknown', 'sending'].includes(row.batch_phase || '')
                          ? '結果待確認'
                          : row.submission_state === 'awaiting_manual'
                            ? '待手動檢舉'
                            : '尚未送出'}
                  </span>
                  {!isSubmitting && ['unknown', 'sending'].includes(row.batch_phase || '') && (
                    <div className="report-footer-actions">
                      <Button
                        size="sm"
                        disabled={resolving}
                        onClick={() => resolveResult(row, true)}
                      >
                        確認已完成
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={resolving}
                        onClick={() => resolveResult(row, false)}
                      >
                        允許重試
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          {/* Step 1: Media Confirmation with Direct 16:9 Preview & Right Actions */}
          <MediaPreviewSection
            currentMediaPath={currentMediaPath}
            mediaStreamUrl={mediaStreamUrl}
            mediaError={mediaError}
            readOnly={isSubmitting || isSavingDraft || batchLocked}
            onMediaError={() =>
              setMediaError(
                '影片無法播放，請確認本機檔案完整且格式受支援，也可使用系統播放器開啟。'
              )
            }
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
            onVideoPlay={() => setIsVideoPaused(false)}
            onVideoPause={() => setIsVideoPaused(true)}
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
            onRecognizeCurrentFrame={handleRecognizeCurrentFrame}
            isRecognizingCurrentFrame={isRecognizingCurrentFrame}
            isVideoPaused={isVideoPaused}
          />

          <fieldset
            className="batch-edit-fields"
            disabled={isSubmitting || isSavingDraft || batchLocked}
          >
            {/* Step 2: Suspect ID & Whitelist Selection */}
            <SuspectSelector
              suspectId={suspectId}
              names={names}
              onNamesChange={setNames}
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
              mapOcrEnabled={mapOcrEnabled}
              ocrMapName={ocrMapName}
              historicalMaps={historicalMaps}
              templates={config.violation_templates || []}
              onServerChange={setServer}
              onMapNameChange={setMapName}
              onNoteChange={setNote}
              individualNotes={
                names.length > 0 && (
                  <IndividualNoteEditor
                    names={names}
                    sharedNote={note}
                    getOverride={getOverride}
                    disabled={isSubmitting || isSavingDraft || batchLocked}
                    onChange={(name, value) => setOverrides({ ...overrides, [name]: value })}
                    onReset={(name) => {
                      const next = { ...overrides };
                      delete next[name];
                      setOverrides(next);
                    }}
                  />
                )
              }
            />

            <div className="step-block report-mode-selector" data-testid="report-mode-selector">
              <div className="step-title-row">
                <span className="step-number">6</span>
                <span>檢舉方式</span>
              </div>
              <div className="report-mode-description">選擇手動填寫或由工具自動填寫。</div>
              <RadioGroup<'manual' | 'automatic'>
                name="submission-mode"
                value={submissionMode}
                direction="horizontal"
                className="report-mode-choice-list"
                onChange={(mode) => {
                  shouldScrollToBackgroundRef.current = mode === 'automatic';
                  setSubmissionMode(mode);
                  onPersistSubmissionMode?.(mode);
                }}
                options={[
                  {
                    value: 'automatic',
                    label: (
                      <span>
                        <strong>自動檢舉</strong>
                        <small>使用獨立瀏覽器填寫官方表單，並可設定是否在背景進行。</small>
                      </span>
                    ),
                  },
                  {
                    value: 'manual',
                    label: (
                      <span>
                        <strong>手動檢舉</strong>
                        <small>上傳證據後，由你開啟官方頁面並複製欄位。</small>
                      </span>
                    ),
                  },
                ]}
              />
              {submissionMode === 'automatic' && (
                <div
                  ref={backgroundSettingRef}
                  className="report-background-setting"
                  data-testid="report-background-setting"
                  role="region"
                  aria-label="自動檢舉設定"
                  aria-live="polite"
                >
                  <div>
                    <strong>在背景完成填表</strong>
                    <span>開啟後不顯示瀏覽器視窗；關閉後可看到填表與送出過程。</span>
                  </div>
                  <Switch
                    checked={formSubmitHeadless}
                    onChange={(value) => {
                      setFormSubmitHeadless(value);
                      onPersistFormSubmitHeadless?.(value);
                    }}
                    aria-label="在背景完成填表"
                  />
                </div>
              )}
            </div>
          </fieldset>
        </form>
      )}
    </Dialog>
  );
}
