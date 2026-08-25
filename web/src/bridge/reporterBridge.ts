import type {
  EvidenceCleanupResult,
  EvidenceCleanupTarget,
  HistoryRecord,
} from '../types';

type PyWebViewApi = NonNullable<NonNullable<Window['pywebview']>['api']>;
type ApiMethod<Name extends keyof PyWebViewApi> = PyWebViewApi[Name];

/** The desktop transport surface exposed by PyWebView. */
export type ReporterBridgeTransport = Pick<
  PyWebViewApi,
  | 'get_initial_data'
  | 'clear_history'
  | 'get_clipboard_text'
  | 'set_clipboard_text'
  | 'minimize_window'
  | 'toggle_window_maximized'
  | 'close_window'
  | 'drag_window'
  | 'resize_window'
  | 'save_config_key'
  | 'save_config_all'
  | 'get_windows'
  | 'get_audio_devices'
  | 'capture_screenshot'
  | 'start_recording'
  | 'cancel_recording'
  | 'cancel_ocr'
  | 'start_replay'
  | 'stop_replay'
  | 'save_replay'
  | 'get_replay_status'
  | 'select_local_file'
  | 'process_imported_file'
  | 'submit_report'
  | 'confirm_manual_report'
  | 'save_report_draft'
  | 'check_gdrive_auth'
  | 'authenticate_gdrive'
  | 'disconnect_gdrive'
  | 'get_gdrive_folder_url'
  | 'test_discord_webhook'
  | 'open_external_url'
  | 'open_file_location'
  | 'open_media_file'
  | 'get_media_preview'
  | 'get_media_stream_url'
  | 'recognize_video_frame'
  | 'trim_video_segment'
  | 'restore_original_video'
  | 'clear_all_recordings'
  | 'open_app_data_folder'
  | 'open_log_file'
  | 'open_log_folder'
  | 'reset_all_user_data'
  | 'start_sanction_sync'
  | 'get_sanction_sync_status'
  | 'get_history'
  | 'cleanup_history_evidence'
  | 'delete_history_entries'
  | 'rebuild_sanction_cache_for_development'
  | 'get_update_status'
  | 'check_for_updates'
  | 'start_update_download'
  | 'cancel_update_download'
  | 'restart_and_apply_update'
>;
type HistoryBridgeTransport = Pick<
  ReporterBridgeTransport,
  'get_history' | 'clear_history' | 'cleanup_history_evidence' | 'delete_history_entries'
>;

export interface ReporterBridge {
  app: {
    initialData: ApiMethod<'get_initial_data'>;
  };
  config: {
    saveKey: ApiMethod<'save_config_key'>;
    saveAll: ApiMethod<'save_config_all'>;
    windows: ApiMethod<'get_windows'>;
    audioDevices: ApiMethod<'get_audio_devices'>;
    getClipboardText: ApiMethod<'get_clipboard_text'>;
    setClipboardText: ApiMethod<'set_clipboard_text'>;
  };
  capture: {
    screenshot: ApiMethod<'capture_screenshot'>;
    startRecording: ApiMethod<'start_recording'>;
    cancelRecording: ApiMethod<'cancel_recording'>;
    cancelOcr: ApiMethod<'cancel_ocr'>;
    startReplay: ApiMethod<'start_replay'>;
    stopReplay: ApiMethod<'stop_replay'>;
    saveReplay: ApiMethod<'save_replay'>;
    replayStatus: ApiMethod<'get_replay_status'>;
    selectLocalFile: ApiMethod<'select_local_file'>;
    processImportedFile: ApiMethod<'process_imported_file'>;
    recognizeVideoFrame: ApiMethod<'recognize_video_frame'>;
  };
  reports: {
    submit: ApiMethod<'submit_report'>;
    confirmManual: ApiMethod<'confirm_manual_report'>;
    saveDraft: ApiMethod<'save_report_draft'>;
  };
  media: {
    preview: ApiMethod<'get_media_preview'>;
    streamUrl: ApiMethod<'get_media_stream_url'>;
    trim: ApiMethod<'trim_video_segment'>;
    restore: ApiMethod<'restore_original_video'>;
    clearRecordings: ApiMethod<'clear_all_recordings'>;
  };
  history: {
    load: () => Promise<HistoryRecord[]>;
    clear: ApiMethod<'clear_history'>;
    cleanupEvidence: (
      recordIds: string[],
      targets: EvidenceCleanupTarget[]
    ) => Promise<EvidenceCleanupResult>;
    deleteEntries: (
      ...args: Parameters<ApiMethod<'delete_history_entries'>>
    ) => ReturnType<ApiMethod<'delete_history_entries'>>;
  };
  integrations: {
    checkGdriveAuth: ApiMethod<'check_gdrive_auth'>;
    authenticateGdrive: ApiMethod<'authenticate_gdrive'>;
    disconnectGdrive: ApiMethod<'disconnect_gdrive'>;
    gdriveFolderUrl: ApiMethod<'get_gdrive_folder_url'>;
    testDiscordWebhook: ApiMethod<'test_discord_webhook'>;
    startSanctionSync: ApiMethod<'start_sanction_sync'>;
    sanctionSyncStatus: ApiMethod<'get_sanction_sync_status'>;
    rebuildSanctionCache: ApiMethod<'rebuild_sanction_cache_for_development'>;
    resetUserData: ApiMethod<'reset_all_user_data'>;
  };
  window: {
    minimize: ApiMethod<'minimize_window'>;
    toggleMaximized: ApiMethod<'toggle_window_maximized'>;
    close: ApiMethod<'close_window'>;
    drag: ApiMethod<'drag_window'>;
    resize: ApiMethod<'resize_window'>;
    openExternalUrl: ApiMethod<'open_external_url'>;
    openFileLocation: ApiMethod<'open_file_location'>;
    openMediaFile: ApiMethod<'open_media_file'>;
    openAppDataFolder: ApiMethod<'open_app_data_folder'>;
    openLogFile: ApiMethod<'open_log_file'>;
    openLogFolder: ApiMethod<'open_log_folder'>;
  };
  updates: {
    status: ApiMethod<'get_update_status'>;
    check: ApiMethod<'check_for_updates'>;
    startDownload: ApiMethod<'start_update_download'>;
    cancelDownload: ApiMethod<'cancel_update_download'>;
    restartAndApply: ApiMethod<'restart_and_apply_update'>;
  };
}

