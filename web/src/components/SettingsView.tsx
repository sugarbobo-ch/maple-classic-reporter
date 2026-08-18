import React, { useState, useEffect } from 'react';
import { ArrowLeft } from 'lucide-react';
import { IconButton } from './ui';
import { useDisclosure, useToast } from '../hooks';
import QuickLinkModal from './QuickLinkModal';
import ViolationTemplateModal from './ViolationTemplateModal';
import {
  GeneralTab,
  OcrTab,
  UploadTab,
  RecordingTab,
  ReplayTab,
  HotkeysTab,
  QuickLinksTab,
  AboutTab,
  ClearRecordingsModal,
} from './settings';
import {
  AppConfig,
  QuickLinkItem,
  DropdownOption,
  WindowItem,
  AudioDeviceItem,
  ViolationTemplateItem,
  ClearRecordingsResponse,
} from '../types';
import { isValidDiscordWebhookUrl } from '../utils';
import { RECORDING_PRESETS, detectPresetKey, PresetKey } from '../constants/presets';

export interface SettingsViewProps {
  config: AppConfig;
  windows?: WindowItem[];
  audioDevices?: AudioDeviceItem[];
  initialTab?: string;
  gdriveAuthenticated?: boolean | null;
  gdriveAuthLoading?: boolean;
  onUpdateConfig: (key: keyof AppConfig, value: unknown) => void;
  onUpdateConfigBatch?: (updates: Partial<AppConfig>) => void;
  onBack: () => void;
  onOpenDriveFolder: () => void;
  onAuthenticateDrive: () => void;
  onRefreshWindows?: () => void;
  onRefreshAudio?: () => void;
  onClearRecordings?: () => void;
}

