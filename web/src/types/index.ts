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

export interface AppConfig {
  default_server: string;
  default_map: string;
  default_note: string;
  selected_window_title: string;
  record_duration_sec: number;
  record_fps: number;
  record_countdown_sec?: number;
  replay_buffer_sec: number;
  upload_destination: 'gdrive' | 'discord';
  gdrive_folder_name: string;
  discord_webhook_url: string;
  whitelist: string[];
  auto_delete_after_upload: boolean;
  record_audio: boolean;
  ocr_autofill_id: boolean;
  ocr_autofill_map?: boolean;
  audio_output_device_id: string;
  global_hotkeys_enabled?: boolean;
  save_replay_hotkey?: string;
  record_video_hotkey?: string;
  form_submit_headless?: boolean;
  dev_mode?: boolean;
  auto_check_sanction_status?: boolean;
  recording_preset?: 'ultra_fast' | 'smooth' | 'balanced' | 'high_fps' | 'extreme' | 'custom';
  has_initialized_defaults?: boolean;
  violation_templates?: ViolationTemplateItem[];
  app_data_dir?: string;
  quick_links?: QuickLinkItem[];
  [key: string]: unknown;
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
  ban_status?: 'pending' | 'banned' | 'unbanned' | string;
  ban_date?: string;
  ban_announcement_url?: string;
  ban_bulletin_id?: number;
  ban_result?: string;
  ban_masked_name?: string;
  ban_checked_at?: string;
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
  sanction_sync_status?: SanctionSyncStatus;
  last_complete_sync_at?: string;
}

export interface SubmissionResponse {
  status: 'success' | 'error';
  message: string;
  evidence_url?: string;
}

export type SubmissionStatusKind = 'progress' | 'success' | 'error';

export interface SubmissionStatusData {
  step?: string;
  status?: SubmissionStatusKind;
  message: string;
}

export interface AuthResponse {
  success: boolean;
  message: string;
  is_authenticated: boolean;
}

export interface ClearRecordingsResponse {
  success: boolean;
  count: number;
  total_bytes?: number;
  size_str?: string;
}

export type PyWebViewEventType =
  | 'RECORDING_COUNTDOWN'
  | 'RECORDING_PROGRESS'
  | 'RECORDING_FINISHED'
  | 'RECORDING_CANCELED'
  | 'RECORDING_ERROR'
  | 'REPLAY_STATE_CHANGED'
  | 'REPLAY_SAVED'
  | 'REPLAY_ERROR'
  | 'OCR_STATUS'
  | 'OCR_RESULT'
  | 'SUBMISSION_STATUS'
  | 'GLOBAL_HOTKEY_TRIGGERED'
  | 'WINDOW_MAXIMIZED'
  | 'WINDOW_RESTORED'
  | 'SANCTION_SYNC_STARTED'
  | 'SANCTION_SYNC_PROGRESS'
  | 'SANCTION_SYNC_COMPLETED'
  | 'SANCTION_SYNC_FAILED';

export interface PyWebViewEvent {
  type: PyWebViewEventType;
  data: any;
}

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
          audioDeviceId?: string
        ) => Promise<boolean>;
        cancel_recording: () => Promise<boolean>;
        start_replay: (
          windowTitle?: string,
          fps?: number,
          bufferSeconds?: number,
          recordAudio?: boolean,
          audioDeviceId?: string
        ) => Promise<boolean>;
        stop_replay: () => Promise<boolean>;
        save_replay: () => Promise<boolean>;
        get_replay_status: () => Promise<{ state: string; duration: number; is_running: boolean }>;
        select_local_file: () => Promise<string | null>;
        process_imported_file: (filePath: string) => Promise<OcrResultData>;
        submit_report: (formData: Record<string, unknown>) => Promise<SubmissionResponse>;
        check_gdrive_auth: () => Promise<boolean>;
        authenticate_gdrive: () => Promise<AuthResponse>;
        get_gdrive_folder_url: (folderName?: string) => Promise<string>;
        test_discord_webhook: (
          webhookUrl: string
        ) => Promise<{ success: boolean; message: string }>;
        open_external_url: (url: string) => Promise<boolean>;
        open_file_location: (filePath: string) => void;
        open_media_file: (filePath: string) => void;
        get_media_preview: (filePath: string) => Promise<string>;
        get_media_stream_url: (filePath: string) => Promise<string>;
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
        start_sanction_sync: (trigger?: 'startup' | 'manual') => Promise<{
          started: boolean;
          reason?: 'already_running' | 'disabled' | 'fresh' | 'no_history';
          status: SanctionSyncStatus;
        }>;
        get_sanction_sync_status: () => Promise<SanctionSyncStatus>;
        get_history: () => Promise<HistoryRecord[]>;
        rebuild_sanction_cache_for_development: () => Promise<boolean>;
      };
    };
  }
}
