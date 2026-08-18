import { useState, useEffect } from 'react';
import {
  ArrowLeft,
  Plus,
  Edit2,
  Trash2,
  CheckCircle,
  FolderOpen,
  Send,
  RefreshCw,
  Keyboard,
  ArrowUp,
  ArrowDown,
  ExternalLink,
  Info,
  AlertCircle,
  GripVertical,
  FileText,
} from 'lucide-react';
import { Switch, Dropdown, Input, Textarea, Button, IconButton, Badge, Dialog, DynamicIcon } from './ui';
import { useDisclosure, useToast } from '../hooks';
import QuickLinkModal from './QuickLinkModal';
import ViolationTemplateModal from './ViolationTemplateModal';
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
import PresetSlider from './PresetSlider';
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
  const [defaultMap, setDefaultMap] = useState(config.default_map || '維多利亞島');
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
        onUpdateConfig(configKey, fullShortcut);
        toast.success(`快捷鍵已設定為：${fullShortcut}`);
        setListeningForHotkey(null);
      }
    };

    window.addEventListener('keydown', handleKeyDown, true);
    return () => {
      window.removeEventListener('keydown', handleKeyDown, true);
    };
  }, [listeningForHotkey, onUpdateConfig, toast]);

  useEffect(() => {
    if (config.violation_templates && config.violation_templates.length > 0) {
      setTemplates(config.violation_templates);
    }
  }, [config.violation_templates]);

  const handleToggle = (key: keyof AppConfig) => {
    onUpdateConfig(key, !config[key]);
  };

  const handleChange = (key: keyof AppConfig, value: unknown) => {
    onUpdateConfig(key, value);
  };

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
    closeLinkModal();
    setEditingLink(null);
    toast.success('快捷連結已儲存');
  };

  const handleDeleteQuickLink = (id: string) => {
    const updated = quickLinks.filter((l) => l.id !== id);
    setQuickLinks(updated);
    onUpdateConfig('quick_links', updated);
    toast.info('已刪除快捷連結');
  };

  const handleMoveQuickLink = (index: number, direction: 'up' | 'down') => {
    if (direction === 'up' && index === 0) return;
    if (direction === 'down' && index === quickLinks.length - 1) return;
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    const updated = [...quickLinks];
    const temp = updated[index];
    updated[index] = updated[targetIndex];
    updated[targetIndex] = temp;
    setQuickLinks(updated);
    onUpdateConfig('quick_links', updated);
  };

  // Drag and Drop state for Quick Links
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(index));
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (dragOverIndex !== index) {
      setDragOverIndex(index);
    }
  };

  const handleDrop = (e: React.DragEvent, targetIndex: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === targetIndex) {
      setDraggedIndex(null);
      setDragOverIndex(null);
      return;
    }
    const updated = [...quickLinks];
    const [movedItem] = updated.splice(draggedIndex, 1);
    updated.splice(targetIndex, 0, movedItem);
    setQuickLinks(updated);
    onUpdateConfig('quick_links', updated);
    setDraggedIndex(null);
    setDragOverIndex(null);
    toast.success('快捷連結順序已更新');
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  const handleTestDiscord = async () => {
    const webhookUrl = discordWebhook.trim();
    if (!webhookUrl) {
      toast.warning('請先輸入 Discord Webhook URL');
      return;
    }
    if (!isValidDiscordWebhookUrl(webhookUrl)) {
      toast.error('連線測試失敗', '請輸入有效的 Discord HTTPS Webhook URL');
      return;
    }
    setTestingDiscord(true);
    if (window.pywebview && window.pywebview.api) {
      try {
        const res = await window.pywebview.api.test_discord_webhook(webhookUrl);
        if (res && res.success) {
          toast.success('連線測試成功！', res.message);
        } else {
          toast.error('連線測試失敗', res?.message);
        }
      } catch (e: any) {
        toast.error('連線異常', e?.message || String(e));
      }
    } else {
      try {
        const res = await fetch(webhookUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: 'Maple Classic Reporter: Webhook 連線測試成功！' }),
        });
        if (res.ok || res.status === 204) {
          toast.success('連線測試成功！', '已成功發送測試訊息至 Discord 頻道');
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
            <>
              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">預設遊戲伺服器</span>
                  <span className="setting-desc">檢舉表單自動選取之伺服器</span>
                </div>
                <div style={{ width: '160px', minWidth: '140px' }}>
                  <Dropdown
                    options={serverOptions}
                    value={config.default_server || '雪吉拉'}
                    onChange={(val) => handleChange('default_server', val)}
                  />
                </div>
              </div>

              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">預設所在地圖名稱</span>
                  <span className="setting-desc">OCR 未能確定時自動預填</span>
                </div>
                <div style={{ width: '220px', minWidth: '180px' }}>
                  <Input
                    value={defaultMap}
                    onChange={(e) => {
                      setDefaultMap(e.target.value);
                      handleImmediateTextChange('default_map', e.target.value);
                    }}
                  />
                </div>
              </div>

              {/* 違規說明與範本管理（自然排列無多餘外框與分隔線） */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                  <div className="setting-info">
                    <span className="setting-label">違規說明與範本管理</span>
                    <span className="setting-desc">管理常用違規備註範本並套用</span>
                  </div>
                  <Button variant="secondary" size="sm" icon={Plus} onClick={handleOpenAddTemplate}>
                    新增範本
                  </Button>
                </div>

                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <div style={{ width: '220px', minWidth: '180px' }}>
                    <Dropdown<number>
                      options={templates.map((t, idx) => ({ value: idx, label: t.name }))}
                      value={selectedTemplateIndex}
                      onChange={(idx) => handleSelectTemplate(idx)}
                    />
                  </div>
                  <Button
                    variant="outline"
                    size="md"
                    icon={Edit2}
                    onClick={() => handleOpenEditTemplate(selectedTemplateIndex)}
                  >
                    編輯
                  </Button>
                  <Button
                    variant="danger"
                    size="md"
                    icon={Trash2}
                    onClick={() => handleDeleteTemplate(selectedTemplateIndex)}
                  >
                    刪除
                  </Button>
                </div>

                <Textarea
                  value={defaultNote}
                  placeholder="違規說明內容"
                  rows={3}
                  disabled
                  helperText={
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <AlertCircle size={14} style={{ flexShrink: 0 }} color="var(--color-warning)" />
                      <span>提醒：點擊上方「編輯」或「新增範本」可修改內容。官方檢舉表單送出時換行將自動縮減合併為一行。</span>
                    </span>
                  }
                />
              </div>

              {/* 白名單管理（自然排列無多餘外框與分隔線） */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div className="setting-info">
                  <span className="setting-label">白名單角色 ID 管理</span>
                  <span className="setting-desc">輸入逗號分隔文字或 Enter，自動切分為 Chip，辨識時將自動過濾</span>
                </div>

                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: '200px' }}>
                    <Input
                      placeholder="輸入角色 ID (例如: player01, player02)"
                      value={whitelistInput}
                      onChange={(e) => setWhitelistInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleAddWhitelist()}
                    />
                  </div>
                  <Button variant="secondary" size="md" onClick={handleAddWhitelist} icon={Plus}>
                    新增
                  </Button>
                </div>

                <div className="chip-group" style={{ margin: '4px 0 0 0' }}>
                  {whitelist.map((item, idx) => (
                    <div key={idx} className="chip">
                      <span>{item}</span>
                      <span
                        style={{ marginLeft: '4px', cursor: 'pointer', fontWeight: 700 }}
                        onClick={() => handleRemoveWhitelist(item)}
                      >
                        ×
                      </span>
                    </div>
                  ))}
                  {whitelist.length === 0 && (
                    <span style={{ fontSize: '0.78rem', color: 'var(--color-text-tertiary)' }}>
                      尚無白名單成員
                    </span>
                  )}
                </div>
              </div>

              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">背景靜默送出檢舉</span>
                  <span className="setting-desc">啟用時 Playwright 自動填表於後台無聲執行；關閉時將開啟可見瀏覽器展示填表</span>
                </div>
                <Switch
                  checked={config.form_submit_headless !== false}
                  onChange={() => handleToggle('form_submit_headless')}
                />
              </div>

              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">啟動時自動更新制裁公告</span>
                  <span className="setting-desc">啟動且距離上次完整檢查超過 6 小時時，在背景以隨機間隔存取官方最新制裁名單</span>
                </div>
                <Switch
                  checked={config.auto_check_sanction_status !== false}
                  onChange={() => handleToggle('auto_check_sanction_status')}
                />
              </div>

              <div className="setting-row no-border">
                <div className="setting-info">
                  <span className="setting-label">自動刪除已確認事證</span>
                  <span className="setting-desc">表單提交與上傳成功後，自動刪除本機錄影暫存檔</span>
                </div>
                <Switch
                  checked={config.auto_delete_after_upload || false}
                  onChange={() => handleToggle('auto_delete_after_upload')}
                />
              </div>
            </>
          )}

          {/* Tab 2: OCR 辨識設定（提升至第 2 順位） */}
          {activeTab === 'ocr' && (
            <>
              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">角色 ID 自動 OCR 辨識</span>
                  <span className="setting-desc">自動辨識遊戲畫面中之玩家名稱並提供候選名單</span>
                </div>
                <Switch
                  checked={config.ocr_autofill_id !== false}
                  onChange={() => handleToggle('ocr_autofill_id')}
                />
              </div>

              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">地圖名稱自動 OCR 辨識</span>
                  <span className="setting-desc">自動辨識左上角小地圖區域文字並比對地圖目錄</span>
                </div>
                <Switch
                  checked={config.ocr_autofill_map !== false}
                  onChange={() => handleToggle('ocr_autofill_map')}
                />
              </div>

              <div
                style={{
                  padding: '12px 16px',
                  backgroundColor: 'var(--color-surface-card)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.82rem',
                  lineHeight: 1.6,
                  color: 'var(--color-text-secondary)',
                  marginTop: '4px',
                }}
              >
                <div style={{ fontWeight: 700, color: 'var(--color-text-heading)', marginBottom: '4px' }}>
                  OCR 引擎架構說明：
                </div>
                採用 RapidOCR (ONNX Runtime) 本地快速模型搭配 Windows 內建 OCR 引擎，並結合小地圖專用前處理與模糊比對庫，可精準識別「地區、村莊、隱密之地」等複雜地圖名稱。
              </div>
            </>
          )}

          {/* Tab 3: 上傳與帳號 */}
          {activeTab === 'upload' && (
            <>
              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">Google Drive 授權狀態</span>
                  <span className="setting-desc">用於長期儲存高畫質檢舉影片與照片</span>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <Badge
                    variant={gdriveAuthenticated ? 'success' : 'warning'}
                    icon={gdriveAuthenticated ? CheckCircle : AlertCircle}
                    data-testid="gdrive-auth-status"
                    aria-live="polite"
                  >
                    {gdriveAuthenticated ? '已授權' : '尚未授權'}
                  </Badge>
                  <Button
                    variant="outline"
                    size="md"
                    onClick={onAuthenticateDrive}
                    loading={gdriveAuthLoading}
                    disabled={gdriveAuthLoading}
                  >
                    {gdriveAuthLoading ? '授權中…' : gdriveAuthenticated ? '重新驗證' : '開始授權'}
                  </Button>
                </div>
              </div>

              {/* 前往雲端資料夾整合於此 */}
              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">Google Drive 資料夾名稱</span>
                  <span className="setting-desc">雲端硬碟存放事證之目錄名稱</span>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <div style={{ width: '220px', minWidth: '180px' }}>
                    <Input
                      placeholder="MapleClassic_Reports"
                      value={gdriveFolder}
                      onChange={(e) => {
                        setGdriveFolder(e.target.value);
                        handleImmediateTextChange('gdrive_folder_name', e.target.value);
                      }}
                    />
                  </div>
                  <Button
                    variant="secondary"
                    size="md"
                    icon={FolderOpen}
                    onClick={onOpenDriveFolder}
                  >
                    前往雲端資料夾
                  </Button>
                </div>
              </div>

              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">Discord Webhook URL</span>
                  <span className="setting-desc">頻道即時通報與短片快速分享</span>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <div style={{ width: '220px', minWidth: '180px' }}>
                    <Input
                      type="password"
                      placeholder="https://discord.com/api/webhooks/..."
                      value={discordWebhook}
                      onChange={(e) => {
                        setDiscordWebhook(e.target.value);
                        handleImmediateTextChange('discord_webhook_url', e.target.value);
                      }}
                    />
                  </div>
                  <Button
                    variant="secondary"
                    size="md"
                    icon={Send}
                    onClick={handleTestDiscord}
                    disabled={testingDiscord}
                  >
                    {testingDiscord ? '測試中...' : '測試連線'}
                  </Button>
                </div>
              </div>

              <div className="setting-row no-border">
                <div className="setting-info">
                  <span className="setting-label">優先上傳目的地</span>
                  <span className="setting-desc">自動選擇預設上傳管道</span>
                </div>
                <div style={{ width: '200px', minWidth: '160px' }}>
                  <Dropdown<'gdrive' | 'discord'>
                    options={destinationOptions}
                    value={config.upload_destination || 'gdrive'}
                    onChange={(val) => handleChange('upload_destination', val)}
                  />
                </div>
              </div>
            </>
          )}

          {/* Tab 4: 錄影與音訊 */}
          {activeTab === 'recording' && (
            <>
              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">目標遊戲視窗</span>
                  <span className="setting-desc">鎖定並擷取畫面之 Windows 視窗</span>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <div style={{ width: '260px', minWidth: '200px' }}>
                    <Dropdown<string>
                      options={windowOptions}
                      value={config.selected_window_title || '新楓之谷：經典版 (1920x1080)'}
                      onChange={(val) => handleChange('selected_window_title', val)}
                    />
                  </div>
                  {onRefreshWindows && (
                    <IconButton
                      icon={RefreshCw}
                      size="md"
                      variant="ghost"
                      tooltip="重新整理視窗清單"
                      onClick={onRefreshWindows}
                    />
                  )}
                </div>
              </div>

              <div className="setting-row">
                <div style={{ width: '100%' }}>
                  <PresetSlider
                    preset={config.recording_preset}
                    duration={config.record_duration_sec}
                    fps={config.record_fps}
                    replay={config.replay_buffer_sec}
                    onChangePreset={handlePresetChange}
                  />
                </div>
              </div>

              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">錄製短片秒數</span>
                  <span className="setting-desc">一般短片錄影持續長度 (1 ~ 60 秒)</span>
                </div>
                <div style={{ width: '140px', minWidth: '120px' }}>
                  <Input
                    type="number"
                    min="1"
                    max="60"
                    value={String(config.record_duration_sec || 8)}
                    onChange={(e) => {
                      const val = Math.max(1, Math.min(60, parseInt(e.target.value) || 8));
                      handleManualDurationChange(val);
                    }}
                  />
                </div>
              </div>

              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">錄影流暢度 (FPS)</span>
                  <span className="setting-desc">影格幀率，建議 20 ~ 30 FPS 兼顧效能與順暢度</span>
                </div>
                <div style={{ width: '140px', minWidth: '120px' }}>
                  <Dropdown<number>
                    options={fpsOptions}
                    value={config.record_fps || 20}
                    onChange={(val) => handleManualFpsChange(val)}
                  />
                </div>
              </div>

              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">錄影前倒數時間</span>
                  <span className="setting-desc">按下錄影後預留之準備倒數</span>
                </div>
                <div style={{ width: '180px', minWidth: '140px' }}>
                  <Dropdown<number>
                    options={countdownOptions}
                    value={config.record_countdown_sec || 0}
                    onChange={(val) => handleChange('record_countdown_sec', val)}
                  />
                </div>
              </div>

              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">同步錄製系統聲音 (WASAPI Loopback)</span>
                  <span className="setting-desc">同步錄製遊戲內音效與背景音樂</span>
                </div>
                <Switch
                  checked={config.record_audio !== false}
                  onChange={() => handleToggle('record_audio')}
                />
              </div>

              {config.record_audio !== false && (
                <div className="setting-row">
                  <div className="setting-info">
                    <span className="setting-label">系統聲音錄製來源</span>
                    <span className="setting-desc">選擇目前實際播放遊戲聲音的 Windows 輸出裝置</span>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <div style={{ width: '260px', minWidth: '200px' }}>
                      <Dropdown<string>
                        options={audioDeviceOptions}
                        value={config.audio_output_device_id || ''}
                        onChange={(val) => handleChange('audio_output_device_id', val)}
                      />
                    </div>
                    {onRefreshAudio && (
                      <IconButton
                        icon={RefreshCw}
                        size="md"
                        variant="ghost"
                        tooltip="重新整理音訊裝置"
                        onClick={onRefreshAudio}
                      />
                    )}
                  </div>
                </div>
              )}

              <div className="setting-row no-border">
                <div className="setting-info">
                  <span className="setting-label">本機資料夾與檔案清理</span>
                  <span className="setting-desc">開啟儲存目錄或清理暫存錄影以釋放容量</span>
                </div>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <Button variant="secondary" size="md" icon={FolderOpen} onClick={handleOpenAppData}>
                    開啟本機資料夾
                  </Button>
                  <Button variant="danger" size="md" icon={Trash2} onClick={handleOpenClearModal}>
                    清理暫存檔案
                  </Button>
                </div>
              </div>
            </>
          )}

          {/* Tab 5: 循環錄影 */}
          {activeTab === 'replay' && (
            <>
              <div className="setting-row">
                <div style={{ width: '100%' }}>
                  <PresetSlider
                    preset={config.recording_preset}
                    duration={config.record_duration_sec}
                    fps={config.record_fps}
                    replay={config.replay_buffer_sec}
                    onChangePreset={handlePresetChange}
                  />
                </div>
              </div>

              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">循環錄影保留秒數</span>
                  <span className="setting-desc">持續在記憶體與背景循環保留最近一段遊戲畫面 (最多 30 秒)</span>
                </div>
                <div style={{ width: '160px', minWidth: '140px' }}>
                  <Dropdown<number>
                    options={replayPresetOptions}
                    value={config.replay_buffer_sec || 20}
                    onChange={(val) => handleManualReplayChange(val)}
                  />
                </div>
              </div>

              <div
                style={{
                  padding: '12px 16px',
                  backgroundColor: 'var(--color-surface-card)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.82rem',
                  lineHeight: 1.6,
                  color: 'var(--color-text-secondary)',
                  marginTop: '4px',
                }}
              >
                <div style={{ fontWeight: 700, color: 'var(--color-text-heading)', marginBottom: '4px' }}>
                  循環錄影運作機制說明：
                </div>
                啟動後會像行車記錄器般持續維護滑動時間線，自動循環保留最近一段畫面與聲音；超過設定秒數的內容會自動釋放。按下「儲存循環錄影」或全域快捷鍵僅會導出當下時間窗影片並加密採樣最後
                5 秒影格進行 OCR 辨識，背景循環錄影不會中斷。
              </div>
            </>
          )}

          {/* Tab 6: 全域快捷鍵 */}
          {activeTab === 'hotkeys' && (
            <>
              <div className="setting-row">
                <div className="setting-info">
                  <span className="setting-label">啟用全域快捷鍵</span>
                  <span className="setting-desc">遊戲視窗在前景時依然有效（Ctrl 與 Shift 固定）</span>
                </div>
                <Switch
                  checked={config.global_hotkeys_enabled !== false}
                  onChange={() => handleToggle('global_hotkeys_enabled')}
                />
              </div>

              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '16px',
                  opacity: config.global_hotkeys_enabled !== false ? 1 : 0.4,
                  pointerEvents: config.global_hotkeys_enabled !== false ? 'auto' : 'none',
                  transition: 'opacity 0.2s ease',
                }}
              >
                <div className="setting-row">
                  <div className="setting-info">
                    <span className="setting-label">儲存循環錄影片段快捷鍵</span>
                    <span className="setting-desc">
                      {listeningForHotkey === 'save_replay'
                        ? '請在鍵盤上按下任意按鍵（如 F9、S、R 等，按 Esc 取消）'
                        : '點擊按鈕後直接按下鍵盤按鍵即可自動偵測設定'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      disabled={config.global_hotkeys_enabled === false}
                      className={`ui-btn ui-btn-md ${
                        listeningForHotkey === 'save_replay' ? 'ui-btn-primary' : 'ui-btn-outline'
                      }`}
                      style={{
                        minWidth: '160px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        justifyContent: 'center',
                      }}
                      onClick={() =>
                        setListeningForHotkey(
                          listeningForHotkey === 'save_replay' ? null : 'save_replay'
                        )
                      }
                    >
                      <Keyboard size={16} />
                      <span>
                        {listeningForHotkey === 'save_replay'
                          ? '聆聽按鍵中...'
                          : config.save_replay_hotkey || 'Ctrl+Shift+F9'}
                      </span>
                    </button>
                    <div style={{ width: '100px' }}>
                      <Dropdown<string>
                        disabled={config.global_hotkeys_enabled === false}
                        options={hotkeyKeyOptions}
                        value={saveReplayKey}
                        onChange={(val) => handleChange('save_replay_hotkey', `Ctrl+Shift+${val}`)}
                      />
                    </div>
                  </div>
                </div>

                <div className="setting-row">
                  <div className="setting-info">
                    <span className="setting-label">開始一般錄影快捷鍵</span>
                    <span className="setting-desc">
                      {listeningForHotkey === 'record_video'
                        ? '請在鍵盤上按下任意按鍵（如 F10、R、V 等，按 Esc 取消）'
                        : '點擊按鈕後直接按下鍵盤按鍵即可自動偵測設定'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      disabled={config.global_hotkeys_enabled === false}
                      className={`ui-btn ui-btn-md ${
                        listeningForHotkey === 'record_video' ? 'ui-btn-primary' : 'ui-btn-outline'
                      }`}
                      style={{
                        minWidth: '160px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        justifyContent: 'center',
                      }}
                      onClick={() =>
                        setListeningForHotkey(
                          listeningForHotkey === 'record_video' ? null : 'record_video'
                        )
                      }
                    >
                      <Keyboard size={16} />
                      <span>
                        {listeningForHotkey === 'record_video'
                          ? '聆聽按鍵中...'
                          : config.record_video_hotkey || 'Ctrl+Shift+F10'}
                      </span>
                    </button>
                    <div style={{ width: '100px' }}>
                      <Dropdown<string>
                        disabled={config.global_hotkeys_enabled === false}
                        options={hotkeyKeyOptions}
                        value={recordVideoKey}
                        onChange={(val) => handleChange('record_video_hotkey', `Ctrl+Shift+${val}`)}
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div
                style={{
                  padding: '12px 16px',
                  backgroundColor: 'var(--color-surface-card)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.82rem',
                  lineHeight: 1.6,
                  color: 'var(--color-text-secondary)',
                  marginTop: '4px',
                }}
              >
                <div style={{ fontWeight: 700, color: 'var(--color-text-heading)', marginBottom: '4px' }}>
                  快捷鍵使用說明：
                </div>
                Windows 全域熱鍵透過底層 Win32 API 註冊，不會攔截遊戲內的其他普通操作。建議使用 <code>Ctrl + Shift + S</code> 儲存片段與 <code>Ctrl + Shift + R</code> 開始錄影以避免單鍵衝突。
              </div>
            </>
          )}

          {/* Tab 7: 快捷連結 */}
          {activeTab === 'quicklinks' && (
            <>
              <div className="setting-row no-border">
                <div className="setting-info">
                  <span className="setting-label">快捷連結管理</span>
                  <span className="setting-desc">管理首頁橫向快捷按鈕，可自由編輯、排序與自訂圖示</span>
                </div>
                <Button
                  variant="primary"
                  size="md"
                  icon={Plus}
                  onClick={() => {
                    setEditingLink(null);
                    openLinkModal();
                  }}
                >
                  新增連結
                </Button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {quickLinks.map((item, idx) => (
                  <div
                    key={item.id || idx}
                    className={`quick-link-drag-item ${draggedIndex === idx ? 'dragging' : ''} ${
                      dragOverIndex === idx ? 'drag-over' : ''
                    }`}
                    draggable
                    onDragStart={(e) => handleDragStart(e, idx)}
                    onDragOver={(e) => handleDragOver(e, idx)}
                    onDrop={(e) => handleDrop(e, idx)}
                    onDragEnd={handleDragEnd}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span title="按住拖曳以重新排序" style={{ display: 'flex', alignItems: 'center', cursor: 'grab', flexShrink: 0 }}>
                        <GripVertical size={18} color="var(--color-border-strong)" />
                      </span>
                      <DynamicIcon
                        name={item.icon || 'Globe'}
                        size={18}
                        color="var(--color-primary)"
                      />
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span>{item.title}</span>
                          {item.isDefault && (
                            <Badge variant="default" style={{ fontSize: '0.7rem', padding: '1px 6px' }}>
                              預設
                            </Badge>
                          )}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
                          {item.url}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                      <IconButton
                        icon={ArrowUp}
                        size="sm"
                        variant="ghost"
                        tooltip="向上移動"
                        disabled={idx === 0}
                        onClick={() => handleMoveQuickLink(idx, 'up')}
                      />
                      <IconButton
                        icon={ArrowDown}
                        size="sm"
                        variant="ghost"
                        tooltip="向下移動"
                        disabled={idx === quickLinks.length - 1}
                        onClick={() => handleMoveQuickLink(idx, 'down')}
                      />
                      <IconButton
                        icon={Edit2}
                        size="sm"
                        variant="ghost"
                        tooltip="編輯"
                        onClick={() => {
                          setEditingLink(item);
                          openLinkModal();
                        }}
                      />
                      <IconButton
                        icon={Trash2}
                        size="sm"
                        variant="danger"
                        tooltip="刪除"
                        onClick={() => handleDeleteQuickLink(item.id)}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Tab 8: 關於與更新 */}
          {activeTab === 'about' && (
            <div style={{ fontSize: '0.88rem', color: 'var(--color-text)', lineHeight: 1.8 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px', marginBottom: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <strong>Maple Classic Reporter</strong>
                  <Badge variant="success">v1.3.0 最新版</Badge>
                </div>
                <Button
                  variant="outline"
                  size="md"
                  icon={ExternalLink}
                  onClick={handleOpenGitHub}
                >
                  前往 GitHub 專案
                </Button>
              </div>

              <p style={{ color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
                專為《新楓之谷：經典版》打造之外掛自動化檢舉與事證錄製桌面輔助工具。整合 RapidOCR 本地高精準度文字辨識、Playwright 自動填表送出、WASAPI 系統音訊錄製與 Google Drive 雲端備份。本工具僅協助玩家錄製事證與送出官方檢舉表單，請勿用於任何違反遊戲服務條款之用途。
              </p>

              {/* 進階 / 開發者專用設定區塊 */}
              <div
                style={{
                  marginTop: '16px',
                  padding: '14px 16px',
                  backgroundColor: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-sm)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '12px',
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--color-text-heading)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>開發者模式 (Dry-Run 模擬送出)</span>
                    {config.dev_mode && <Badge variant="event" size="sm">已啟用</Badge>}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                    開啟後，送出檢舉時不會真正透過 Playwright 提交官方表單，僅在系統瀏覽器開啟網頁並記錄事證以供檢視與測試。
                  </div>
                </div>
                <Switch
                  checked={config.dev_mode || false}
                  onChange={() => handleToggle('dev_mode')}
                />
              </div>

              {config.dev_mode && (
                <div
                  style={{
                    marginTop: '12px',
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--color-surface-hover)',
                    border: '1px solid var(--color-border)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                  }}
                >
                  <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--color-text-heading)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>🛠️ 開發者除錯與 LOG 即時檢視</span>
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
                    • <strong>F12 / 右鍵「檢查」</strong>：視窗內已啟用 DevTools 控制台，可即時查看 Console 輸出與 Network 請求。<br />
                    • <strong>後端 Python 日誌</strong>：包含 OCR 辨識、公告制裁比對、系統熱鍵之完整 Debug 訊息。
                  </div>
                  <div style={{ display: 'flex', gap: '8px', marginTop: '4px', flexWrap: 'wrap' }}>
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={FileText}
                      onClick={handleOpenLogFile}
                    >
                      開啟即時日誌 (reporter.log)
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      icon={FolderOpen}
                      onClick={handleOpenLogFolder}
                    >
                      開啟 Log 資料夾
                    </Button>
                  </div>
                </div>
              )}

              <div style={{ marginTop: '16px', fontSize: '0.78rem', color: 'var(--color-text-tertiary)' }}>
                版權所有 © 2026. 遵循 MIT 開源協議。
              </div>
            </div>
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
      <Dialog
        isOpen={clearModalOpen}
        onClose={() => setClearModalOpen(false)}
        title="清理本機暫存錄影"
        titleIcon={Trash2}
        maxWidth="420px"
        footer={
          clearResult ? (
            <Button variant="primary" size="md" onClick={() => setClearModalOpen(false)}>
              完成
            </Button>
          ) : (
            <>
              <Button variant="outline" size="md" onClick={() => setClearModalOpen(false)}>
                取消
              </Button>
              <Button
                variant="danger"
                size="md"
                onClick={handleExecuteClearRecordings}
                disabled={clearingProgress}
              >
                {clearingProgress ? '清理中...' : '確認清理'}
              </Button>
            </>
          )
        }
      >
        {clearResult ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '6px 0' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-status-success)', fontWeight: 600 }}>
              <CheckCircle size={20} />
              <span>清理完成！</span>
            </div>
            <div style={{ fontSize: '0.86rem', color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>
              已成功刪除 <strong>{clearResult.count}</strong> 個本機暫存檔案，共釋放 <strong>{clearResult.size_str || '0 MB'}</strong> 容量。
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '6px 0' }}>
            <div style={{ fontSize: '0.88rem', color: 'var(--color-text)', lineHeight: 1.6 }}>
              確定要清理所有已錄製但尚未刪除的本機暫存影音檔案嗎？
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
              <Info size={14} />
              <span>此操作不會影響已上傳至 Google Drive 或送出的檢舉歷史紀錄。</span>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
}
