import { lazy, Suspense, useState, useEffect, useCallback, useRef } from 'react';
import Header from './components/Header';
import AlertBanner from './components/AlertBanner';
import ActionCards from './components/ActionCards';
import StatusBar from './components/StatusBar';
import WindowResizeHandles from './components/WindowResizeHandles';
import { useToast, usePyWebViewEvents, useAppConfig } from './hooks';
import {
  WindowItem,
  AudioDeviceItem,
  HistoryRecord,
  OcrResultData,
  QuickLinkItem,
  ViewType,
  StatusState,
  SubmissionStatusData,
  SanctionSyncStatus,
  UpdateStatus,
} from './types';
import { normalizeSafeHttpsUrl } from './utils';
import './styles/app.css';

import { choosePreferredWindow, normalizeOcrResult } from './utils/appHelpers';

const SettingsView = lazy(() => import('./components/SettingsView'));
const HistoryView = lazy(() => import('./components/HistoryView'));
const ReportFlowModal = lazy(() => import('./components/ReportFlowModal'));
const QuickLinkModal = lazy(() => import('./components/QuickLinkModal'));
const QuickSettings = lazy(() => import('./components/QuickSettings'));
const QuickLinks = lazy(() => import('./components/QuickLinks'));

export default function App() {
  const [currentView, setCurrentView] = useState<ViewType>('home');
  const [settingsTab, setSettingsTab] = useState('general');
  const { toast } = useToast();
  const {
    config,
    setConfig,
    updateConfig,
    updateConfigBatch,
    isDevMode,
    saveError,
    clearSaveError,
  } = useAppConfig();
  const [gdriveAuthenticated, setGdriveAuthenticated] = useState<boolean | null>(null);
  const [isAuthenticatingDrive, setIsAuthenticatingDrive] = useState(false);

  const [windows, setWindows] = useState<WindowItem[]>([
    { title: '新楓之谷：經典版', width: 1920, height: 1080 },
  ]);

  const [audioDevices, setAudioDevices] = useState<AudioDeviceItem[]>([
    { id: '', name: '系統預設' },
  ]);

  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [sanctionSyncStatus, setSanctionSyncStatus] = useState<SanctionSyncStatus | null>(null);
  const [isCheckingSanctions, setIsCheckingSanctions] = useState<boolean>(false);
  const [lastCompleteSyncAt, setLastCompleteSyncAt] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState<boolean>(true);
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus | null>(null);
  const manualUpdateCheckRef = useRef(false);

  // Status & modal states
  const [statusState, setStatusState] = useState<StatusState>('idle');
  const [recordingTime, setRecordingTime] = useState(0);
  const [countdown, setCountdown] = useState(0);
  const [countdownTotal, setCountdownTotal] = useState(3);
  const [countdownFraction, setCountdownFraction] = useState<number | undefined>(undefined);
  const [recordingFraction, setRecordingFraction] = useState<number | undefined>(undefined);
  const [replayTime, setReplayTime] = useState(0);
  const animFrameRef = useRef<number | null>(null);

  // Modal State
  const [modalOpen, setModalOpen] = useState(false);
  const [modalStage, setModalStage] = useState<'progress' | 'form'>('progress');
  const modalStageRef = useRef(modalStage);
  modalStageRef.current = modalStage;
  const [modalProgress, setModalProgress] = useState(0);
  const [modalStatusText, setModalStatusText] = useState('');
  const [isSubmittingReport, setIsSubmittingReport] = useState(false);
  const [submissionStatus, setSubmissionStatus] = useState<SubmissionStatusData | null>(null);
  const [isResetting, setIsResetting] = useState(false);
  const [ocrResults, setOcrResults] = useState<OcrResultData>({
    suspect_ids: [],
    map_name: '',
    media_path: '',
    media_type: 'video',
  });

  // Quick Link In-place Modal State
  const [quickLinkModalOpen, setQuickLinkModalOpen] = useState(false);
  const [editingQuickLink, setEditingQuickLink] = useState<QuickLinkItem | null>(null);

  const cancelAnim = () => {
    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
  };

  // PyWebView Bridge Event Subscriptions
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
      cancelAnim();
      setStatusState('idle');
      setRecordingTime(0);
      setCountdown(0);
      setCountdownFraction(undefined);
      setRecordingFraction(undefined);
      setSubmissionStatus(null);
      if (modalStageRef.current !== 'form') {
        setModalStage('progress');
        setModalProgress(35);
        setModalStatusText('錄影已完成，正在解析關鍵影格...');
      }
      if (data?.file_path) {
        setOcrResults((prev) => ({
          ...prev,
          media_path: data.file_path || prev.media_path,
          media_type: 'video',
        }));
      }
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
      setSubmissionStatus(null);
      if (modalStageRef.current !== 'form') {
        setModalStage('progress');
        setModalProgress(40);
        setModalStatusText('已儲存循環錄影，正在解析關鍵影格...');
      }
      if (data?.file_path) {
        setOcrResults((prev) => ({
          ...prev,
          media_path: data.file_path || prev.media_path,
          media_type: 'video',
        }));
      }
      setModalOpen(true);
    },
    REPLAY_ERROR: (data: { message: string }) => {
      toast.error('循環錄影錯誤', data.message);
      setModalOpen(false);
    },
    OCR_STATUS: (data: { status: string; percent: number; step?: string }) => {
      if (modalStageRef.current !== 'form') {
        setModalProgress(data.percent || 50);
        if (data.status) {
          setModalStatusText(data.status);
        }
      }
    },
    OCR_RESULT: (data: OcrResultData) => {
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
    SANCTION_SYNC_STARTED: (data: any) => {
      setSanctionSyncStatus(data);
      setIsCheckingSanctions(true);
    },
    SANCTION_SYNC_PROGRESS: (data: any) => {
      setSanctionSyncStatus(data);
      setIsCheckingSanctions(true);
    },
    SANCTION_SYNC_COMPLETED: (data: any) => {
      const summary = data?.summary;
      const historyList = data?.history;
      setIsCheckingSanctions(false);
      setSanctionSyncStatus(null);
      if (Array.isArray(historyList)) {
        setHistory(historyList);
      }
      const syncAt =
        summary?.last_complete_sync_at ||
        data?.last_complete_sync_at ||
        data?.summary?.last_complete_sync_at;
      if (syncAt) {
        setLastCompleteSyncAt(syncAt);
        updateConfig('last_complete_sync_at', syncAt);
      }

      // Toast summary decisions
      const newlyBanned = summary?.newly_banned_count || 0;
      const changedToUnbanned = summary?.changed_to_unbanned_count || 0;
      const checkedCount = summary?.checked_record_count || 0;

      if (sanctionSyncStatus?.trigger === 'manual') {
        toast.success(
          '官方處分狀態檢查完成',
          `已檢查 ${checkedCount} 筆紀錄，新增 ${newlyBanned} 筆封鎖，解除 ${changedToUnbanned} 筆`
        );
      } else if (newlyBanned > 0) {
        toast.info('官方處分名單已更新', `新增 ${newlyBanned} 筆封鎖結果`);
      }
    },
    SANCTION_SYNC_FAILED: (data: any) => {
      setIsCheckingSanctions(false);
      setSanctionSyncStatus(null);
      if (Array.isArray(data?.history)) {
        setHistory(data.history);
      }
      toast.warning('官方處分狀態同步未完成', data?.message || '部分公告未能成功下載，已保留既有結果');
    },
    UPDATE_STATUS: (data: UpdateStatus) => {
      if (!data || typeof data.state !== 'string') return;
      setUpdateStatus(data);
      if (!manualUpdateCheckRef.current) return;
      if (data.state === 'checking') return;
      if (data.state === 'up_to_date') {
        toast.success('目前已是最新版');
        manualUpdateCheckRef.current = false;
      } else if (data.state === 'available') {
        toast.info('發現可用更新', data.target_version ? `可更新至 v${data.target_version}` : undefined);
        manualUpdateCheckRef.current = false;
      } else if (data.state === 'error' || data.state === 'insufficient_space') {
        toast.warning('更新檢查未完成', data.error_message || '請稍後再試');
        manualUpdateCheckRef.current = false;
      }
    },
  });

  // Initialize PyWebView bridge API connection
  const initPyWebView = useCallback(async () => {
    if (window.pywebview && window.pywebview.api) {
      try {
        const initData = await window.pywebview.api.get_initial_data();
        if (initData) {
          const initialWindows = initData.windows || [];
          const initialSelectedTitle = choosePreferredWindow(
            initialWindows,
            initData.config?.selected_window_title
          );
          if (initData.config || initialSelectedTitle) {
            setConfig((prev) => ({
              ...prev,
              ...initData.config,
              ...(initialSelectedTitle ? { selected_window_title: initialSelectedTitle } : {}),
            }));
          }
          if (initialWindows.length > 0) setWindows(initialWindows);
          if (initData.audio_devices && initData.audio_devices.length > 0)
            setAudioDevices(initData.audio_devices);
          if (initData.history) setHistory(initData.history);
          if (initData.update_status) setUpdateStatus(initData.update_status);
          setGdriveAuthenticated(Boolean(initData.gdrive_authenticated));
          if (initData.sanction_sync_status) {
            setSanctionSyncStatus(initData.sanction_sync_status);
            setIsCheckingSanctions(Boolean(initData.sanction_sync_status.running));
          }
          if (initData.last_complete_sync_at) {
            setLastCompleteSyncAt(initData.last_complete_sync_at);
          }
          if (
            initData.replay_state &&
            ['warming', 'ready', 'saving'].includes(initData.replay_state)
          ) {
            setStatusState('replaying');
            setReplayTime(Math.floor(initData.replay_duration || 0));
          }

          // Trigger startup sanction sync once if applicable
          if (window.pywebview?.api?.start_sanction_sync) {
            window.pywebview.api
              .start_sanction_sync('startup')
              .then((res) => {
                if (res?.started && res?.status) {
                  setSanctionSyncStatus(res.status);
                  setIsCheckingSanctions(true);
                }
              })
              .catch(() => {
                // Ignore startup sync initiation failures
              });
          }
        }
      } catch (e) {
        console.warn('PyWebView API initialization error:', e);
      } finally {
        setIsInitializing(false);
      }
    } else {
      setTimeout(() => setIsInitializing(false), 200);
    }
  }, [setConfig]);

  useEffect(() => {
    if (saveError) {
      toast.error('設定儲存失敗', saveError);
      clearSaveError();
    }
  }, [saveError, clearSaveError, toast]);

  useEffect(() => {
    if (window.pywebview) {
      initPyWebView();
    } else {
      window.addEventListener('pywebviewready', initPyWebView);
    }
    return () => window.removeEventListener('pywebviewready', initPyWebView);
  }, [initPyWebView]);

  useEffect(() => {
    if (currentView === 'history' && window.pywebview?.api?.get_history) {
      window.pywebview.api
        .get_history()
        .then((records) => {
          if (Array.isArray(records)) {
            setHistory(records);
          }
        })
        .catch((e) => {
          console.warn('Failed to refresh history on entering history view:', e);
        });
    }
  }, [currentView]);

  // Action Triggers
  const handleCaptureScreenshot = async () => {
    setSubmissionStatus(null);
    setModalStage('progress');
    setModalProgress(30);
    setModalStatusText('正在截圖並進行辨識...');
    setModalOpen(true);

    if (window.pywebview && window.pywebview.api) {
      try {
        const result = await window.pywebview.api.capture_screenshot('window');
        if (result && result.status === 'success') {
          setOcrResults((prev) => normalizeOcrResult(result, prev, config));
          setModalProgress(100);
          setModalStatusText('辨識完成');
          setModalStage('form');
          return;
        } else if (result && result.status === 'error') {
          toast.error('截圖失敗', result.message || '無法截取遊戲視窗');
          setModalOpen(false);
          return;
        }
      } catch (e: any) {
        toast.error('截圖辨識發生異常', e?.message || String(e));
        setModalOpen(false);
        return;
      }
    }

    // Browser fallback when not in pywebview
    setTimeout(() => {
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
      const now = performance.now();
      const elapsed = now - startTime;

      if (cdSec > 0 && elapsed < cdMs) {
        // Countdown phase: 100% -> 0%
        const remainingCd = cdMs - elapsed;
        const cdFrac = Math.max(0, Math.min(1, remainingCd / cdMs));
        const cdInt = Math.ceil(remainingCd / 1000);
        setCountdown(cdInt);
        setCountdownTotal(cdSec);
        setCountdownFraction(cdFrac);
        setRecordingFraction(0);
        setRecordingTime(0);
        animFrameRef.current = requestAnimationFrame(tick);
      } else {
        // Recording phase: 0% -> 100%
        const recElapsed = cdSec > 0 ? elapsed - cdMs : elapsed;
        const recFrac = Math.max(0, Math.min(1, recElapsed / recMs));
        const recSecInt = Math.min(recSec, Math.floor(recElapsed / 1000));
        setCountdown(0);
        setCountdownFraction(0);
        setRecordingTime((prev) => Math.max(prev, recSecInt));
        setRecordingFraction((prev) => (prev !== undefined ? Math.max(prev, recFrac) : recFrac));

        if (recElapsed < recMs) {
          animFrameRef.current = requestAnimationFrame(tick);
        } else {
          // Recording complete (100% reached!)
          setRecordingFraction(1.0);
          setRecordingTime(recSec);
          animFrameRef.current = null;
          if (!window.pywebview || !window.pywebview.api) {
            setTimeout(() => {
              setStatusState('idle');
              setRecordingFraction(undefined);
              setCountdownFraction(undefined);
              setModalStage('progress');
              setModalProgress(50);
              setModalOpen(true);
              setTimeout(() => {
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
        }
      }
    };

    animFrameRef.current = requestAnimationFrame(tick);
  };

  const handleCancelRecording = async () => {
    if (isResetting) return;
    setIsResetting(true);
    cancelAnim();
    try {
      if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.cancel_recording();
      }
    } catch {
      // ignore
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

    setIsResetting(true);
    if (window.pywebview && window.pywebview.api) {
      try {
        await window.pywebview.api.start_recording(
          config.record_duration_sec,
          config.record_fps,
          config.record_countdown_sec || 0,
          config.record_audio !== false,
          config.audio_output_device_id || '',
          config.audio_capture_mode
        );
      } catch (e: any) {
        cancelAnim();
        toast.error('錄影啟動失敗', e?.message || String(e));
        setStatusState('idle');
        setCountdown(0);
        setCountdownFraction(undefined);
        setRecordingFraction(undefined);
      } finally {
        setTimeout(() => setIsResetting(false), 300);
      }
    } else {
      // Mock standalone web mode
      setStatusState('recording');
      startRealtimeProgress(cd, dur);
      setTimeout(() => setIsResetting(false), 300);
    }
  };

  const handleToggleReplay = async () => {
    if (statusState === 'replaying') {
      if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.stop_replay();
      }
      setStatusState('idle');
      toast.info('已停止循環錄影');
    } else {
      if (window.pywebview && window.pywebview.api) {
        const ok = await window.pywebview.api.start_replay(
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
    }
  };

  const handleSkipOcr = () => {
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
    setSubmissionStatus(null);
    if (window.pywebview && window.pywebview.api) {
      try {
        const ok = await window.pywebview.api.save_replay();
        if (!ok) {
          toast.warning('循環錄影片段尚未就緒', '請稍候幾秒待緩衝累積後再儲存');
        } else {
          setModalStage('progress');
          setModalProgress(35);
          setModalStatusText('已儲存循環錄影，正在解析關鍵影格...');
          setModalOpen(true);
        }
      } catch (e: any) {
        toast.error('儲存循環錄影失敗', e?.message || String(e));
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
    if (window.pywebview && window.pywebview.api) {
      try {
        const filePath = await window.pywebview.api.select_local_file();
        if (filePath) {
          setSubmissionStatus(null);
          setModalStage('progress');
          setModalProgress(25);
          setModalStatusText('已選取檢舉證據檔案，正在分析畫面...');
          setModalOpen(true);
          const res = await window.pywebview.api.process_imported_file(filePath);
          if (res && res.status === 'success') {
            setOcrResults((prev) => normalizeOcrResult(res, prev, config));
            setModalProgress(100);
            setModalStatusText('辨識完成');
            setModalStage('form');
          } else {
            toast.error('檔案辨識失敗', res?.message || '無法解析該檔案');
            setModalOpen(false);
          }
        }
      } catch (e: any) {
        toast.error('檔案選取錯誤', e?.message || String(e));
      }
    } else {
      setModalStage('progress');
      setModalProgress(40);
      setModalStatusText('正在分析檢舉證據檔案...');
      setModalOpen(true);
      setTimeout(() => {
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
    }
  };

  const handleOpenUrl = (url: string) => {
    if (!url) return;
    const targetUrl = normalizeSafeHttpsUrl(url);
    if (!targetUrl) {
      toast.warning('無法開啟連結', '只允許安全的 HTTPS 網址。');
      return;
    }
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.open_external_url(targetUrl);
    } else {
      window.open(targetUrl, '_blank', 'noopener,noreferrer');
    }
  };

  const handleClearHistory = async (): Promise<boolean> => {
    if (!window.pywebview?.api?.clear_history) {
      toast.warning('目前無法清空歷史紀錄', '請使用桌面版程式操作。');
      return false;
    }

    try {
      const cleared = await window.pywebview.api.clear_history();
      if (!cleared) {
        toast.error('清空歷史紀錄失敗', '本機歷史檔案沒有成功更新。');
        return false;
      }

      const initData = await window.pywebview.api.get_initial_data();
      setHistory(initData?.history || []);
      toast.success('歷史紀錄已清空');
      return true;
    } catch (error: unknown) {
      toast.error('清空歷史紀錄失敗', error instanceof Error ? error.message : String(error));
      return false;
    }
  };

  const handleCheckSanctions = async (): Promise<void> => {
    if (isCheckingSanctions) return;
    setIsCheckingSanctions(true);

    if (window.pywebview?.api?.start_sanction_sync) {
      try {
        const res = await window.pywebview.api.start_sanction_sync('manual');
        if (res) {
          if (res.status?.last_complete_sync_at) {
            setLastCompleteSyncAt(res.status.last_complete_sync_at);
            updateConfig('last_complete_sync_at', res.status.last_complete_sync_at);
          }
          if (res.started && res.status) {
            setSanctionSyncStatus(res.status);
          } else if (!res.started) {
            setIsCheckingSanctions(false);
            setSanctionSyncStatus(null);
            if (res.reason === 'fresh') {
              toast.info('官方處分紀錄已是最新', '不久前已完成完整同步檢查。');
            }
          }
        }
      } catch (err: unknown) {
        setIsCheckingSanctions(false);
        toast.error('啟動官方處分狀態檢查失敗', err instanceof Error ? err.message : String(err));
      }
    } else {
      // Mock flow for browser preview
      setSanctionSyncStatus({
        running: true,
        trigger: 'manual',
        phase: 'fetching',
        current: 1,
        total: 2,
        message: '正在檢查官方處分公告（測試）…',
      });
      setTimeout(() => {
        setIsCheckingSanctions(false);
        setSanctionSyncStatus(null);
        const mockNow = new Date().toISOString();
        setLastCompleteSyncAt(mockNow);
        updateConfig('last_complete_sync_at', mockNow);
        toast.success('官方處分狀態檢查完成（測試）', '已比對最新官方處分公告');
      }, 1200);
    }
  };

  const handleCheckForUpdates = async (force = true) => {
    if (!window.pywebview?.api?.check_for_updates) {
      toast.warning('目前環境無法檢查更新', '請使用 Windows 發行版執行此功能');
      return;
    }
    manualUpdateCheckRef.current = true;
    toast.info('正在檢查更新…');
    await window.pywebview.api.check_for_updates(force);
  };

  const handleStartUpdateDownload = async () => {
    if (!window.pywebview?.api?.start_update_download) return;
    await window.pywebview.api.start_update_download();
  };

  const handleCancelUpdateDownload = async () => {
    if (!window.pywebview?.api?.cancel_update_download) return;
    await window.pywebview.api.cancel_update_download();
  };

  const handleRestartAndApplyUpdate = async () => {
    if (!window.pywebview?.api?.restart_and_apply_update) return;
    await window.pywebview.api.restart_and_apply_update();
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
    if (window.pywebview && window.pywebview.api) {
      try {
        const res = await window.pywebview.api.submit_report({
          ...formData,
          file_path: evidencePath,
          upload_destination: config.upload_destination || 'gdrive',
        });
        if (res && res.status === 'success') {
          setSubmissionStatus({
            step: 'completed',
            status: 'success',
            message: res.message || '檢舉證據已成功提交！',
          });
          toast.success('檢舉證據已成功提交！', res.message || '已自動加入歷史紀錄');
          const initData = await window.pywebview.api.get_initial_data();
          if (initData && initData.history) setHistory(initData.history);
          setModalOpen(false);
        } else {
          const message = res?.message || '請確認網路與帳號授權狀態';
          toast.error('送出失敗', message);
          setSubmissionStatus({ step: 'failed', status: 'error', message });
          setModalStatusText(message);
        }
      } catch (e: any) {
        const message = e?.message || '送出發生錯誤，請稍後重試';
        toast.error('送出表單異常', message);
        setSubmissionStatus({ step: 'failed', status: 'error', message });
        setModalStatusText(message);
      } finally {
        setIsSubmittingReport(false);
      }
    } else {
      toast.info('瀏覽器預覽模式', '請在桌面應用程式中執行以提交真實檢舉與儲存紀錄');
      setIsSubmittingReport(false);
      setModalOpen(false);
    }
  };

  const handleRefreshWindows = useCallback(
    async (silent = false) => {
      if (window.pywebview && window.pywebview.api) {
        try {
          const list = await window.pywebview.api.get_windows();
          if (list) {
            setWindows(list);
            const preferredTitle = choosePreferredWindow(list, config.selected_window_title);
            if (preferredTitle && preferredTitle !== config.selected_window_title) {
              await updateConfig('selected_window_title', preferredTitle);
            }
          }
          if (!silent) {
            toast.info('已重新整理視窗清單', `找到 ${list?.length || 0} 個可選視窗`);
          }
        } catch {
          if (!silent) toast.error('重新整理視窗失敗');
        }
      } else {
        if (!silent) toast.info('已重新整理視窗清單');
      }
    },
    [config.selected_window_title, updateConfig, toast]
  );

  const handleRefreshAudio = useCallback(
    async (silent = false) => {
      if (window.pywebview && window.pywebview.api) {
        try {
          const list = await window.pywebview.api.get_audio_devices();
          if (list) setAudioDevices(list);
          if (!silent) toast.info('已重新整理音訊裝置清單');
        } catch {
          if (!silent) toast.error('重新整理音訊裝置失敗');
        }
      } else {
        if (!silent) toast.info('已重新整理音訊裝置清單');
      }
    },
    [toast]
  );

  // Silently refresh windows and audio devices when application gains focus
  useEffect(() => {
    const handleFocus = () => {
      handleRefreshWindows(true);
      handleRefreshAudio(true);
    };
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, [handleRefreshWindows, handleRefreshAudio]);

  const handleAuthenticateDrive = async () => {
    if (isAuthenticatingDrive) return;
    if (!(window.pywebview && window.pywebview.api)) {
      toast.info('正在連線登入 Google 帳號（測試）...');
      return;
    }

    setIsAuthenticatingDrive(true);
    toast.info('正在開啟系統瀏覽器進行 Google 授權驗證...');
    try {
      const res = await window.pywebview.api.authenticate_gdrive();
      let authenticated = Boolean(res?.is_authenticated);
      try {
        authenticated = await window.pywebview.api.check_gdrive_auth();
      } catch {
        // Keep the authoritative value returned by authenticate_gdrive when the
        // follow-up check is unavailable.
      }
      setGdriveAuthenticated(authenticated);
      if (authenticated) {
        toast.success('Google 帳號登入成功！');
      } else {
        toast.error('Google 帳號登入失敗', res?.message || '尚未取得有效登入狀態');
      }
    } catch (e: any) {
      setGdriveAuthenticated(false);
      toast.error('Google 帳號登入異常', e?.message || String(e));
    } finally {
      setIsAuthenticatingDrive(false);
    }
  };

  const handleOpenDriveFolder = async () => {
    if (window.pywebview && window.pywebview.api) {
      const url = await window.pywebview.api.get_gdrive_folder_url(config.gdrive_folder_name);
      window.pywebview.api.open_external_url(url);
    } else {
      window.open('https://drive.google.com/', '_blank');
    }
  };

  const handleClearRecordings = async () => {
    if (window.pywebview && window.pywebview.api) {
      const res = await window.pywebview.api.clear_all_recordings();
      if (res && res.success) {
        toast.success('本機錄影清理完成', `已刪除 ${res.count} 個暫存檔案`);
      }
    }
  };

  const handleSaveQuickLink = (linkData: QuickLinkItem) => {
    const existing = config.quick_links || [];
    let updated: QuickLinkItem[];
    if (editingQuickLink) {
      updated = existing.map((l) => (l.id === linkData.id ? linkData : l));
    } else {
      updated = [...existing, linkData];
    }
    updateConfig('quick_links', updated);
    setQuickLinkModalOpen(false);
    setEditingQuickLink(null);
    toast.success(editingQuickLink ? '快捷連結已更新' : '已新增快捷連結');
  };

  const handleStopReplay = async () => {
    if (window.pywebview && window.pywebview.api) {
      await window.pywebview.api.stop_replay();
    }
    setStatusState('idle');
    setReplayTime(0);
    toast.info('已停止循環錄影');
  };

  const selectedWindow = windows.find((w) => w.title === config.selected_window_title);
  const currentWindowSize =
    selectedWindow && selectedWindow.width > 0
      ? `${selectedWindow.width} × ${selectedWindow.height}`
      : '1920 × 1080';
  const currentAudioDevice =
    config.audio_capture_mode === 'off'
      ? '不錄音'
      : config.audio_capture_mode === 'process'
        ? '僅遊戲聲音'
        : audioDevices.find((a) => a.id === config.audio_output_device_id)?.name || '系統預設';
  const currentQuality = `${selectedWindow ? `${selectedWindow.height}p` : '1080p'} ${config.record_fps || 30} FPS`;
  const activeTotalCountdown = countdownTotal || config.record_countdown_sec || 3;

  const alertUnconfigured =
    (config.upload_destination === 'discord' && !config.discord_webhook_url) ||
    (config.upload_destination === 'gdrive' && gdriveAuthenticated === false);
  const configurationWarning =
    config.upload_destination === 'gdrive'
      ? '尚未登入 Google 帳號，檢舉證據目前無法上傳。'
      : '尚未設定 Discord 頻道連結，檢舉證據目前無法上傳。';

  return (
    <div className="app-container">
      <WindowResizeHandles />
      <Header
        currentView={currentView}
        setCurrentView={setCurrentView}
        alertUnconfigured={alertUnconfigured}
        isDevMode={isDevMode}
        theme={typeof config.theme === 'string' ? config.theme : undefined}
        onUpdateTheme={(nextTheme) => updateConfig('theme', nextTheme)}
        updateStatus={updateStatus}
        updateBusy={statusState !== 'idle' || isSubmittingReport || modalOpen}
        onStartUpdateDownload={handleStartUpdateDownload}
        onRestartAndApplyUpdate={handleRestartAndApplyUpdate}
        onCancelUpdateDownload={handleCancelUpdateDownload}
        onOpenUpdateDetails={() => {
          setCurrentView('settings');
          setSettingsTab('about');
        }}
      />

      <main className="main-content">
        {alertUnconfigured && (
          <AlertBanner
            message={configurationWarning}
            onStartSettings={() => setCurrentView('settings')}
          />
        )}

        {currentView === 'home' && (
          <div className="home-view">
            <section className="home-actions-area" aria-label="蒐證與檢舉操作">
              <ActionCards
                onCaptureScreenshot={handleCaptureScreenshot}
                onRecordVideo={handleRecordVideo}
                onToggleReplay={handleToggleReplay}
                onSelectFile={handleSelectFile}
                isReplaying={statusState === 'replaying'}
                isRecording={statusState === 'recording' || countdown > 0}
                recordingLabel={countdown > 0 ? `倒數 ${countdown}s` : `錄影中 ${recordingTime}s`}
                countdown={countdown}
                totalCountdown={activeTotalCountdown}
                countdownFraction={countdownFraction}
                recordingTime={recordingTime}
                totalRecordingDuration={config.record_duration_sec || 8}
                recordingFraction={recordingFraction}
                disabled={isResetting}
              />
            </section>

            <section className="home-settings-area" aria-label="快速設定">
              <Suspense
                fallback={
                  <div className="route-loading" role="status">
                    載入快速設定…
                  </div>
                }
              >
                <QuickSettings
                  config={config}
                  windows={windows}
                  audioDevices={audioDevices}
                  isInitializing={isInitializing}
                  onUpdateConfig={updateConfig}
                  onUpdateConfigBatch={updateConfigBatch}
                  onRefreshWindows={handleRefreshWindows}
                  onRefreshAudio={handleRefreshAudio}
                  onOpenSettings={() => {
                    setSettingsTab('recording');
                    setCurrentView('settings');
                  }}
                />
              </Suspense>
            </section>

            <section className="home-links-area" aria-label="快捷連結">
              <Suspense
                fallback={
                  <div className="route-loading" role="status">
                    載入快捷連結…
                  </div>
                }
              >
                <QuickLinks
                  quickLinks={config.quick_links}
                  onOpenLink={handleOpenUrl}
                  onManageLinks={() => {
                    setSettingsTab('quicklinks');
                    setCurrentView('settings');
                  }}
                  onAddCustomLink={() => {
                    setEditingQuickLink(null);
                    setQuickLinkModalOpen(true);
                  }}
                />
              </Suspense>
            </section>
          </div>
        )}

        {currentView === 'settings' && (
          <Suspense
            fallback={
              <div className="route-loading" role="status">
                載入設定…
              </div>
            }
          >
            <SettingsView
              config={config}
              windows={windows}
              audioDevices={audioDevices}
              initialTab={settingsTab}
              gdriveAuthenticated={gdriveAuthenticated}
              gdriveAuthLoading={isAuthenticatingDrive}
              onUpdateConfig={updateConfig}
              onUpdateConfigBatch={updateConfigBatch}
              onBack={() => setCurrentView('home')}
              onOpenDriveFolder={handleOpenDriveFolder}
              onAuthenticateDrive={handleAuthenticateDrive}
              onRefreshWindows={handleRefreshWindows}
              onRefreshAudio={handleRefreshAudio}
              onClearRecordings={handleClearRecordings}
              updateStatus={updateStatus}
              onCheckForUpdates={() => handleCheckForUpdates(true)}
              onStartUpdateDownload={handleStartUpdateDownload}
              onCancelUpdateDownload={handleCancelUpdateDownload}
              onRestartAndApplyUpdate={handleRestartAndApplyUpdate}
              updateBusy={statusState !== 'idle' || isSubmittingReport || modalOpen}
            />
          </Suspense>
        )}

        {currentView === 'history' && (
          /* Keep backend history authoritative for both the history view and form suggestions. */
          <Suspense
            fallback={
              <div className="route-loading" role="status">
                載入歷史紀錄…
              </div>
            }
          >
            <HistoryView
              history={history}
              compactLayout={
                typeof config.history_compact_layout === 'boolean'
                  ? config.history_compact_layout
                  : false
              }
              onUpdateCompactLayout={(compact) => updateConfig('history_compact_layout', compact)}
              pageSize={
                typeof config.history_page_size === 'number' ? config.history_page_size : 15
              }
              onUpdatePageSize={(size) => updateConfig('history_page_size', size)}
              onBack={() => setCurrentView('home')}
              onClearHistory={handleClearHistory}
              onOpenUrl={handleOpenUrl}
              onCheckSanctions={handleCheckSanctions}
              isCheckingSanctions={isCheckingSanctions}
              sanctionSyncStatus={sanctionSyncStatus}
              lastCompleteSyncAt={
                lastCompleteSyncAt ||
                (typeof config.last_complete_sync_at === 'string'
                  ? config.last_complete_sync_at
                  : null)
              }
            />
          </Suspense>
        )}
      </main>

      <StatusBar
        statusState={statusState}
        recordingTime={recordingTime}
        totalRecordingDuration={config.record_duration_sec || 8}
        recordingFraction={recordingFraction}
        countdown={countdown}
        totalCountdown={activeTotalCountdown}
        countdownFraction={countdownFraction}
        replayTime={replayTime}
        maxReplayBuffer={config.replay_buffer_sec || 30}
        targetWindowTitle={config.selected_window_title || '新楓之谷：經典版'}
        windowSize={currentWindowSize}
        audioDevice={currentAudioDevice}
        quality={currentQuality}
        disabled={isResetting}
        onCancelRecording={handleCancelRecording}
        onStopReplay={handleStopReplay}
        onSaveReplay={handleSaveReplay}
      />

      {modalOpen && (
        <Suspense fallback={null}>
          <ReportFlowModal
            stage={modalStage}
            progressPercent={modalProgress}
            progressStatus={modalStatusText}
            isSubmitting={isSubmittingReport}
            submissionStatus={submissionStatus}
            ocrResults={ocrResults}
            config={config}
            history={history}
            onClose={() => {
              setModalOpen(false);
              setModalProgress(0);
              setModalStatusText('');
              setSubmissionStatus(null);
            }}
            onSkipOcr={handleSkipOcr}
            onSubmitReport={handleSubmitReport}
            onOpenFilePath={(p) => {
              if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.open_media_file(p);
              }
            }}
            onOpenFileLocation={(p) => {
              if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.open_file_location(p);
              }
            }}
            onUpdateWhitelist={(newWhitelist) => {
              updateConfig('whitelist', newWhitelist);
              toast.success('略過名單已更新');
            }}
          />
        </Suspense>
      )}

      {quickLinkModalOpen && (
        <Suspense fallback={null}>
          <QuickLinkModal
            linkToEdit={editingQuickLink}
            onSave={handleSaveQuickLink}
            onClose={() => {
              setQuickLinkModalOpen(false);
              setEditingQuickLink(null);
            }}
          />
        </Suspense>
      )}
    </div>
  );
}
