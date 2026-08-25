import { useCallback, useRef, useState } from 'react';
import { getReporterBridge } from '../bridge/reporterBridge';
import { usePyWebViewEvents } from './usePyWebViewEvents';
import { useToast } from './useToast';
import {
  getSubmissionState,
  SUBMISSION_AWAITING_MANUAL,
  SUBMISSION_DRAFT,
} from '../domain/history';
import {
  AppConfig,
  HistoryRecord,
  OcrResultData,
  StatusState,
  SubmissionStatusData,
} from '../types';
import { normalizeOcrResult } from '../utils/appHelpers';

export interface ReportWorkflowOptions {
  config: AppConfig;
  onHistoryChange: (records: HistoryRecord[]) => void;
}

export interface ReportWorkflowResult {
  statusState: StatusState;
  recordingTime: number;
  countdown: number;
  countdownTotal: number;
  countdownFraction: number | undefined;
  recordingFraction: number | undefined;
  replayTime: number;
  modalOpen: boolean;
  modalStage: 'progress' | 'form';
  modalProgress: number;
  modalStatusText: string;
  isSubmittingReport: boolean;
  isSavingDraft: boolean;
  submissionStatus: SubmissionStatusData | null;
  isResetting: boolean;
  reportWorkflowId: number;
  ocrResults: OcrResultData;
  activeHistoryRecord: HistoryRecord | null;
  manualReport: HistoryRecord | null;
  isConfirmingManual: boolean;
  handleCaptureScreenshot: () => Promise<void>;
  handleCancelRecording: () => Promise<void>;
  handleRecordVideo: () => Promise<void>;
  handleToggleReplay: () => Promise<void>;
  handleSkipOcr: () => void;
  handleSaveReplay: () => Promise<void>;
  handleSelectFile: () => Promise<void>;
  handleRecognizeCurrentFrame: (
    filePath: string,
    timestampSec: number
  ) => Promise<OcrResultData | null>;
  handleSubmitReport: (formData: Record<string, unknown>) => Promise<void>;
  handleConfirmManualReport: (recordId: string) => Promise<void>;
  handleSaveReportDraft: (formData: Record<string, unknown>) => Promise<void>;
  handleContinueDraft: (record: HistoryRecord, runRecognition: boolean) => Promise<void>;
  handleContinueManual: (record: HistoryRecord) => void;
  handleCloseReport: () => void;
  handleStopReplay: () => Promise<void>;
  restoreReplayState: (state?: string, duration?: number) => void;
}

