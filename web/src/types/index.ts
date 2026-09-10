import { LucideIcon } from 'lucide-react';

export interface QuickLinkItem {
  id: string;
  title: string;
  url: string;
  icon: string;
  isDefault?: boolean;
}

export interface ViolationTemplateItem {
  name: string;
  content: string;
}

export type AudioCaptureMode = 'process' | 'system' | 'off';
export type ReportSubmissionMode = 'manual' | 'automatic';
export type UploadDestination = 'gdrive' | 'discord' | 'none';

export interface AppConfig {
  default_server: string;
  default_map: string;
  default_note: string;
  selected_window_title: string;
  record_duration_sec: number;
  record_fps: number;
  record_countdown_sec?: number;
  replay_buffer_sec: number;
  replay_save_sec?: number | null;
  upload_destination: UploadDestination;
  gdrive_folder_name: string;
  discord_webhook_url: string;
  whitelist: string[];
  auto_delete_after_upload: boolean;
  record_audio: boolean;
  audio_capture_mode: AudioCaptureMode;
  ocr_autofill_id: boolean;
  ocr_autofill_map?: boolean;
  audio_output_device_id: string;
  global_hotkeys_enabled?: boolean;
  save_replay_hotkey?: string;
  record_video_hotkey?: string;
  form_submit_headless?: boolean;
  onboarding_completed?: boolean;
  report_submission_mode?: ReportSubmissionMode;
  dev_mode?: boolean;
  auto_check_sanction_status?: boolean;
  theme?: 'light' | 'dark';
  history_compact_layout?: boolean;
  history_page_size?: number;
  last_complete_sync_at?: string;
  recording_preset?: 'ultra_fast' | 'smooth' | 'balanced' | 'high_fps' | 'extreme' | 'custom';
  has_initialized_defaults?: boolean;
  violation_templates?: ViolationTemplateItem[];
  app_data_dir?: string;
  quick_links?: QuickLinkItem[];
  auto_update_enabled?: boolean;
  update_channel?: 'stable' | 'preview';
}

export type UpdateState =
  | 'idle'
  | 'checking'
  | 'up_to_date'
  | 'available'
  | 'downloading'
  | 'ready'
  | 'waiting_for_idle'
  | 'applying'
  | 'updated'
  | 'error'
  | 'insufficient_space';

export interface UpdateStatus {
  state: UpdateState;
  current_version: string;
  target_version?: string | null;
  downloaded_bytes: number;
  total_bytes: number;
  progress_percent: number;
  package_kind?: 'delta' | 'full' | null;
  release_notes?: string;
  release_url?: string;
  required_bytes: number;
  available_bytes: number;
  error_code?: string | null;
  error_message?: string | null;
}

export interface WindowItem {
  title: string;
  width: number;
  height: number;
}

export interface AudioDeviceItem {
  id: string;
  name: string;
}

export interface HistoryRecord {
  batch_id?: string;
  batch_order?: number;
  batch_note?: string;
  note_override?: string | null;
  batch_phase?: 'draft' | 'queued' | 'sending' | 'unknown' | 'manual' | 'completed';

  record_id?: string;
  timestamp?: string;
  time?: string;
  suspect_id?: string;
  id?: string;
  server?: string;
  map_name?: string;
  map?: string;
  upload_status?: string;
  status?: string;
  evidence_url?: string;
  url?: string;
  note?: string;
  submission_state?: 'draft' | 'awaiting_manual' | 'submitted';
  submission_mode?: ReportSubmissionMode;
  media_path?: string;
  media_type?: 'video' | 'image' | string;
  media_available?: boolean;
  evidence_provider?: 'gdrive' | 'discord' | 'external' | 'none' | string;
  remote_evidence_id?: string;
  remote_evidence_state?: 'available' | 'trashed' | 'unmanaged' | 'unavailable' | 'error' | string;
  remote_evidence_cleaned_at?: string;
  remote_cleanup_error?: string;
  local_evidence_cleaned_at?: string;
  media_cleanup_eligible?: boolean;
  ban_status?: 'pending' | 'banned' | 'unbanned' | string;
  ban_date?: string;
  ban_announcement_url?: string;
  ban_bulletin_id?: number;
  ban_result?: string;
  ban_masked_name?: string;
  ban_checked_at?: string;
}

export type EvidenceCleanupTarget = 'local' | 'google_drive';

export interface EvidenceCleanupTargetResult {
  success: boolean;
  message?: string;
  status?: string;
}

export interface EvidenceCleanupResult {
  success: boolean;
  cleaned_record_ids?: string[];
  failed_record_ids?: string[];
  results?: Array<{
    record_id: string;
    success: boolean;
    record?: HistoryRecord;
    results?: Record<string, EvidenceCleanupTargetResult>;
    message?: string;
  }>;
  message?: string;
}

export interface HistoryDeleteResult {
  success: boolean;
  deleted_record_ids?: string[];
  failed_record_ids?: string[];
  failed?: Array<{
    record_id: string;
    message?: string;
    cleanup?: EvidenceCleanupResult;
  }>;
  message?: string;
}

