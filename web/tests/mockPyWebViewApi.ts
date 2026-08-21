import { vi } from 'vitest';
import type {
  AppConfig,
  AudioDeviceItem,
  HistoryRecord,
  InitialDataResponse,
  WindowItem,
} from '../src/types';

type PyWebViewApi = NonNullable<NonNullable<Window['pywebview']>['api']>;

export const TEST_CONFIG: AppConfig = {
  default_server: 'Gamania',
  default_map: 'Test Map',
  default_note: 'Test note',
  selected_window_title: 'MapleStory Classic',
  record_duration_sec: 8,
  record_fps: 30,
  record_countdown_sec: 0,
  replay_buffer_sec: 30,
  upload_destination: 'gdrive',
  gdrive_folder_name: 'MapleClassic_Reports',
  discord_webhook_url: '',
  whitelist: ['known-player'],
  auto_delete_after_upload: false,
  record_audio: true,
  audio_capture_mode: 'process',
  ocr_autofill_id: true,
  ocr_autofill_map: true,
  audio_output_device_id: '',
  global_hotkeys_enabled: true,
  save_replay_hotkey: 'Ctrl+Shift+F9',
  record_video_hotkey: 'Ctrl+Shift+F10',
  form_submit_headless: true,
  dev_mode: false,
  quick_links: [],
};

export const TEST_WINDOWS: WindowItem[] = [
  { title: 'MapleStory Classic', width: 1920, height: 1080 },
];

export const TEST_AUDIO_DEVICES: AudioDeviceItem[] = [{ id: '', name: 'Default output' }];

export const TEST_HISTORY: HistoryRecord[] = [
  {
    timestamp: '2026-08-17 12:00:00',
    suspect_id: 'suspect-42',
    server: 'Gamania',
    map_name: 'Test Map',
    upload_status: 'success',
    evidence_url: 'https://drive.google.com/file/d/test-evidence/view',
  },
];

export const TEST_INITIAL_DATA: InitialDataResponse = {
  config: TEST_CONFIG,
  windows: TEST_WINDOWS,
  audio_devices: TEST_AUDIO_DEVICES,
  history: TEST_HISTORY,
  gdrive_authenticated: false,
  replay_state: 'idle',
  replay_duration: 0,
};

export function createMockPyWebViewApi(
  overrides: Partial<PyWebViewApi> = {},
  initialData: InitialDataResponse = TEST_INITIAL_DATA
): PyWebViewApi {
  const defaults: Record<string, unknown> = {
    get_initial_data: vi.fn().mockResolvedValue(initialData),
    clear_history: vi.fn().mockResolvedValue(true),
    get_clipboard_text: vi.fn().mockResolvedValue(''),
    set_clipboard_text: vi.fn().mockResolvedValue(true),
    minimize_window: vi.fn().mockResolvedValue(true),
    toggle_window_maximized: vi.fn().mockResolvedValue(false),
    close_window: vi.fn().mockResolvedValue(true),
    drag_window: vi.fn().mockResolvedValue(true),
    resize_window: vi.fn().mockResolvedValue(true),
    save_config_key: vi.fn().mockResolvedValue(true),
    save_config_all: vi.fn().mockResolvedValue(true),
    get_windows: vi.fn().mockResolvedValue(TEST_WINDOWS),
    get_audio_devices: vi.fn().mockResolvedValue(TEST_AUDIO_DEVICES),
    capture_screenshot: vi.fn().mockResolvedValue({
      status: 'success',
      suspect_ids: [],
      map_name: 'Test Map',
      media_path: '',
      media_type: 'image',
    }),
    start_recording: vi.fn().mockResolvedValue(true),
    cancel_recording: vi.fn().mockResolvedValue(true),
    cancel_ocr: vi.fn().mockResolvedValue(true),
    start_replay: vi.fn().mockResolvedValue(true),
    stop_replay: vi.fn().mockResolvedValue(true),
    save_replay: vi.fn().mockResolvedValue(true),
    get_replay_status: vi.fn().mockResolvedValue({
      state: 'idle',
      duration: 0,
      is_running: false,
    }),
    select_local_file: vi.fn().mockResolvedValue(null),
    process_imported_file: vi.fn().mockResolvedValue({
      status: 'success',
      suspect_ids: [],
      map_name: 'Test Map',
      media_path: '',
      media_type: 'image',
    }),
    submit_report: vi.fn().mockResolvedValue({
      status: 'success',
      message: 'Submitted',
      evidence_url: TEST_HISTORY[0].evidence_url,
    }),
    check_gdrive_auth: vi.fn().mockResolvedValue(false),
    authenticate_gdrive: vi.fn().mockResolvedValue({
      success: false,
      message: 'Not configured for test',
      is_authenticated: false,
    }),
    get_gdrive_folder_url: vi.fn().mockResolvedValue('https://drive.google.com/drive/my-drive'),
    test_discord_webhook: vi.fn().mockResolvedValue({ success: true, message: 'OK' }),
    open_external_url: vi.fn().mockResolvedValue(true),
    open_file_location: vi.fn(),
    open_media_file: vi.fn(),
    get_media_preview: vi.fn().mockResolvedValue(''),
    get_media_stream_url: vi.fn().mockResolvedValue(''),
    recognize_video_frame: vi.fn().mockResolvedValue({
      status: 'success',
      suspect_ids: [],
      map_name: '',
      media_path: '',
      media_type: 'video',
    }),
    trim_video_segment: vi.fn().mockResolvedValue({ success: false, error: 'No trim result' }),
    restore_original_video: vi
      .fn()
      .mockResolvedValue({ success: false, error: 'No restore result' }),
    clear_all_recordings: vi.fn().mockResolvedValue({ success: true, count: 0, total_bytes: 0 }),
    open_app_data_folder: vi.fn(),
    open_log_file: vi.fn().mockResolvedValue(true),
    open_log_folder: vi.fn(),
    start_sanction_sync: vi.fn().mockResolvedValue({
      started: true,
      status: { running: true, trigger: 'manual', phase: 'listing' },
    }),
    get_sanction_sync_status: vi.fn().mockResolvedValue({ running: false }),
    get_history: vi.fn().mockResolvedValue(TEST_HISTORY),
    rebuild_sanction_cache_for_development: vi.fn().mockResolvedValue(true),
  };

  return { ...defaults, ...overrides } as PyWebViewApi;
}

export function installMockPyWebView(
  overrides: Partial<PyWebViewApi> = {},
  initialData: InitialDataResponse = TEST_INITIAL_DATA
): PyWebViewApi {
  const api = createMockPyWebViewApi(overrides, initialData);
  window.pywebview = { api };
  return api;
}
