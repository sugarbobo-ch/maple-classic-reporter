import { useState, useEffect, useCallback } from 'react';
import { AppConfig } from '../types';

export const DEFAULT_APP_CONFIG: AppConfig = {
  default_server: '雪吉拉',
  default_map: '',
  default_note: '自動打怪/外掛行為',
  selected_window_title: '新楓之谷：經典版 (1920x1080)',
  record_duration_sec: 8,
  record_fps: 20,
  record_countdown_sec: 0,
  replay_buffer_sec: 20,
  recording_preset: 'balanced',
  has_initialized_defaults: false,
  upload_destination: 'gdrive',
  gdrive_folder_name: 'MapleClassic_Reports',
  discord_webhook_url: '',
  whitelist: ['player01', 'player02'],
  auto_delete_after_upload: false,
  record_audio: true,
  ocr_autofill_id: true,
  ocr_autofill_map: true,
  audio_output_device_id: '',
  global_hotkeys_enabled: true,
  save_replay_hotkey: 'Ctrl+Shift+F9',
  record_video_hotkey: 'Ctrl+Shift+F10',
  form_submit_headless: true,
  dev_mode: false,
  auto_check_sanction_status: true,
  quick_links: [
    {
      id: 'official-main',
      title: '新楓之谷官網',
      url: 'https://maplestoryclassic.beanfun.com/Main',
      icon: 'Globe',
      isDefault: true,
    },
    {
      id: 'official-report',
      title: '外掛檢舉頁面',
      url: 'https://forms.gamania.com/s/eLGg4',
      icon: 'ShieldAlert',
      isDefault: true,
    },
  ],
};

export function useAppConfig() {
  const [config, setConfig] = useState<AppConfig>(DEFAULT_APP_CONFIG);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Load configuration from PyWebView backend bridge
  const reloadConfig = useCallback(async () => {
    if (window.pywebview && window.pywebview.api) {
      try {
        const initData = await window.pywebview.api.get_initial_data();
        if (initData && initData.config) {
          const nextConfig = {
            ...DEFAULT_APP_CONFIG,
            ...initData.config,
          };
          setConfig(nextConfig);
          return nextConfig;
        }
      } catch (err) {
        console.warn('Failed to load initial config from backend:', err);
      } finally {
        setIsLoading(false);
      }
      return null;
    } else {
      setIsLoading(false);
      return null;
    }
  }, []);

  useEffect(() => {
    if (window.pywebview && window.pywebview.api) {
      reloadConfig();
    } else {
      const handleReady = () => {
        reloadConfig();
      };
      window.addEventListener('pywebviewready', handleReady);
      return () => window.removeEventListener('pywebviewready', handleReady);
    }
  }, [reloadConfig]);

  // Update a single config item and auto-persist to backend
  const updateConfig = useCallback(
    async (key: keyof AppConfig, value: unknown) => {
      const previousConfig = config;
      setConfig((prev) => ({
        ...prev,
        [key]: value,
      }));

      if (window.pywebview && window.pywebview.api) {
        try {
          setSaveError(null);
          const saved = await window.pywebview.api.save_config_key(String(key), value);
          if (!saved) throw new Error('後端拒絕儲存設定');
        } catch (err) {
          console.error(`Failed to save config key "${String(key)}":`, err);
          setSaveError(`無法儲存設定「${String(key)}」`);
          const restoredConfig = await reloadConfig();
          if (!restoredConfig) setConfig(previousConfig);
        }
      }
    },
    [config, reloadConfig]
  );

  // Update multiple config items in one atomic batch
  const updateConfigBatch = useCallback(
    async (updates: Partial<AppConfig>) => {
      const previousConfig = config;
      const nextConfig = { ...config, ...updates };
      setConfig(nextConfig);

      if (window.pywebview && window.pywebview.api) {
        try {
          setSaveError(null);
          const saved = await window.pywebview.api.save_config_all(nextConfig);
          if (!saved) throw new Error('後端拒絕儲存設定');
        } catch (err) {
          console.error('Failed to save config batch:', err);
          setSaveError('無法儲存設定');
          const restoredConfig = await reloadConfig();
          if (!restoredConfig) setConfig(previousConfig);
        }
      }
    },
    [config, reloadConfig]
  );

  // Batch update all config items
  const saveAllConfig = useCallback(async (newConfig: AppConfig) => {
    const previousConfig = config;
    setConfig(newConfig);

    if (window.pywebview && window.pywebview.api) {
      try {
        setSaveError(null);
        const saved = await window.pywebview.api.save_config_all(newConfig);
        if (!saved) throw new Error('後端拒絕儲存設定');
      } catch (err) {
        console.error('Failed to batch save config:', err);
        setSaveError('無法儲存設定');
        const restoredConfig = await reloadConfig();
        if (!restoredConfig) setConfig(previousConfig);
      }
    }
  }, [config, reloadConfig]);

  return {
    config,
    setConfig,
    updateConfig,
    updateConfigBatch,
    saveAllConfig,
    reloadConfig,
    isDevMode: Boolean(config.dev_mode),
    isLoading,
    saveError,
    clearSaveError: () => setSaveError(null),
  };
}

export default useAppConfig;