export type SanctionSyncPhase = 'listing' | 'fetching' | 'matching';

export interface SanctionSyncStatus {
  running: boolean;
  trigger?: 'startup' | 'manual';
  phase?: SanctionSyncPhase;
  current?: number;
  total?: number;
  message?: string;
  last_complete_sync_at?: string;
}

export interface SanctionSyncSummary {
  completed: boolean;
  bulletin_count: number;
  checked_record_count: number;
  newly_banned_count: number;
  changed_to_unbanned_count: number;
  unchanged_count: number;
  indeterminate_count: number;
  failed_request_count: number;
  last_complete_sync_at?: string;
}

export interface OcrResultData {
  status?: string;
  message?: string;
  suspect_ids: string[];
  map_name: string;
  /** The map name actually recognised by OCR, excluding the configured default. */
  ocr_map_name?: string;
  /** Identifies whether map_name came from OCR or the configured default. */
  map_name_source?: 'ocr' | 'default' | 'manual';
  media_path: string;
  media_type: 'video' | 'image';
}

export interface DropdownOption<T = string | number> {
  value: T;
  label: string;
  icon?: LucideIcon;
}

export type ViewType = 'home' | 'settings' | 'history';
export type StatusState = 'idle' | 'recording' | 'replaying';

export interface InitialDataResponse {
  config?: AppConfig;
  windows?: WindowItem[];
  audio_devices?: AudioDeviceItem[];
  history?: HistoryRecord[];
  gdrive_authenticated?: boolean;
  replay_state?: string;
  replay_duration?: number;
  replay_total?: number;
  sanction_sync_status?: SanctionSyncStatus;
  last_complete_sync_at?: string;
  update_status?: UpdateStatus;
}

export interface SubmissionResponse {
  batch_id?: string;
  records?: HistoryRecord[];

  status: 'success' | 'manual_ready' | 'error';
  message: string;
  evidence_url?: string;
  record_id?: string;
  record?: HistoryRecord;
}

export interface ConfirmManualReportResponse {
  next_record?: HistoryRecord | null;
  records?: HistoryRecord[];

  status: 'success' | 'error';
  message: string;
  record?: HistoryRecord;
  deleted?: boolean;
}

export interface DraftSaveResponse {
  status: 'success' | 'error';
  message: string;
  record?: HistoryRecord;
}

export type SubmissionStatusKind = 'progress' | 'success' | 'error';

export interface SubmissionStatusData {
  batch_id?: string;
  records?: HistoryRecord[];

  step?: string;
  status?: SubmissionStatusKind;
  message: string;
}

export interface AuthResponse {
  success: boolean;
  message: string;
  is_authenticated: boolean;
}

export interface DisconnectDriveResponse extends AuthResponse {
  remote_revoked: boolean | null;
  requires_manual_revoke: boolean;
}

export interface ResetUserDataResponse {
  success: boolean;
  accepted: boolean;
  message: string;
}

export interface ClearRecordingsResponse {
  success: boolean;
  count: number;
  total_bytes?: number;
  size_str?: string;
}

export interface PyWebViewEventData {
  RECORDING_COUNTDOWN: { remaining: number; percent: number; total: number };
  RECORDING_PROGRESS: { elapsed: number; total: number; percent: number; fraction?: number };
  RECORDING_FINISHED: { file_path?: string } | undefined;
  RECORDING_CANCELED: undefined;
  RECORDING_ERROR: { message: string };
  REPLAY_STATE_CHANGED: { state: string; duration: number; total: number };
  REPLAY_SAVED: { file_path?: string } | undefined;
  REPLAY_ERROR: { message: string };
  OCR_STATUS: { status: string; percent: number; step?: string };
  OCR_RESULT: OcrResultData;
  EVIDENCE_READY: { file_path?: string; media_type?: 'video' | 'image' };
  SUBMISSION_STATUS: SubmissionStatusData;
  GLOBAL_HOTKEY_TRIGGERED: { action: string };
  WINDOW_MAXIMIZED: undefined;
  WINDOW_RESTORED: undefined;
  SANCTION_SYNC_STARTED: SanctionSyncStatus;
  SANCTION_SYNC_PROGRESS: SanctionSyncStatus;
  SANCTION_SYNC_COMPLETED: SanctionSyncStatus & {
    summary?: SanctionSyncSummary;
    history?: HistoryRecord[];
  };
  SANCTION_SYNC_FAILED: { history?: HistoryRecord[]; message?: string };
  UPDATE_STATUS: UpdateStatus;
}

export type PyWebViewEventType = keyof PyWebViewEventData;
export type PyWebViewEvent = {
  [K in PyWebViewEventType]: { type: K; data: PyWebViewEventData[K] };
}[PyWebViewEventType];