export default function SettingsView({
  config,
  windows = [],
  audioDevices = [],
  initialTab = 'general',
  gdriveAuthenticated = false,
  gdriveAuthLoading = false,
  onUpdateConfig,
  onUpdateConfigBatch,
  onBack,
  onOpenDriveFolder,
  onAuthenticateDrive,
  onRefreshWindows,
  onRefreshAudio,
}: SettingsViewProps) {
  const [activeTab, setActiveTab] = useState(initialTab);

  useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab);
    }
  }, [initialTab]);
  const { toast } = useToast();

  // Quick Links state
  const defaultInitialLinks: QuickLinkItem[] = [
    {
      id: 'official-main',
      title: '新楓之谷：經典版',
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
  ];
  const [quickLinks, setQuickLinks] = useState<QuickLinkItem[]>(
    config.quick_links && config.quick_links.length > 0 ? config.quick_links : defaultInitialLinks
  );
  const [editingLink, setEditingLink] = useState<QuickLinkItem | null>(null);
  const { isOpen: linkModalOpen, open: openLinkModal, close: closeLinkModal } = useDisclosure();

  // Violation Templates state
  const [templates, setTemplates] = useState<ViolationTemplateItem[]>(
    config.violation_templates && config.violation_templates.length > 0
      ? config.violation_templates
      : [{ name: '自動打怪／外掛行為', content: '自動打怪/外掛行為' }]
  );
  const [selectedTemplateIndex, setSelectedTemplateIndex] = useState(0);
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  const [editingTemplateIndex, setEditingTemplateIndex] = useState<number | null>(null);

  // Whitelist state
  const [whitelistInput, setWhitelistInput] = useState('');

  // Local text input states for debouncing
  const [defaultMap, setDefaultMap] = useState(config.default_map || '');
  const [defaultNote, setDefaultNote] = useState(config.default_note || '自動打怪/外掛行為');
  const [gdriveFolder, setGdriveFolder] = useState(config.gdrive_folder_name || 'MapleClassic_Reports');
  const [discordWebhook, setDiscordWebhook] = useState(config.discord_webhook_url || '');

  // Testing discord webhook state
  const [testingDiscord, setTestingDiscord] = useState(false);

  // Clear recordings popup modal state
  const [clearModalOpen, setClearModalOpen] = useState(false);
  const [clearingProgress, setClearingProgress] = useState(false);
  const [clearResult, setClearResult] = useState<ClearRecordingsResponse | null>(null);

  // Auto-sync all local state whenever config changes
  useEffect(() => {
    if (config.default_map !== undefined) setDefaultMap(config.default_map);
    if (config.default_note !== undefined) setDefaultNote(config.default_note);
    if (config.gdrive_folder_name !== undefined) setGdriveFolder(config.gdrive_folder_name);
    if (config.discord_webhook_url !== undefined) setDiscordWebhook(config.discord_webhook_url);
    if (config.quick_links && config.quick_links.length > 0) setQuickLinks(config.quick_links);
    if (config.violation_templates && config.violation_templates.length > 0) setTemplates(config.violation_templates);
  }, [config]);

  // Immediate save on change
  const handleImmediateTextChange = (key: keyof AppConfig, value: string) => {
    onUpdateConfig(key, value);
  };

  // Hotkey direct capture state
  const [listeningForHotkey, setListeningForHotkey] = useState<'save_replay' | 'record_video' | null>(null);

  const handleHotkeyChange = (
    key: 'save_replay_hotkey' | 'record_video_hotkey',
    newShortcut: string
  ) => {
    const otherKey = key === 'save_replay_hotkey' ? 'record_video_hotkey' : 'save_replay_hotkey';
    const otherShortcut = config[otherKey] || (key === 'save_replay_hotkey' ? 'Ctrl+Shift+F10' : 'Ctrl+Shift+F9');
    if (newShortcut.trim().toLowerCase() === otherShortcut.trim().toLowerCase()) {
      const otherLabel = key === 'save_replay_hotkey' ? '開始一般錄影' : '儲存循環錄影';
      toast.error('快捷鍵重複衝突', `「${newShortcut}」已被「${otherLabel}」使用，無法重複設定！請選擇其他按鍵。`);
      return false;
    }
    onUpdateConfig(key, newShortcut);
    toast.success(`快捷鍵已設定為：${newShortcut}`);
    return true;
  };

  useEffect(() => {
    if (!listeningForHotkey) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (e.key === 'Escape') {
        setListeningForHotkey(null);
        toast.info('已取消快捷鍵設定');
        return;
      }

      if (['Control', 'Shift', 'Alt', 'Meta'].includes(e.key)) {
        return;
      }

      let keyName: string | null = null;
      if (e.key.startsWith('F') && /^F\d+$/i.test(e.key)) {
        keyName = e.key.toUpperCase();
      } else if (e.code.startsWith('Key')) {
        keyName = e.code.replace('Key', '').toUpperCase();
      } else if (e.code.startsWith('Digit')) {
        keyName = e.code.replace('Digit', '');
      } else if (e.code.startsWith('Numpad') && /^Numpad\d$/i.test(e.code)) {
        keyName = e.code.replace('Numpad', '');
      } else {
        const special: Record<string, string> = {
          ' ': 'Space',
          'Space': 'Space',
          'Tab': 'Tab',
          'Enter': 'Enter',
          'Insert': 'Insert',
          'Delete': 'Delete',
          'Home': 'Home',
          'End': 'End',
          'PageUp': 'PageUp',
          'PageDown': 'PageDown',
          'ArrowUp': 'Up',
          'ArrowDown': 'Down',
          'ArrowLeft': 'Left',
          'ArrowRight': 'Right',
        };
        if (special[e.key]) {
          keyName = special[e.key];
        } else if (e.key.length === 1 && /[a-zA-Z0-9]/.test(e.key)) {
          keyName = e.key.toUpperCase();
        }
      }

      if (keyName) {
        const fullShortcut = `Ctrl+Shift+${keyName}`;
        const configKey = listeningForHotkey === 'save_replay' ? 'save_replay_hotkey' : 'record_video_hotkey';
        handleHotkeyChange(configKey, fullShortcut);
        setListeningForHotkey(null);
      }
    };

    window.addEventListener('keydown', handleKeyDown, true);
    return () => {
      window.removeEventListener('keydown', handleKeyDown, true);
    };
  }, [listeningForHotkey, config, onUpdateConfig, toast]);

  useEffect(() => {
    if (config.violation_templates && config.violation_templates.length > 0) {
      setTemplates(config.violation_templates);
    }
  }, [config.violation_templates]);

  // Whitelist management
  const whitelist = Array.isArray(config.whitelist) ? config.whitelist : [];

  const handleAddWhitelist = () => {
    if (!whitelistInput.trim()) return;
    const newItems = whitelistInput
      .split(',')
      .map((s) => s.trim())
      .filter((s) => s && !whitelist.includes(s));

    if (newItems.length > 0) {
      const updated = [...whitelist, ...newItems];
      onUpdateConfig('whitelist', updated);
      setWhitelistInput('');
    }
  };

  const handleRemoveWhitelist = (item: string) => {
    const updated = whitelist.filter((i) => i !== item);
    onUpdateConfig('whitelist', updated);
  };

  // Violation Template Handlers
  const handleSelectTemplate = (idx: number) => {
    setSelectedTemplateIndex(idx);
    const tmpl = templates[idx];
    if (tmpl) {
      setDefaultNote(tmpl.content);
      onUpdateConfig('default_note', tmpl.content);
    }
  };

  const handleOpenAddTemplate = () => {
    setEditingTemplateIndex(null);
    setTemplateModalOpen(true);
  };

  const handleOpenEditTemplate = (idx: number) => {
    setEditingTemplateIndex(idx);
    setTemplateModalOpen(true);
  };

  const handleSaveTemplate = (name: string, content: string) => {
    let updated: ViolationTemplateItem[];
    if (editingTemplateIndex !== null) {
      updated = templates.map((t, idx) =>
        idx === editingTemplateIndex ? { name, content } : t
      );
    } else {
      updated = [...templates, { name, content }];
    }
    setTemplates(updated);
    onUpdateConfig('violation_templates', updated);
    setTemplateModalOpen(false);
    toast.success('違規範本已儲存');
  };

  const handleDeleteTemplate = (idx: number) => {
    if (templates.length <= 1) {
      toast.warning('至少需保留一個違規範本');
      return;
    }
    const updated = templates.filter((_, i) => i !== idx);
    setTemplates(updated);
    onUpdateConfig('violation_templates', updated);
    setSelectedTemplateIndex(0);
    toast.info('已刪除範本');
  };

  // Quick Links handlers
  const handleSaveQuickLink = (linkData: QuickLinkItem) => {
    let updated: QuickLinkItem[];
    if (editingLink) {
      updated = quickLinks.map((l) => (l.id === linkData.id ? linkData : l));
    } else {
      updated = [...quickLinks, linkData];
    }
    setQuickLinks(updated);
    onUpdateConfig('quick_links', updated);
    setEditingLink(null);
    closeLinkModal();
    toast.success(editingLink ? '捷徑已更新' : '捷徑已新增');
  };

  const handleDeleteQuickLink = (id: string) => {
    const updated = quickLinks.filter((l) => l.id !== id);
    setQuickLinks(updated);
    onUpdateConfig('quick_links', updated);
    toast.info('已刪除捷徑');
  };

  const handleMoveQuickLink = (idx: number, direction: 'up' | 'down') => {
    const targetIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (targetIdx < 0 || targetIdx >= quickLinks.length) return;
    const updated = [...quickLinks];
    const temp = updated[idx];
    updated[idx] = updated[targetIdx];
    updated[targetIdx] = temp;
    setQuickLinks(updated);
    onUpdateConfig('quick_links', updated);
  };

  // Drag and drop state
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  const handleDragStart = (_e: React.DragEvent, index: number) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;
    setDragOverIndex(index);
  };

  const handleDrop = (e: React.DragEvent, targetIndex: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === targetIndex) return;

    const newLinks = [...quickLinks];
    const [draggedItem] = newLinks.splice(draggedIndex, 1);
    newLinks.splice(targetIndex, 0, draggedItem);

    setQuickLinks(newLinks);
    onUpdateConfig('quick_links', newLinks);
    setDraggedIndex(null);
    setDragOverIndex(null);
    toast.success('快捷連結排序已更新');
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  const handleTestDiscord = async () => {
    if (!discordWebhook.trim()) {
      toast.warning('請先輸入 Discord Webhook URL');
      return;
    }
    if (!isValidDiscordWebhookUrl(discordWebhook)) {
      toast.warning('Webhook 格式不符', '必須以 https://discord.com/api/webhooks/ 或 discordapp.com 開頭');
      return;
    }
    setTestingDiscord(true);
    if (window.pywebview && window.pywebview.api) {
      try {
        const ok = await window.pywebview.api.test_discord_webhook(discordWebhook);
        if (ok) {
          toast.success('Discord Webhook 測試連線成功！');
        } else {
          toast.error('Discord Webhook 測試失敗', '請確認 Webhook 網址是否正確有效');
        }
      } catch (e: any) {
        toast.error('發送失敗', e?.message || String(e));
      }
    } else {
      try {
        const res = await fetch(discordWebhook, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            embeds: [
              {
                title: '🍁 Maple Classic Reporter - 連線測試',
                description: '這是一則由 Maple Classic Reporter 偏好設定發送的連線測試通知。',
                color: 0x5865f2,
                timestamp: new Date().toISOString(),
              },
            ],
          }),
        });
        if (res.ok || res.status === 204) {
          toast.success('Discord Webhook 測試連線成功！');
        } else {
          toast.error('連線測試失敗', `狀態碼: ${res.status}`);
        }
      } catch (e: any) {
        toast.error('連線發送失敗', e?.message || String(e));
      }
    }
    setTestingDiscord(false);
  };

  const handleOpenAppData = () => {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.open_app_data_folder();
    } else {
      toast.info(
        '開啟本機資料夾 (%LOCALAPPDATA%\\MapleClassicReporter)',
        '提示：桌面版程式運行時將自動喚起 Windows 檔案總管'
      );
    }
  };

  const handleExecuteClearRecordings = async () => {
    setClearingProgress(true);
    if (window.pywebview && window.pywebview.api) {
      try {
        const res = await window.pywebview.api.clear_all_recordings();
        setClearResult(res);
      } catch (e: any) {
        toast.error('清理暫存失敗', e?.message || String(e));
      }
    } else {
      setClearResult({ success: true, count: 3, size_str: '24.8 MB' });
    }
    setClearingProgress(false);
  };

  const handleOpenClearModal = () => {
    setClearResult(null);
    setClearModalOpen(true);
  };

  const handleOpenGitHub = () => {
    const url = 'https://github.com/sugarbobo-ch/maple-classic-reporter';
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.open_external_url(url);
    } else {
      window.open(url, '_blank');
    }
  };

  const handleOpenLogFile = async () => {
    if (window.pywebview?.api?.open_log_file) {
      const ok = await window.pywebview.api.open_log_file();
      if (!ok) {
        toast.info('日誌檔案已建立', '尚未有任何日誌內容。');
      }
    } else {
      toast.info('模擬日誌檢視 (Mock)', '已在獨立視窗開啟模擬日誌');
    }
  };

  const handleOpenLogFolder = () => {
    if (window.pywebview?.api?.open_log_folder) {
      window.pywebview.api.open_log_folder();
    } else if (window.pywebview?.api?.open_app_data_folder) {
      window.pywebview.api.open_app_data_folder();
    } else {
      toast.info('開啟日誌資料夾 (Mock)');
    }
  };

  // Dropdown Options
  const serverOptions: DropdownOption<string>[] = [
    { value: '雪吉拉', label: '雪吉拉' },
    { value: '菇菇寶貝', label: '菇菇寶貝' },
  ];

  const destinationOptions: DropdownOption<'gdrive' | 'discord'>[] = [
    { value: 'gdrive', label: 'Google Drive（建議）' },
    { value: 'discord', label: 'Discord Webhook' },
  ];

  const fpsOptions: DropdownOption<number>[] = [
    { value: 15, label: '15 FPS' },
    { value: 20, label: '20 FPS' },
    { value: 24, label: '24 FPS' },
    { value: 30, label: '30 FPS' },
    { value: 45, label: '45 FPS' },
    { value: 60, label: '60 FPS' },
  ];

  const countdownOptions: DropdownOption<number>[] = [
    { value: 0, label: '無倒數 (立即錄影)' },
    { value: 1, label: '1 秒' },
    { value: 2, label: '2 秒' },
    { value: 3, label: '3 秒 (預設)' },
    { value: 5, label: '5 秒' },
    { value: 10, label: '10 秒' },
  ];

  const replayPresetOptions: DropdownOption<number>[] = [
    { value: 10, label: '10 秒' },
    { value: 15, label: '15 秒' },
    { value: 20, label: '20 秒 (推薦)' },
    { value: 25, label: '25 秒' },
    { value: 30, label: '30 秒 (上限)' },
  ];

  const handlePresetChange = (presetKey: PresetKey) => {
    const selectedPreset = RECORDING_PRESETS.find((p) => p.key === presetKey);
    if (selectedPreset) {
      if (onUpdateConfigBatch) {
        onUpdateConfigBatch({
          recording_preset: selectedPreset.key,
          record_duration_sec: selectedPreset.duration,
          record_fps: selectedPreset.fps,
          replay_buffer_sec: selectedPreset.replay,
        });
      } else {
        onUpdateConfig('recording_preset', selectedPreset.key);
        onUpdateConfig('record_duration_sec', selectedPreset.duration);
        onUpdateConfig('record_fps', selectedPreset.fps);
        onUpdateConfig('replay_buffer_sec', selectedPreset.replay);
      }
    }
  };

  const handleManualDurationChange = (val: number) => {
    const nextDuration = Math.max(1, Math.min(60, val));
    onUpdateConfig('record_duration_sec', nextDuration);
    const matched = detectPresetKey(nextDuration, config.record_fps, config.replay_buffer_sec);
    onUpdateConfig('recording_preset', matched);
  };

  const handleManualFpsChange = (val: number) => {
    onUpdateConfig('record_fps', val);
    const matched = detectPresetKey(config.record_duration_sec, val, config.replay_buffer_sec);
    onUpdateConfig('recording_preset', matched);
  };

  const handleManualReplayChange = (val: number) => {
    const nextReplay = Math.max(5, Math.min(120, val));
    onUpdateConfig('replay_buffer_sec', nextReplay);
    const matched = detectPresetKey(config.record_duration_sec, config.record_fps, nextReplay);
    onUpdateConfig('recording_preset', matched);
  };

  const windowOptions: DropdownOption<string>[] = windows.map((w) => ({
    value: w.title,
    label: w.title,
  }));

  const audioDeviceOptions: DropdownOption<string>[] = audioDevices.map((d) => ({
    value: d.id,
    label: d.name,
  }));

  const hotkeyKeyOptions: DropdownOption<string>[] = [
    ...Array.from({ length: 12 }, (_, i) => ({ value: `F${i + 1}`, label: `F${i + 1}` })),
    ...['S', 'R', 'C', 'V', 'X', 'Z', 'A', 'D', 'W', 'Q', 'E', '1', '2', '3', '4'].map((k) => ({
      value: k,
      label: k,
    })),
  ];

  const saveReplayKey = (config.save_replay_hotkey || 'F9').split('+').pop() || 'F9';
  const recordVideoKey = (config.record_video_hotkey || 'F10').split('+').pop() || 'F10';

  return (
    <div
      className="card-section"
      style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}
    >
      <div className="modal-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <IconButton
            icon={ArrowLeft}
            size="md"
            variant="ghost"
            tooltip="返回首頁"
            onClick={onBack}
          />
          <span style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--color-text-heading)' }}>
            偏好設定
          </span>
        </div>
      </div>

      <div className="settings-container">
        {/* Sidebar Navigation */}
        <div className="settings-sidebar">
          <div
            className={`settings-nav-item ${activeTab === 'general' ? 'active' : ''}`}
            onClick={() => setActiveTab('general')}
          >
            一般與表單預設
          </div>
          <div
            className={`settings-nav-item ${activeTab === 'ocr' ? 'active' : ''}`}
            onClick={() => setActiveTab('ocr')}
          >
            OCR 辨識設定
          </div>
          <div
            className={`settings-nav-item ${activeTab === 'upload' ? 'active' : ''}`}
            onClick={() => setActiveTab('upload')}
          >
            上傳與帳號
          </div>
          <div
            className={`settings-nav-item ${activeTab === 'recording' ? 'active' : ''}`}
            onClick={() => setActiveTab('recording')}
          >
            錄影與音訊
          </div>
          <div
            className={`settings-nav-item ${activeTab === 'replay' ? 'active' : ''}`}
            onClick={() => setActiveTab('replay')}
          >
            循環錄影
          </div>
          <div
            className={`settings-nav-item ${activeTab === 'hotkeys' ? 'active' : ''}`}
            onClick={() => setActiveTab('hotkeys')}
          >
            全域快捷鍵
          </div>
          <div
            className={`settings-nav-item ${activeTab === 'quicklinks' ? 'active' : ''}`}
            onClick={() => setActiveTab('quicklinks')}
          >
            快捷連結
          </div>
          <div
            className={`settings-nav-item ${activeTab === 'about' ? 'active' : ''}`}
            onClick={() => setActiveTab('about')}
          >
            關於與更新
          </div>
        </div>

        {/* Panel Content */}
        <div className="settings-panel">
          {/* Tab 1: 一般與表單預設 */}
          {activeTab === 'general' && (
            <GeneralTab
              config={config}
              serverOptions={serverOptions}
              defaultMap={defaultMap}
              defaultNote={defaultNote}
              templates={templates}
              selectedTemplateIndex={selectedTemplateIndex}
              whitelist={whitelist}
              whitelistInput={whitelistInput}
              onUpdateConfig={onUpdateConfig}
              onDefaultMapChange={(val) => {
                setDefaultMap(val);
                handleImmediateTextChange('default_map', val);
              }}
              onWhitelistInputChange={setWhitelistInput}
              onAddWhitelist={handleAddWhitelist}
              onRemoveWhitelist={handleRemoveWhitelist}
              onSelectTemplate={handleSelectTemplate}
              onOpenAddTemplate={handleOpenAddTemplate}
              onOpenEditTemplate={handleOpenEditTemplate}
              onDeleteTemplate={handleDeleteTemplate}
            />
          )}

          {/* Tab 2: OCR 辨識設定 */}
          {activeTab === 'ocr' && (
            <OcrTab config={config} onUpdateConfig={onUpdateConfig} />
          )}

          {/* Tab 3: 上傳與帳號 */}
          {activeTab === 'upload' && (
            <UploadTab
              config={config}
              destinationOptions={destinationOptions}
              gdriveFolder={gdriveFolder}
              discordWebhook={discordWebhook}
              testingDiscord={testingDiscord}
              gdriveAuthenticated={gdriveAuthenticated}
              gdriveAuthLoading={gdriveAuthLoading}
              onUpdateConfig={onUpdateConfig}
              onGdriveFolderChange={(val) => {
                setGdriveFolder(val);
                handleImmediateTextChange('gdrive_folder_name', val);
              }}
              onDiscordWebhookChange={(val) => {
                setDiscordWebhook(val);
                handleImmediateTextChange('discord_webhook_url', val);
              }}
              onAuthenticateDrive={onAuthenticateDrive}
              onOpenDriveFolder={onOpenDriveFolder}
              onTestDiscord={handleTestDiscord}
            />
          )}

          {/* Tab 4: 錄影與音訊 */}
          {activeTab === 'recording' && (
            <RecordingTab
              config={config}
              windowOptions={windowOptions}
              audioDeviceOptions={audioDeviceOptions}
              fpsOptions={fpsOptions}
              countdownOptions={countdownOptions}
              onUpdateConfig={onUpdateConfig}
              onPresetChange={handlePresetChange}
              onManualDurationChange={handleManualDurationChange}
              onManualFpsChange={handleManualFpsChange}
              onRefreshWindows={onRefreshWindows}
              onRefreshAudio={onRefreshAudio}
              onOpenAppData={handleOpenAppData}
              onOpenClearModal={handleOpenClearModal}
            />
          )}

          {/* Tab 5: 循環錄影 */}
          {activeTab === 'replay' && (
            <ReplayTab
              config={config}
              replayPresetOptions={replayPresetOptions}
              onPresetChange={handlePresetChange}
              onManualReplayChange={handleManualReplayChange}
            />
          )}

          {/* Tab 6: 全域快捷鍵 */}
          {activeTab === 'hotkeys' && (
            <HotkeysTab
              config={config}
              listeningForHotkey={listeningForHotkey}
              hotkeyKeyOptions={hotkeyKeyOptions}
              saveReplayKey={saveReplayKey}
              recordVideoKey={recordVideoKey}
              onUpdateConfig={onUpdateConfig}
              onUpdateHotkey={handleHotkeyChange}
              onSetListeningForHotkey={setListeningForHotkey}
            />
          )}

          {/* Tab 7: 快捷連結 */}
          {activeTab === 'quicklinks' && (
            <QuickLinksTab
              quickLinks={quickLinks}
              draggedIndex={draggedIndex}
              dragOverIndex={dragOverIndex}
              onOpenAddModal={() => {
                setEditingLink(null);
                openLinkModal();
              }}
              onOpenEditModal={(item) => {
                setEditingLink(item);
                openLinkModal();
              }}
              onDeleteQuickLink={handleDeleteQuickLink}
              onMoveQuickLink={handleMoveQuickLink}
              onDragStart={handleDragStart}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onDragEnd={handleDragEnd}
            />
          )}

          {/* Tab 8: 關於與更新 */}
          {activeTab === 'about' && (
            <AboutTab
              config={config}
              onUpdateConfig={onUpdateConfig}
              onOpenGitHub={handleOpenGitHub}
              onOpenLogFile={handleOpenLogFile}
              onOpenLogFolder={handleOpenLogFolder}
            />
          )}
        </div>
      </div>

      {/* Quick Link Edit Modal */}
      {linkModalOpen && (
        <QuickLinkModal
          linkToEdit={editingLink}
          onSave={handleSaveQuickLink}
          onClose={() => {
            closeLinkModal();
            setEditingLink(null);
          }}
        />
      )}

      {/* Violation Template Modal */}
      <ViolationTemplateModal
        isOpen={templateModalOpen}
        templateToEdit={
          editingTemplateIndex !== null && templates[editingTemplateIndex]
            ? templates[editingTemplateIndex]
            : null
        }
        onSave={handleSaveTemplate}
        onClose={() => {
          setTemplateModalOpen(false);
          setEditingTemplateIndex(null);
        }}
      />

      {/* Clear Recordings Popup Dialog */}
      <ClearRecordingsModal
        isOpen={clearModalOpen}
        clearResult={clearResult}
        clearingProgress={clearingProgress}
        onClose={() => setClearModalOpen(false)}
        onExecuteClear={handleExecuteClearRecordings}
      />
    </div>
  );
}