export function createReporterBridge(transport: ReporterBridgeTransport): ReporterBridge {
  return {
    app: {
      initialData: () => transport.get_initial_data(),
    },
    config: {
      saveKey: (key, value) => transport.save_config_key(key, value),
      saveAll: (config) => transport.save_config_all(config),
      windows: () => transport.get_windows(),
      audioDevices: () => transport.get_audio_devices(),
      getClipboardText: () => transport.get_clipboard_text(),
      setClipboardText: (text) => transport.set_clipboard_text(text),
    },
    capture: {
      screenshot: (mode) => transport.capture_screenshot(mode),
      startRecording: (...args) => transport.start_recording(...args),
      cancelRecording: () => transport.cancel_recording(),
      cancelOcr: () => transport.cancel_ocr(),
      startReplay: (...args) => transport.start_replay(...args),
      stopReplay: () => transport.stop_replay(),
      saveReplay: () => transport.save_replay(),
      replayStatus: () => transport.get_replay_status(),
      selectLocalFile: () => transport.select_local_file(),
      processImportedFile: (filePath) => transport.process_imported_file(filePath),
      recognizeVideoFrame: (filePath, timestampSec) =>
        transport.recognize_video_frame(filePath, timestampSec),
    },
    reports: {
      submit: (formData) => transport.submit_report(formData),
      confirmManual: (recordId) => transport.confirm_manual_report(recordId),
      saveDraft: (formData) => transport.save_report_draft(formData),
    },
    media: {
      preview: (filePath) => transport.get_media_preview(filePath),
      streamUrl: (filePath) => transport.get_media_stream_url(filePath),
      trim: (...args) => transport.trim_video_segment(...args),
      restore: (...args) => transport.restore_original_video(...args),
      clearRecordings: () => transport.clear_all_recordings(),
    },
    history: {
      ...createHistoryBridge(transport),
    },
    integrations: {
      checkGdriveAuth: () => transport.check_gdrive_auth(),
      authenticateGdrive: () => transport.authenticate_gdrive(),
      disconnectGdrive: () => transport.disconnect_gdrive(),
      gdriveFolderUrl: (folderName) => transport.get_gdrive_folder_url(folderName),
      testDiscordWebhook: (webhookUrl) => transport.test_discord_webhook(webhookUrl),
      startSanctionSync: (trigger) => transport.start_sanction_sync(trigger),
      sanctionSyncStatus: () => transport.get_sanction_sync_status(),
      rebuildSanctionCache: () => transport.rebuild_sanction_cache_for_development(),
      resetUserData: () => transport.reset_all_user_data(),
    },
    window: {
      minimize: () => transport.minimize_window(),
      toggleMaximized: () => transport.toggle_window_maximized(),
      close: () => transport.close_window(),
      drag: (anchorMode) => transport.drag_window(anchorMode),
      resize: (direction) => transport.resize_window(direction),
      openExternalUrl: (url) => transport.open_external_url(url),
      openFileLocation: (filePath) => transport.open_file_location(filePath),
      openMediaFile: (filePath) => transport.open_media_file(filePath),
      openAppDataFolder: () => transport.open_app_data_folder(),
      openLogFile: () => transport.open_log_file(),
      openLogFolder: () => transport.open_log_folder(),
    },
    updates: {
      status: () => transport.get_update_status(),
      check: (force) => transport.check_for_updates(force),
      startDownload: () => transport.start_update_download(),
      cancelDownload: () => transport.cancel_update_download(),
      restartAndApply: () => transport.restart_and_apply_update(),
    },
  };
}

export function createHistoryBridge(transport: HistoryBridgeTransport): ReporterBridge['history'] {
  return {
    load: () => transport.get_history(),
    clear: () => transport.clear_history(),
    cleanupEvidence: (recordIds, targets) =>
      transport.cleanup_history_evidence(recordIds, targets),
    deleteEntries: (...args) => transport.delete_history_entries(...args),
  };
}

export function getReporterBridge(): ReporterBridge | null {
  const transport = window.pywebview?.api;
  return transport ? createReporterBridge(transport) : null;
}