declare global {
  interface Window {
    __MAPLE_REPORTER_EVENT__?: (event: PyWebViewEvent) => void;
    pywebview?: {
      api: {
        get_initial_data: () => Promise<InitialDataResponse>;
        clear_history: () => Promise<boolean>;
        get_clipboard_text: () => Promise<string>;
        set_clipboard_text: (text: string) => Promise<boolean>;
        minimize_window: () => Promise<boolean>;
        toggle_window_maximized: () => Promise<boolean>;
        close_window: () => Promise<boolean>;
        drag_window: (anchorMode?: 'left' | 'right' | 'proportional') => Promise<boolean>;
        resize_window: (direction: string) => Promise<boolean>;
        save_config_key: (key: string, value: unknown) => Promise<boolean>;
        save_config_all: (config: Record<string, unknown>) => Promise<boolean>;
        get_windows: () => Promise<WindowItem[]>;
        get_audio_devices: () => Promise<AudioDeviceItem[]>;
        capture_screenshot: (mode?: string) => Promise<OcrResultData>;
        start_recording: (
          durationSec?: number,
          fps?: number,
          countdownSec?: number,
          recordAudio?: boolean,
          audioDeviceId?: string,
          audioCaptureMode?: AudioCaptureMode
        ) => Promise<boolean>;
        cancel_recording: () => Promise<boolean>;
        cancel_ocr: () => Promise<boolean>;
        start_replay: (
          windowTitle?: string,
          fps?: number,
          bufferSeconds?: number,
          recordAudio?: boolean,
          audioDeviceId?: string,
          audioCaptureMode?: AudioCaptureMode
        ) => Promise<boolean>;
        stop_replay: () => Promise<boolean>;
        save_replay: (saveSeconds?: number | null) => Promise<boolean>;
        get_replay_status: () => Promise<{
          state: string;
          duration: number;
          is_running: boolean;
          total?: number;
        }>;
        select_local_file: () => Promise<string | null>;
        process_imported_file: (filePath: string) => Promise<OcrResultData>;
        submit_report_batch: (formData: Record<string, unknown>) => Promise<SubmissionResponse>;
        save_report_batch: (formData: Record<string, unknown>) => Promise<DraftSaveResponse>;
        resolve_report_result: (data: { record_id: string; completed: boolean }) => Promise<SubmissionResponse>;
        submit_report: (formData: Record<string, unknown>) => Promise<SubmissionResponse>;
        confirm_manual_report: (recordId: string) => Promise<ConfirmManualReportResponse>;
        save_report_draft: (formData: Record<string, unknown>) => Promise<DraftSaveResponse>;
        check_gdrive_auth: () => Promise<boolean>;
        authenticate_gdrive: () => Promise<AuthResponse>;
        disconnect_gdrive: () => Promise<DisconnectDriveResponse>;
        get_gdrive_folder_url: (folderName?: string) => Promise<string>;
        test_discord_webhook: (
          webhookUrl: string
        ) => Promise<{ success: boolean; message: string }>;
        open_external_url: (url: string) => Promise<boolean>;
        open_file_location: (filePath: string) => void;
        open_media_file: (filePath: string) => void;
        get_media_preview: (filePath: string) => Promise<string>;
        get_media_stream_url: (filePath: string) => Promise<string>;
        recognize_video_frame: (
          filePath: string,
          timestampSec: number
        ) => Promise<OcrResultData & { frame_time?: number }>;
        trim_video_segment: (
          filePath: string,
          cutStart: number,
          cutEnd: number,
          originalBackupPath?: string
        ) => Promise<{
          success: boolean;
          new_path?: string;
          duration?: number;
          stream_url?: string;
          original_backup_path?: string;
          error?: string;
        }>;
        restore_original_video: (
          currentPath: string,
          backupPath: string
        ) => Promise<{
          success: boolean;
          restored_path?: string;
          duration?: number;
          stream_url?: string;
          error?: string;
        }>;
        clear_all_recordings: () => Promise<ClearRecordingsResponse>;
        open_app_data_folder: () => void;
        open_log_file: () => Promise<boolean>;
        open_log_folder: () => void;
        reset_all_user_data: () => Promise<ResetUserDataResponse>;
        start_sanction_sync: (trigger?: 'startup' | 'manual') => Promise<{
          started: boolean;
          reason?: 'already_running' | 'disabled' | 'fresh' | 'no_history';
          status: SanctionSyncStatus;
        }>;
        get_sanction_sync_status: () => Promise<SanctionSyncStatus>;
        get_history: () => Promise<HistoryRecord[]>;
        cleanup_history_evidence: (
          recordIds: string[],
          targets: Array<'local' | 'google_drive'>
        ) => Promise<EvidenceCleanupResult>;
        delete_history_entries: (
          recordIds: string[],
          cleanupTargets?: Array<'local' | 'google_drive'>
        ) => Promise<HistoryDeleteResult>;
        rebuild_sanction_cache_for_development: () => Promise<boolean>;
        get_update_status: () => Promise<UpdateStatus>;
        check_for_updates: (force?: boolean) => Promise<boolean>;
        start_update_download: () => Promise<boolean>;
        cancel_update_download: () => Promise<boolean>;
        restart_and_apply_update: () => Promise<boolean>;
      };
    };
  }
}
