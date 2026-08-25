import { lazy, Suspense, useState, useEffect, useCallback, useRef, type MouseEvent } from 'react';
import Header from './components/Header';
import AlertBanner from './components/AlertBanner';
import ActionCards from './components/ActionCards';
import StatusBar from './components/StatusBar';
import WindowResizeHandles from './components/WindowResizeHandles';
import WindowControls from './components/WindowControls';
import OnboardingFlow from './components/OnboardingFlow';
import { getReporterBridge } from './bridge/reporterBridge';
import { useToast, usePyWebViewEvents, useAppConfig, useReportWorkflow } from './hooks';
import {
  WindowItem,
  AudioDeviceItem,
  HistoryRecord,
  QuickLinkItem,
  ViewType,
  SanctionSyncStatus,
  UpdateStatus,
  EvidenceCleanupResult,
  EvidenceCleanupTarget,
  HistoryDeleteResult,
  DisconnectDriveResponse,
  ResetUserDataResponse,
} from './types';
import { normalizeSafeHttpsUrl } from './utils';
import './styles/app.css';

import { choosePreferredWindow } from './utils/appHelpers';

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
    isLoading: isConfigLoading,
    saveError,
    clearSaveError,
  } = useAppConfig();
  const [gdriveAuthenticated, setGdriveAuthenticated] = useState<boolean | null>(null);
  const [isAuthenticatingDrive, setIsAuthenticatingDrive] = useState(false);
  const [isResettingUserData, setIsResettingUserData] = useState(false);

  const [windows, setWindows] = useState<WindowItem[]>([
    { title: '新楓之谷：經典版', width: 1920, height: 1080 },
  ]);

  const [audioDevices, setAudioDevices] = useState<AudioDeviceItem[]>([
    { id: '', name: '系統預設' },
  ]);

  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const reportWorkflow = useReportWorkflow({
    config,
    onHistoryChange: setHistory,
  });
  const {
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
    handleSkipOcr,
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
  } = reportWorkflow;
  const [sanctionSyncStatus, setSanctionSyncStatus] = useState<SanctionSyncStatus | null>(null);
  const [isCheckingSanctions, setIsCheckingSanctions] = useState<boolean>(false);
  const [lastCompleteSyncAt, setLastCompleteSyncAt] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState<boolean>(true);
  const [onboardingReplay, setOnboardingReplay] = useState(false);
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus | null>(null);
  const manualUpdateCheckRef = useRef(false);

  // Quick Link In-place Modal State
  const [quickLinkModalOpen, setQuickLinkModalOpen] = useState(false);
  const [editingQuickLink, setEditingQuickLink] = useState<QuickLinkItem | null>(null);

  // PyWebView Bridge Event Subscriptions
  usePyWebViewEvents({
    SANCTION_SYNC_STARTED: (data) => {
      setSanctionSyncStatus(data);
      setIsCheckingSanctions(true);
    },
    SANCTION_SYNC_PROGRESS: (data) => {
      setSanctionSyncStatus(data);
      setIsCheckingSanctions(true);
    },
    SANCTION_SYNC_COMPLETED: (data) => {
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
    SANCTION_SYNC_FAILED: (data) => {
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
    const bridge = getReporterBridge();
    if (bridge) {
      try {
        const initData = await bridge.app.initialData();
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
            restoreReplayState(initData.replay_state, initData.replay_duration);
          }

          // Trigger startup sanction sync once if applicable
          const activeBridge = getReporterBridge();
          if (activeBridge) {
            activeBridge.integrations
              .startSanctionSync('startup')
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
  }, [restoreReplayState, setConfig]);

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
      initPyWebView();
      window.addEventListener('pywebviewready', initPyWebView);
    }
    return () => window.removeEventListener('pywebviewready', initPyWebView);
  }, [initPyWebView]);

  useEffect(() => {
    const bridge = getReporterBridge();
    if (currentView === 'history' && bridge) {
      bridge.history
        .load()
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

  const handleOpenUrl = (url: string) => {
    if (!url) return;
    const targetUrl = normalizeSafeHttpsUrl(url);
    if (!targetUrl) {
      toast.warning('無法開啟連結', '只允許安全的 HTTPS 網址。');
      return;
    }
    const bridge = getReporterBridge();
    if (bridge) {
      void bridge.window.openExternalUrl(targetUrl);
    } else {
      window.open(targetUrl, '_blank', 'noopener,noreferrer');
    }
  };

  const handleClearHistory = async (): Promise<boolean> => {
    const bridge = getReporterBridge();
    if (!bridge) {
      toast.warning('目前無法清空歷史紀錄', '請使用桌面版程式操作。');
      return false;
    }

    try {
      const cleared = await bridge.history.clear();
      if (!cleared) {
        toast.error('清空歷史紀錄失敗', '本機歷史檔案沒有成功更新。');
        return false;
      }

      const initData = await bridge.app.initialData();
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

    const bridge = getReporterBridge();
    if (bridge) {
      try {
        const res = await bridge.integrations.startSanctionSync('manual');
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
    const bridge = getReporterBridge();
    if (!bridge) {
      toast.warning('目前環境無法檢查更新', '請使用 Windows 發行版執行此功能');
      return;
    }
    if (updateStatus?.state === 'downloading') {
      toast.warning('正在下載更新中', '請等待下載完成或取消下載後再檢查更新');
      return;
    }
    if (updateStatus?.state === 'applying' || updateStatus?.state === 'waiting_for_idle') {
      return;
    }
    manualUpdateCheckRef.current = true;
    toast.info('正在檢查更新…');
    await bridge.updates.check(force);
  };

  const reloadHistory = async () => {
    const bridge = getReporterBridge();
    if (!bridge) return;
    const records = await bridge.history.load();
    if (Array.isArray(records)) setHistory(records);
  };

  const handleCleanupHistoryEvidence = async (
    recordIds: string[],
    targets: EvidenceCleanupTarget[]
  ): Promise<EvidenceCleanupResult> => {
    const bridge = getReporterBridge();
    if (!bridge) {
      return { success: false, message: '目前無法清理證據，請使用桌面版程式操作。' };
    }
    try {
      const result = await bridge.history.cleanupEvidence(recordIds, targets);
      await reloadHistory();
      return result;
    } catch (error: unknown) {
      return { success: false, message: error instanceof Error ? error.message : String(error) };
    }
  };

  const handleDeleteHistoryEntries = async (
    recordIds: string[],
    cleanupTargets: EvidenceCleanupTarget[] = []
  ): Promise<HistoryDeleteResult> => {
    const bridge = getReporterBridge();
    if (!bridge) {
      return { success: false, message: '目前無法刪除紀錄，請使用桌面版程式操作。' };
    }
    try {
      const result = await bridge.history.deleteEntries(recordIds, cleanupTargets);
      await reloadHistory();
      return result;
    } catch (error: unknown) {
      return { success: false, message: error instanceof Error ? error.message : String(error) };
    }
  };

  const handleStartUpdateDownload = async () => {
    const bridge = getReporterBridge();
    if (!bridge) return;
    await bridge.updates.startDownload();
  };

  const handleCancelUpdateDownload = async () => {
    const bridge = getReporterBridge();
    if (!bridge) return;
    await bridge.updates.cancelDownload();
  };

  const handleRestartAndApplyUpdate = async () => {
    const bridge = getReporterBridge();
    if (!bridge) return;
    await bridge.updates.restartAndApply();
  };

  const handleRefreshWindows = useCallback(
    async (silent = false) => {
      const bridge = getReporterBridge();
      if (bridge) {
        try {
          const list = await bridge.config.windows();
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
      const bridge = getReporterBridge();
      if (bridge) {
        try {
          const list = await bridge.config.audioDevices();
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
    const bridge = getReporterBridge();
    if (!bridge) {
      toast.info('正在連線登入 Google 帳號（測試）...');
      return;
    }

    setIsAuthenticatingDrive(true);
    toast.info('正在開啟系統瀏覽器進行 Google 授權驗證...');
    try {
      const res = await bridge.integrations.authenticateGdrive();
      let authenticated = Boolean(res?.is_authenticated);
      try {
        authenticated = await bridge.integrations.checkGdriveAuth();
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
    } catch (error: unknown) {
      setGdriveAuthenticated(false);
      toast.error(
        'Google 帳號登入異常',
        error instanceof Error ? error.message : String(error)
      );
    } finally {
      setIsAuthenticatingDrive(false);
    }
  };

  const handleOpenDriveFolder = async () => {
    const bridge = getReporterBridge();
    if (bridge) {
      const url = await bridge.integrations.gdriveFolderUrl(config.gdrive_folder_name);
      await bridge.window.openExternalUrl(url);
    } else {
      window.open('https://drive.google.com/', '_blank');
    }
  };

  const handleClearRecordings = async () => {
    const bridge = getReporterBridge();
    if (bridge) {
      const res = await bridge.media.clearRecordings();
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
    config.upload_destination === 'none' ||
    (config.upload_destination === 'discord' && !config.discord_webhook_url) ||
    (config.upload_destination === 'gdrive' && gdriveAuthenticated === false);
  const configurationWarning =
    config.upload_destination === 'none'
      ? '目前是只試用模式，不會上傳證據。送出檢舉前請選擇 Google Drive 或 Discord。'
      : config.upload_destination === 'gdrive'
      ? '尚未登入 Google 帳號，檢舉證據目前無法上傳。'
      : '尚未設定 Discord 頻道連結，檢舉證據目前無法上傳。';

  const handleOnboardingWindowDrag = (event: MouseEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    const target = event.target as HTMLElement;
    if (target.closest('.window-controls, button, a, input, select')) return;
    void getReporterBridge()?.window.drag('proportional');
  };

  const handleDisconnectDrive = async (): Promise<DisconnectDriveResponse> => {
    const bridge = getReporterBridge();
    if (!bridge) {
      return {
        success: false,
        message: '目前無法連接桌面程式，請重新啟動後再試。',
        is_authenticated: Boolean(gdriveAuthenticated),
        remote_revoked: false,
        requires_manual_revoke: false,
      };
    }
    const result = await bridge.integrations.disconnectGdrive();
    if (result.success) setGdriveAuthenticated(false);
    return result;
  };

  const handleResetAllUserData = async (): Promise<ResetUserDataResponse> => {
    const bridge = getReporterBridge();
    if (!bridge) {
      return {
        success: false,
        accepted: false,
        message: '目前無法連接桌面程式，請重新啟動後再試。',
      };
    }
    const result = await bridge.integrations.resetUserData();
    if (result.accepted) setIsResettingUserData(true);
    return result;
  };

  const handleOnboardingHeaderDoubleClick = (event: MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (target.closest('.window-controls, button, a, input, select')) return;
    void getReporterBridge()?.window.toggleMaximized();
  };

  if (isInitializing || isConfigLoading) {
    return (
      <div className="app-container app-initializing">
        <WindowResizeHandles />
        <div className="route-loading" role="status">正在準備應用程式…</div>
      </div>
    );
  }

  if (onboardingReplay || config.onboarding_completed !== true) {
    return (
      <div className="app-container onboarding-app-container">
        <WindowResizeHandles />
        <div
          className="onboarding-window-controls pywebview-drag-region"
          onMouseDown={handleOnboardingWindowDrag}
          onDoubleClick={handleOnboardingHeaderDoubleClick}
        >
          <WindowControls />
        </div>
        <OnboardingFlow
          config={config}
          windows={windows}
          gdriveAuthenticated={gdriveAuthenticated}
          gdriveAuthLoading={isAuthenticatingDrive}
          onUpdateConfig={updateConfig}
          onUpdateConfigBatch={updateConfigBatch}
          onAuthenticateDrive={handleAuthenticateDrive}
          onFinish={async () => {
            await updateConfig('onboarding_completed', true);
            setOnboardingReplay(false);
          }}
          onSkip={async () => {
            await updateConfigBatch({
              onboarding_completed: true,
              report_submission_mode: 'automatic',
            });
            setOnboardingReplay(false);
          }}
        />
      </div>
    );
  }

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
              onDisconnectDrive={handleDisconnectDrive}
              onResetAllUserData={handleResetAllUserData}
              onRefreshWindows={handleRefreshWindows}
              onRefreshAudio={handleRefreshAudio}
              onClearRecordings={handleClearRecordings}
              updateStatus={updateStatus}
              onCheckForUpdates={() => handleCheckForUpdates(true)}
              onStartUpdateDownload={handleStartUpdateDownload}
              onCancelUpdateDownload={handleCancelUpdateDownload}
              onRestartAndApplyUpdate={handleRestartAndApplyUpdate}
              updateBusy={
                statusState !== 'idle' ||
                isSubmittingReport ||
                modalOpen ||
                ['checking', 'downloading', 'waiting_for_idle', 'applying'].includes(
                  updateStatus?.state || ''
                )
              }
              onReplayOnboarding={() => setOnboardingReplay(true)}
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
              onCleanupEvidence={handleCleanupHistoryEvidence}
              onDeleteHistoryEntries={handleDeleteHistoryEntries}
              onOpenUrl={handleOpenUrl}
              onCheckSanctions={handleCheckSanctions}
              onContinueDraft={handleContinueDraft}
              onContinueManual={handleContinueManual}
              ocrAutofillId={config.ocr_autofill_id !== false}
              ocrAutofillMap={config.ocr_autofill_map !== false}
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
            key={reportWorkflowId}
            stage={modalStage}
            progressPercent={modalProgress}
            progressStatus={modalStatusText}
            isSubmitting={isSubmittingReport}
            submissionStatus={submissionStatus}
            ocrResults={ocrResults}
            config={config}
            history={history}
            initialRecord={activeHistoryRecord}
            isSavingDraft={isSavingDraft}
            onClose={handleCloseReport}
            onSkipOcr={handleSkipOcr}
            onSubmitReport={handleSubmitReport}
            onSaveDraft={handleSaveReportDraft}
            onRecognizeCurrentFrame={handleRecognizeCurrentFrame}
            onOpenFilePath={(p) => {
              void getReporterBridge()?.window.openMediaFile(p);
            }}
            onOpenFileLocation={(p) => {
              void getReporterBridge()?.window.openFileLocation(p);
            }}
            onUpdateWhitelist={(newWhitelist) => {
              updateConfig('whitelist', newWhitelist);
              toast.success('略過名單已更新');
            }}
            onPersistFormSubmitHeadless={(enabled) =>
              updateConfig('form_submit_headless', enabled)
            }
            onPersistSubmissionMode={(mode) => updateConfig('report_submission_mode', mode)}
            manualReport={manualReport}
            isConfirmingManual={isConfirmingManual}
            onOpenReportPage={() => handleOpenUrl('https://forms.gamania.com/s/eLGg4')}
            onConfirmManual={handleConfirmManualReport}
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

      {isResettingUserData && (
        <div className="user-data-reset-overlay" role="status" aria-live="assertive">
          <div className="user-data-reset-status">
            <span className="user-data-reset-spinner" aria-hidden="true" />
            <strong>正在關閉並刪除所有本機資料…</strong>
            <span>請不要重新開啟程式。</span>
          </div>
        </div>
      )}
    </div>
  );
}