export function useReportWorkflow({
  config,
  onHistoryChange,
}: ReportWorkflowOptions): ReportWorkflowResult {
  const { toast } = useToast();
  const [statusState, setStatusState] = useState<StatusState>('idle');
  const [recordingTime, setRecordingTime] = useState(0);
  const [countdown, setCountdown] = useState(0);
  const [countdownTotal, setCountdownTotal] = useState(3);
  const [countdownFraction, setCountdownFraction] = useState<number | undefined>(undefined);
  const [recordingFraction, setRecordingFraction] = useState<number | undefined>(undefined);
  const [replayTime, setReplayTime] = useState(0);
  const animFrameRef = useRef<number | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [modalStage, setModalStage] = useState<'progress' | 'form'>('progress');
  const modalStageRef = useRef(modalStage);
  modalStageRef.current = modalStage;
  const [modalProgress, setModalProgress] = useState(0);
  const [modalStatusText, setModalStatusText] = useState('');
  const [isSubmittingReport, setIsSubmittingReport] = useState(false);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [submissionStatus, setSubmissionStatus] = useState<SubmissionStatusData | null>(null);
  const [isResetting, setIsResetting] = useState(false);
  const [reportWorkflowId, setReportWorkflowId] = useState(0);
  const [ocrResults, setOcrResults] = useState<OcrResultData>({
    suspect_ids: [],
    map_name: '',
    media_path: '',
    media_type: 'video',
  });
  const [activeHistoryRecord, setActiveHistoryRecord] = useState<HistoryRecord | null>(null);
  const [manualReport, setManualReport] = useState<HistoryRecord | null>(null);
  const [isConfirmingManual, setIsConfirmingManual] = useState(false);
  const ocrCancelledRef = useRef(false);
  const frameOcrActiveRef = useRef(false);

  const resetOcrResultsForWorkflow = (
    mediaPath = '',
    mediaType: OcrResultData['media_type'] = 'video'
  ) => {
    setOcrResults({
      suspect_ids: [],
      map_name: '',
      ocr_map_name: '',
      map_name_source: undefined,
      media_path: mediaPath,
      media_type: mediaType,
    });
  };

  const beginOcrWorkflow = (mediaPath = '', mediaType: OcrResultData['media_type'] = 'video') => {
    ocrCancelledRef.current = false;
    setActiveHistoryRecord(null);
    setManualReport(null);
    setReportWorkflowId((previous) => previous + 1);
    resetOcrResultsForWorkflow(mediaPath, mediaType);
  };

  const cancelAnim = () => {
    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
  };

  const refreshHistory = async () => {
    const bridge = getReporterBridge();
    if (!bridge) return [];
    const records = await bridge.history.load();
    if (Array.isArray(records)) onHistoryChange(records);
    return Array.isArray(records) ? records : [];
  };

  usePyWebViewEvents({
    RECORDING_COUNTDOWN: (data: { remaining: number; percent: number; total: number }) => {
      setStatusState('recording');
      setCountdown(data.remaining);
      setCountdownTotal(data.total || 3);
      setCountdownFraction((data.percent || 0) / 100);
      setRecordingTime(0);
      setRecordingFraction(0);
    },
    RECORDING_PROGRESS: (data: {
      elapsed: number;
      total: number;
      percent: number;
      fraction?: number;
    }) => {
      setStatusState('recording');
      setCountdown(0);
      setCountdownFraction(0);
      const frac =
        data.fraction !== undefined
          ? data.fraction
          : Math.max(0, Math.min(1, (data.percent || 0) / 100));
      setRecordingFraction((prev) => (prev !== undefined ? Math.max(prev, frac) : frac));
      setRecordingTime((prev) => Math.max(prev, data.elapsed));
    },
    RECORDING_FINISHED: (data?: { file_path?: string }) => {
      beginOcrWorkflow(data?.file_path || '', 'video');
      cancelAnim();
      setStatusState('idle');
      setRecordingTime(0);
      setCountdown(0);
      setCountdownFraction(undefined);
      setRecordingFraction(undefined);
      setSubmissionStatus(null);
      setModalStage('progress');
      setModalProgress(35);
      setModalStatusText('錄影已完成，正在解析關鍵影格...');
      setModalOpen(true);
    },
    RECORDING_CANCELED: () => {
      cancelAnim();
      setStatusState('idle');
      setRecordingTime(0);
      setCountdown(0);
      setCountdownFraction(undefined);
      setRecordingFraction(undefined);
      toast.info('錄影已取消');
    },
    RECORDING_ERROR: (data: { message: string }) => {
      cancelAnim();
      setStatusState('idle');
      setRecordingTime(0);
      setCountdown(0);
      setCountdownFraction(undefined);
      setRecordingFraction(undefined);
      toast.error('錄影失敗', data.message);
      setModalOpen(false);
    },
    REPLAY_STATE_CHANGED: (data: { state: string; duration: number; total: number }) => {
      if (['warming', 'ready', 'saving'].includes(data.state)) {
        setStatusState('replaying');
      } else {
        setStatusState('idle');
      }
      setReplayTime(Math.floor(data.duration));
    },
    REPLAY_SAVED: (data?: { file_path?: string }) => {
      if (ocrCancelledRef.current) {
        const savedPath = data?.file_path || '';
        if (savedPath) {
          setOcrResults((previous) => ({
            ...previous,
            media_path: savedPath,
            media_type: 'video',
          }));
        }
        return;
      }
      beginOcrWorkflow(data?.file_path || '', 'video');
      setSubmissionStatus(null);
      setModalStage('progress');
      setModalProgress(40);
      setModalStatusText('已儲存循環錄影，正在解析關鍵影格...');
      setModalOpen(true);
    },
    REPLAY_ERROR: (data: { message: string }) => {
      toast.error('循環錄影錯誤', data.message);
      setModalOpen(false);
    },
    OCR_STATUS: (data: { status: string; percent: number; step?: string }) => {
      if (ocrCancelledRef.current) return;
      if (modalStageRef.current !== 'form') {
        setModalProgress(data.percent || 50);
        if (data.status) setModalStatusText(data.status);
      }
    },
    OCR_RESULT: (data: OcrResultData) => {
      if (ocrCancelledRef.current) return;
      setOcrResults((prev) => normalizeOcrResult(data, prev, config));
      setSubmissionStatus(null);
      setModalProgress(100);
      setModalStatusText('辨識完成');
      setModalStage('form');
      setModalOpen(true);
    },
    SUBMISSION_STATUS: (data: SubmissionStatusData) => {
      if (!data?.message) return;
      setSubmissionStatus({
        step: data.step,
        status: data.status || 'progress',
        message: data.message,
      });
      setModalStatusText(data.message);
    },
    GLOBAL_HOTKEY_TRIGGERED: (data: { action: string }) => {
      toast.info(
        '快捷鍵已觸發',
        data.action === 'save_replay' ? '正在儲存循環錄影片段' : '正在執行錄影'
      );
    },
    EVIDENCE_READY: (data: { file_path?: string; media_type?: 'video' | 'image' }) => {
      const filePath = data?.file_path || '';
      if (!filePath) return;
      setOcrResults((previous) => ({
        ...previous,
        media_path: filePath,
        media_type: data.media_type || previous.media_type,
      }));
    },
  });

  const handleCaptureScreenshot = async () => {
    beginOcrWorkflow('', 'image');
    setSubmissionStatus(null);
    setModalStage('progress');
    setModalProgress(30);
    setModalStatusText('正在截圖並進行辨識...');
    setModalOpen(true);

    const bridge = getReporterBridge();
    if (bridge) {
      try {
        const result = await bridge.capture.screenshot('window');
        if (ocrCancelledRef.current) return;
        if (result && result.status === 'success') {
          setOcrResults((prev) => normalizeOcrResult(result, prev, config));
          setModalProgress(100);
          setModalStatusText('辨識完成');
          setModalStage('form');
          return;
        }
        if (result && result.status === 'error') {
          toast.error('截圖失敗', result.message || '無法截取遊戲視窗');
          setModalOpen(false);
          return;
        }
      } catch (error: unknown) {
        if (ocrCancelledRef.current) return;
        toast.error('截圖辨識發生異常', error instanceof Error ? error.message : String(error));
        setModalOpen(false);
        return;
      }
    }

    setTimeout(() => {
      if (ocrCancelledRef.current) return;
      setOcrResults((prev) =>
        normalizeOcrResult(
          {
            suspect_ids: [],
            map_name: config.default_map || '',
            ocr_map_name: '',
            map_name_source: 'default',
            media_path: '',
            media_type: 'image',
          },
          prev,
          config
        )
      );
      setModalProgress(100);
      setModalStage('form');
    }, 400);
  };

  const startRealtimeProgress = (cdSec: number, recSec: number) => {
    cancelAnim();
    const cdMs = cdSec * 1000;
    const recMs = recSec * 1000;
    const startTime = performance.now();

    const tick = () => {
      const elapsed = performance.now() - startTime;
      if (cdSec > 0 && elapsed < cdMs) {
        const remainingCd = cdMs - elapsed;
        const cdFrac = Math.max(0, Math.min(1, remainingCd / cdMs));
        setCountdown(Math.ceil(remainingCd / 1000));
        setCountdownTotal(cdSec);
        setCountdownFraction(cdFrac);
        setRecordingFraction(0);
        setRecordingTime(0);
        animFrameRef.current = requestAnimationFrame(tick);
        return;
      }

      const recElapsed = cdSec > 0 ? elapsed - cdMs : elapsed;
      const recFrac = Math.max(0, Math.min(1, recElapsed / recMs));
      const recSecInt = Math.min(recSec, Math.floor(recElapsed / 1000));
      setCountdown(0);
      setCountdownFraction(0);
      setRecordingTime((prev) => Math.max(prev, recSecInt));
      setRecordingFraction((prev) => (prev !== undefined ? Math.max(prev, recFrac) : recFrac));

      if (recElapsed < recMs) {
        animFrameRef.current = requestAnimationFrame(tick);
        return;
      }

      setRecordingFraction(1.0);
      setRecordingTime(recSec);
      animFrameRef.current = null;
      if (!getReporterBridge()) {
        setTimeout(() => {
          if (ocrCancelledRef.current) return;
          setStatusState('idle');
          setRecordingFraction(undefined);
          setCountdownFraction(undefined);
          setModalStage('progress');
          setModalProgress(50);
          setModalOpen(true);
          setTimeout(() => {
            if (ocrCancelledRef.current) return;
            setOcrResults((prev) =>
              normalizeOcrResult(
                {
                  suspect_ids: [],
                  map_name: config.default_map || '',
                  ocr_map_name: '',
                  map_name_source: 'default',
                  media_path: '',
                  media_type: 'video',
                },
                prev,
                config
              )
            );
            setModalProgress(100);
            setModalStage('form');
          }, 400);
        }, 200);
      }
    };

    animFrameRef.current = requestAnimationFrame(tick);
  };

  const handleCancelRecording = async () => {
    if (isResetting) return;
    setIsResetting(true);
    cancelAnim();
    try {
      await getReporterBridge()?.capture.cancelRecording();
    } catch {
      // ignore cancellation errors; state is reset below.
    } finally {
      setStatusState('idle');
      setRecordingTime(0);
      setCountdown(0);
      setCountdownFraction(undefined);
      setRecordingFraction(undefined);
      setTimeout(() => setIsResetting(false), 300);
    }
  };

  const handleRecordVideo = async () => {
    if (isResetting) return;
    if (statusState === 'recording' || countdown > 0) {
      await handleCancelRecording();
      return;
    }

    const cd = config.record_countdown_sec || 0;
    const dur = config.record_duration_sec || 8;
    beginOcrWorkflow('', 'video');
    setIsResetting(true);
    const bridge = getReporterBridge();
    if (bridge) {
      try {
        await bridge.capture.startRecording(
          config.record_duration_sec,
          config.record_fps,
          config.record_countdown_sec || 0,
          config.record_audio !== false,
          config.audio_output_device_id || '',
          config.audio_capture_mode
        );
      } catch (error: unknown) {
        cancelAnim();
        toast.error('錄影啟動失敗', error instanceof Error ? error.message : String(error));
        setStatusState('idle');
        setCountdown(0);
        setCountdownFraction(undefined);
        setRecordingFraction(undefined);
      } finally {
        setTimeout(() => setIsResetting(false), 300);
      }
    } else {
      setStatusState('recording');
      startRealtimeProgress(cd, dur);
      setTimeout(() => setIsResetting(false), 300);
    }
  };

  const handleToggleReplay = async () => {
    if (statusState === 'replaying') {
      await getReporterBridge()?.capture.stopReplay();
      setStatusState('idle');
      toast.info('已停止循環錄影');
      return;
    }

    const bridge = getReporterBridge();
    if (bridge) {
      const ok = await bridge.capture.startReplay(
        config.selected_window_title,
        config.record_fps,
        config.replay_buffer_sec,
        config.record_audio !== false,
        config.audio_output_device_id || '',
        config.audio_capture_mode
      );
      if (ok) {
        setStatusState('replaying');
        toast.info('已啟動循環錄影', `持續保留最近 ${config.replay_buffer_sec || 30} 秒畫面`);
      }
    } else {
      setStatusState('replaying');
      setReplayTime(30);
      toast.info('已啟動循環錄影（測試）');
    }
  };

  const handleSkipOcr = () => {
    ocrCancelledRef.current = true;
    void getReporterBridge()
      ?.capture.cancelOcr()
      .catch(() => undefined);
    setModalStage('form');
    setModalProgress(100);
    setModalStatusText('已略過辨識');
    setOcrResults((prev) => ({
      ...prev,
      map_name: prev.map_name || config.default_map || '',
      ocr_map_name: '',
      map_name_source: 'default',
    }));
  };

  const handleSaveReplay = async () => {
    beginOcrWorkflow('', 'video');
    setSubmissionStatus(null);
    const bridge = getReporterBridge();
    if (bridge) {
      try {
        const ok = await bridge.capture.saveReplay();
        if (!ok) {
          toast.warning('循環錄影片段尚未就緒', '請稍候幾秒待緩衝累積後再儲存');
        } else {
          setModalStage('progress');
          setModalProgress(35);
          setModalStatusText('已儲存循環錄影，正在解析關鍵影格...');
          setModalOpen(true);
        }
      } catch (error: unknown) {
        toast.error('儲存循環錄影失敗', error instanceof Error ? error.message : String(error));
      }
    } else {
      setModalStage('progress');
      setModalProgress(35);
      setModalStatusText('正在分析檢舉證據檔案...');
      setModalOpen(true);
      setTimeout(() => {
        setOcrResults((prev) =>
          normalizeOcrResult(
            {
              suspect_ids: [],
              map_name: config.default_map || '',
              map_name_source: 'default',
              media_path: '',
              media_type: 'video',
            },
            prev,
            config
          )
        );
        setModalProgress(100);
        setModalStage('form');
      }, 400);
    }
  };

  const handleSelectFile = async () => {
    const bridge = getReporterBridge();
    if (bridge) {
      try {
        const filePath = await bridge.capture.selectLocalFile();
        if (filePath) {
          beginOcrWorkflow(filePath, /\.(mp4|mkv|avi|mov)$/i.test(filePath) ? 'video' : 'image');
          setSubmissionStatus(null);
          setModalStage('progress');
          setModalProgress(25);
          setModalStatusText('已選取檢舉證據檔案，正在分析畫面...');
          setModalOpen(true);
          const result = await bridge.capture.processImportedFile(filePath);
          if (ocrCancelledRef.current) return;
          if (result?.status === 'success') {
            setOcrResults((prev) => normalizeOcrResult(result, prev, config));
            setModalProgress(100);
            setModalStatusText('辨識完成');
            setModalStage('form');
          } else {
            toast.error('檔案辨識失敗', result?.message || '無法解析該檔案');
            setModalOpen(false);
          }
        }
      } catch (error: unknown) {
        if (ocrCancelledRef.current) return;
        toast.error('檔案選取錯誤', error instanceof Error ? error.message : String(error));
      }
      return;
    }

    beginOcrWorkflow('', 'video');
    setModalStage('progress');
    setModalProgress(40);
    setModalStatusText('正在分析檢舉證據檔案...');
    setModalOpen(true);
    setTimeout(() => {
      if (ocrCancelledRef.current) return;
      setOcrResults((prev) =>
        normalizeOcrResult(
          {
            suspect_ids: [],
            map_name: config.default_map || '',
            ocr_map_name: '',
            map_name_source: 'default',
            media_path: '',
            media_type: 'video',
          },
          prev,
          config
        )
      );
      setModalProgress(100);
      setModalStatusText('辨識完成');
      setModalStage('form');
    }, 400);
  };

  const handleRecognizeCurrentFrame = async (
    filePath: string,
    timestampSec: number
  ): Promise<OcrResultData | null> => {
    const recognizeFrame = getReporterBridge()?.capture.recognizeVideoFrame;
    if (!recognizeFrame) {
      toast.warning('目前版本不支援目前畫面辨識', '請重新建置最新版本後再試。');
      return null;
    }

    frameOcrActiveRef.current = true;
    ocrCancelledRef.current = false;
    try {
      const result = await recognizeFrame(filePath, timestampSec);
      if (ocrCancelledRef.current) return null;
      if (result?.status !== 'success') {
        toast.warning('目前畫面辨識失敗', result?.message || '無法辨識暫停畫面');
        return null;
      }
      setOcrResults((previous) =>
        normalizeOcrResult(
          {
            ...result,
            map_name: result.map_name_source === 'ocr' ? result.map_name : previous.map_name,
            map_name_source:
              result.map_name_source === 'ocr' ? 'ocr' : previous.map_name_source || 'default',
            media_path: previous.media_path,
            media_type: previous.media_type,
          },
          previous,
          config
        )
      );
      setModalStatusText(`已辨識目前畫面（${timestampSec.toFixed(2)} 秒）`);
      return result;
    } catch (error: unknown) {
      if (!ocrCancelledRef.current) {
        toast.error('目前畫面辨識異常', error instanceof Error ? error.message : String(error));
      }
      return null;
    } finally {
      frameOcrActiveRef.current = false;
    }
  };

  const handleSubmitReport = async (formData: Record<string, unknown>) => {
    if (isSubmittingReport) return;
    setIsSubmittingReport(true);
    const evidencePath =
      (typeof formData.file_path === 'string' && formData.file_path) ||
      (typeof formData.media_path === 'string' && formData.media_path) ||
      ocrResults.media_path;
    const submittingMessage = '正在送出檢舉…';
    setSubmissionStatus({ step: 'starting', status: 'progress', message: submittingMessage });
    setModalStatusText(submittingMessage);

    const bridge = getReporterBridge();
    if (bridge) {
      try {
        const result = await bridge.reports.submit({
          ...formData,
          file_path: evidencePath,
          upload_destination: config.upload_destination || 'gdrive',
        });
        if (result?.status === 'manual_ready') {
          const record: HistoryRecord = result.record || {
            record_id: result.record_id,
            suspect_id: String(formData.suspect_id || ''),
            server: String(formData.server || ''),
            map_name: String(formData.map_name || ''),
            note: String(formData.note || ''),
            evidence_url: result.evidence_url || '',
            url: result.evidence_url || '',
            media_path: evidencePath,
            submission_state: SUBMISSION_AWAITING_MANUAL,
            submission_mode: 'manual',
          };
          setManualReport(record);
          setActiveHistoryRecord(record);
          setSubmissionStatus(null);
          setModalStatusText('');
          await refreshHistory();
          toast.success('證據已上傳', result.message);
        } else if (result?.status === 'success') {
          setSubmissionStatus({
            step: 'completed',
            status: 'success',
            message: result.message || '檢舉證據已成功提交！',
          });
          toast.success('檢舉證據已成功提交！', result.message || '已自動加入歷史紀錄');
          await refreshHistory();
          setActiveHistoryRecord(null);
          setModalOpen(false);
        } else {
          const message = result?.message || '請確認網路與帳號授權狀態';
          toast.error('送出失敗', message);
          setSubmissionStatus({ step: 'failed', status: 'error', message });
          setModalStatusText(message);
        }
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : '送出發生錯誤，請稍後重試';
        toast.error('送出表單異常', message);
        setSubmissionStatus({ step: 'failed', status: 'error', message });
        setModalStatusText(message);
      } finally {
        setIsSubmittingReport(false);
      }
      return;
    }

    toast.info('瀏覽器預覽模式', '請在桌面應用程式中執行以提交真實檢舉與儲存紀錄');
    setIsSubmittingReport(false);
    setModalOpen(false);
  };

  const handleConfirmManualReport = async (recordId: string) => {
    const bridge = getReporterBridge();
    if (isConfirmingManual || !bridge) return;
    setIsConfirmingManual(true);
    try {
      const result = await bridge.reports.confirmManual(recordId);
      if (result.status !== 'success') {
        toast.error('無法完成確認', result.message);
        return;
      }
      await refreshHistory();
      toast.success('已完成檢舉', result.deleted ? '紀錄已更新，本機證據已清理。' : result.message);
      setManualReport(null);
      setActiveHistoryRecord(null);
      setModalOpen(false);
    } catch (error: unknown) {
      toast.error('無法完成確認', error instanceof Error ? error.message : '請稍後再試。');
    } finally {
      setIsConfirmingManual(false);
    }
  };

  const handleSaveReportDraft = async (formData: Record<string, unknown>) => {
    if (isSavingDraft || isSubmittingReport) return;
    if (modalStageRef.current === 'progress') {
      ocrCancelledRef.current = true;
      void getReporterBridge()
        ?.capture.cancelOcr()
        .catch(() => undefined);
    }
    const bridge = getReporterBridge();
    if (!bridge) {
      toast.info('瀏覽器預覽模式', '請在桌面應用程式中儲存回報紀錄');
      return;
    }

    setIsSavingDraft(true);
    try {
      const result = await bridge.reports.saveDraft(formData);
      if (result.status !== 'success') {
        toast.error('儲存失敗', result.message || '請確認證據檔案後重試');
        return;
      }
      await refreshHistory();
      toast.success('已儲存至回報紀錄', '你可以稍後從「回報紀錄」繼續處理。');
      setModalOpen(false);
      setModalProgress(0);
      setModalStatusText('');
      setSubmissionStatus(null);
      setActiveHistoryRecord(null);
    } catch (error: unknown) {
      toast.error('儲存失敗', error instanceof Error ? error.message : '請確認磁碟空間後重試');
    } finally {
      setIsSavingDraft(false);
    }
  };

  const openDraftForm = (record: HistoryRecord) => {
    if (getSubmissionState(record) !== SUBMISSION_DRAFT || record.media_available === false) return;
    ocrCancelledRef.current = false;
    setActiveHistoryRecord(record);
    setReportWorkflowId((previous) => previous + 1);
    setOcrResults({
      suspect_ids: record.suspect_id ? [record.suspect_id] : [],
      map_name: record.map_name || record.map || '',
      ocr_map_name: '',
      map_name_source: record.map_name || record.map ? 'manual' : undefined,
      media_path: record.media_path || '',
      media_type: record.media_type === 'image' ? 'image' : 'video',
    });
    setSubmissionStatus(null);
    setModalProgress(100);
    setModalStatusText('');
    setModalStage('form');
    setModalOpen(true);
  };

  const handleContinueManual = (record: HistoryRecord) => {
    if (getSubmissionState(record) !== SUBMISSION_AWAITING_MANUAL) return;
    setActiveHistoryRecord(record);
    setManualReport(record);
    setReportWorkflowId((previous) => previous + 1);
    setModalStage('form');
    setModalOpen(true);
  };

  const handleContinueDraft = async (record: HistoryRecord, runRecognition: boolean) => {
    if (!runRecognition) {
      openDraftForm(record);
      return;
    }
    if (getSubmissionState(record) !== SUBMISSION_DRAFT || record.media_available === false) return;

    const mediaPath = record.media_path || '';
    const bridge = getReporterBridge();
    if (!bridge || !mediaPath) {
      toast.warning('無法重新辨識', '已改為載入原本儲存的資料。');
      openDraftForm(record);
      return;
    }

    const savedMap = record.map_name || record.map || '';
    const initialOcr: OcrResultData = {
      suspect_ids: record.suspect_id ? [record.suspect_id] : [],
      map_name: savedMap,
      ocr_map_name: '',
      map_name_source: savedMap ? 'manual' : undefined,
      media_path: mediaPath,
      media_type: record.media_type === 'image' ? 'image' : 'video',
    };
    ocrCancelledRef.current = false;
    setActiveHistoryRecord(record);
    setOcrResults(initialOcr);
    setReportWorkflowId((previous) => previous + 1);
    setSubmissionStatus(null);
    setModalProgress(25);
    setModalStatusText('正在依目前設定重新辨識證據...');
    setModalStage('progress');
    setModalOpen(true);

    try {
      const result = await bridge.capture.processImportedFile(mediaPath);
      if (ocrCancelledRef.current) return;
      if (result?.status !== 'success') {
        toast.warning('重新辨識未完成', result?.message || '已載入原本儲存的資料。');
        openDraftForm(record);
        return;
      }

      const normalized = normalizeOcrResult(result, initialOcr, config);
      const recognizedId =
        config.ocr_autofill_id !== false
          ? normalized.suspect_ids.find((id) => !config.whitelist.includes(id)) ||
            normalized.suspect_ids[0] ||
            record.suspect_id ||
            ''
          : record.suspect_id || '';
      const hasRecognizedMap =
        config.ocr_autofill_map !== false &&
        (normalized.map_name_source === 'ocr' || Boolean(normalized.ocr_map_name));
      const recognizedMap = hasRecognizedMap ? normalized.map_name : savedMap;
      const recognizedRecord: HistoryRecord = {
        ...record,
        suspect_id: recognizedId,
        map: recognizedMap,
        map_name: recognizedMap,
      };

      setActiveHistoryRecord(recognizedRecord);
      setOcrResults({
        ...normalized,
        suspect_ids: recognizedId
          ? [recognizedId, ...normalized.suspect_ids.filter((id) => id !== recognizedId)]
          : [],
        map_name: recognizedMap,
      });
      setReportWorkflowId((previous) => previous + 1);
      setModalProgress(100);
      setModalStatusText('辨識完成');
      setModalStage('form');
    } catch (error: unknown) {
      if (ocrCancelledRef.current) return;
      toast.warning(
        '重新辨識失敗',
        error instanceof Error ? error.message : '已載入原本儲存的資料。'
      );
      openDraftForm(record);
    }
  };

  const handleSkipOcrAndClose = handleSkipOcr;

  const handleCloseReport = () => {
    if (modalStageRef.current === 'progress' || frameOcrActiveRef.current) {
      ocrCancelledRef.current = true;
      void getReporterBridge()
        ?.capture.cancelOcr()
        .catch(() => undefined);
    }
    setModalOpen(false);
    setModalProgress(0);
    setModalStatusText('');
    setSubmissionStatus(null);
    setActiveHistoryRecord(null);
    setManualReport(null);
  };

  const handleStopReplay = async () => {
    await getReporterBridge()?.capture.stopReplay();
    setStatusState('idle');
    setReplayTime(0);
    toast.info('已停止循環錄影');
  };

  const restoreReplayState = useCallback((state?: string, duration?: number) => {
    if (state && ['warming', 'ready', 'saving'].includes(state)) {
      setStatusState('replaying');
      setReplayTime(Math.floor(duration || 0));
    }
  }, []);

  return {
    statusState,
    recordingTime,
    countdown,
    countdownTotal,
    countdownFraction,
    recordingFraction,
    replayTime,
    modalOpen,
    modalStage,
    modalProgress,
    modalStatusText,
    isSubmittingReport,
    isSavingDraft,
    submissionStatus,
    isResetting,
    reportWorkflowId,
    ocrResults,
    activeHistoryRecord,
    manualReport,
    isConfirmingManual,
    handleCaptureScreenshot,
    handleCancelRecording,
    handleRecordVideo,
    handleToggleReplay,
    handleSkipOcr: handleSkipOcrAndClose,
    handleSaveReplay,
    handleSelectFile,
    handleRecognizeCurrentFrame,
    handleSubmitReport,
    handleConfirmManualReport,
    handleSaveReportDraft,
    handleContinueDraft,
    handleContinueManual,
    handleCloseReport,
    handleStopReplay,
    restoreReplayState,
  };
}
