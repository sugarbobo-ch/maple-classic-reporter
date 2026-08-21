import { Plus, Edit2, Trash2, AlertCircle } from 'lucide-react';
import { Switch, Dropdown, Input, Textarea, Button } from '../ui';
import { AppConfig, DropdownOption, ViolationTemplateItem } from '../../types';

export interface GeneralTabProps {
  config: AppConfig;
  serverOptions: DropdownOption<string>[];
  defaultMap: string;
  defaultNote: string;
  templates: ViolationTemplateItem[];
  selectedTemplateIndex: number;
  whitelist: string[];
  whitelistInput: string;
  onUpdateConfig: (key: keyof AppConfig, value: unknown) => void;
  onDefaultMapChange: (val: string) => void;
  onWhitelistInputChange: (val: string) => void;
  onAddWhitelist: () => void;
  onRemoveWhitelist: (item: string) => void;
  onSelectTemplate: (idx: number) => void;
  onOpenAddTemplate: () => void;
  onOpenEditTemplate: (idx: number) => void;
  onDeleteTemplate: (idx: number) => void;
}

export default function GeneralTab({
  config,
  serverOptions,
  defaultMap,
  defaultNote,
  templates,
  selectedTemplateIndex,
  whitelist,
  whitelistInput,
  onUpdateConfig,
  onDefaultMapChange,
  onWhitelistInputChange,
  onAddWhitelist,
  onRemoveWhitelist,
  onSelectTemplate,
  onOpenAddTemplate,
  onOpenEditTemplate,
  onDeleteTemplate,
}: GeneralTabProps) {
  const handleToggle = (key: keyof AppConfig) => {
    onUpdateConfig(key, !config[key]);
  };

  return (
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
            onChange={(val) => onUpdateConfig('default_server', val)}
          />
        </div>
      </div>

      <div className="setting-row">
        <div className="setting-info">
          <span className="setting-label">預設所在地圖名稱</span>
          <span className="setting-desc">辨識未能確定時自動預填</span>
        </div>
        <div style={{ width: '220px', minWidth: '180px' }}>
          <Input
            value={defaultMap}
            onChange={(e) => onDefaultMapChange(e.target.value)}
          />
        </div>
      </div>

      {/* 違規說明與範本管理（附底部橫向分隔線） */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          paddingBottom: '12px',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '8px',
          }}
        >
          <div className="setting-info">
            <span className="setting-label">違規說明與範本管理</span>
            <span className="setting-desc">管理常用違規備註範本並套用</span>
          </div>
          <Button variant="secondary" size="sm" icon={Plus} onClick={onOpenAddTemplate}>
            新增範本
          </Button>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ width: '220px', minWidth: '180px' }}>
            <Dropdown<number>
              options={templates.map((t, idx) => ({ value: idx, label: t.name }))}
              value={selectedTemplateIndex}
              onChange={(idx) => onSelectTemplate(idx)}
            />
          </div>
          <Button
            variant="outline"
            size="md"
            icon={Edit2}
            onClick={() => onOpenEditTemplate(selectedTemplateIndex)}
          >
            編輯
          </Button>
          <Button
            variant="danger"
            size="md"
            icon={Trash2}
            onClick={() => onDeleteTemplate(selectedTemplateIndex)}
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

      {/* 白名單管理（附底部橫向分隔線） */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          paddingBottom: '12px',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <div className="setting-info">
          <span className="setting-label">略過名單（白名單）角色 ID 管理</span>
          <span className="setting-desc">輸入逗號分隔文字或按 Enter，可加入多個角色 ID；辨識時會自動略過</span>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '200px' }}>
            <Input
              placeholder="輸入角色 ID (例如: player01, player02)"
              value={whitelistInput}
              onChange={(e) => onWhitelistInputChange(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && onAddWhitelist()}
            />
          </div>
          <Button variant="secondary" size="md" onClick={onAddWhitelist} icon={Plus}>
            新增
          </Button>
        </div>

        <div className="chip-group" style={{ margin: '4px 0 0 0' }}>
          {whitelist.map((item, idx) => (
            <div key={idx} className="chip">
              <span>{item}</span>
              <button
                type="button"
                className="chip-remove-button"
                onClick={() => onRemoveWhitelist(item)}
                aria-label={`移除略過名單 ${item}`}
              >
                ×
              </button>
            </div>
          ))}
          {whitelist.length === 0 && (
            <span style={{ fontSize: '0.78rem', color: 'var(--color-text-tertiary)' }}>
              尚無略過名單成員
            </span>
          )}
        </div>
      </div>

      <div className="setting-row">
        <div className="setting-info">
          <span className="setting-label">背景靜默送出檢舉</span>
          <span className="setting-desc">啟用時會在背景自動填寫表單；關閉時會開啟瀏覽器展示填寫過程</span>
        </div>
        <Switch
          checked={config.form_submit_headless !== false}
          onChange={() => handleToggle('form_submit_headless')}
        />
      </div>

      <div className="setting-row">
        <div className="setting-info">
          <span className="setting-label">啟動時自動更新官方處分公告</span>
          <span className="setting-desc">啟動且距離上次完整檢查超過 6 小時時，會在背景更新官方最新處分名單</span>
        </div>
        <Switch
          checked={config.auto_check_sanction_status !== false}
          onChange={() => handleToggle('auto_check_sanction_status')}
        />
      </div>

      <div className="setting-row no-border">
        <div className="setting-info">
          <span className="setting-label">自動刪除已確認檢舉證據</span>
          <span className="setting-desc">表單提交與上傳成功後，自動刪除本機暫存影片</span>
        </div>
        <Switch
          checked={config.auto_delete_after_upload || false}
          onChange={() => handleToggle('auto_delete_after_upload')}
        />
      </div>
    </>
  );
}
