import { AlertCircle, Zap } from 'lucide-react';
import { RadioGroup, Input, Textarea, Switch } from '../ui';
import { ViolationTemplateItem } from '../../types';

export interface ReportFormSectionProps {
  server: string;
  mapName: string;
  note: string;
  formSubmitHeadless: boolean;
  mapOcrEnabled: boolean;
  ocrMapName: string;
  historicalMaps: string[];
  templates?: ViolationTemplateItem[];
  onServerChange: (val: string) => void;
  onMapNameChange: (val: string) => void;
  onNoteChange: (val: string) => void;
  onFormSubmitHeadlessChange: (val: boolean) => void;
}

export default function ReportFormSection({
  server,
  mapName,
  note,
  formSubmitHeadless,
  mapOcrEnabled,
  ocrMapName,
  historicalMaps,
  templates = [],
  onServerChange,
  onMapNameChange,
  onNoteChange,
  onFormSubmitHeadlessChange,
}: ReportFormSectionProps) {
  return (
    <>
      {/* Step 3: Game Server */}
      <div className="step-block">
        <div className="step-title-row">
          <span className="step-number">3</span>
          <span>外掛角色所在伺服器</span>
        </div>
        <div style={{ padding: '4px 0' }}>
          <RadioGroup
            name="server"
            value={server}
            onChange={onServerChange}
            options={[
              { value: '雪吉拉', label: '雪吉拉' },
              { value: '菇菇寶貝', label: '菇菇寶貝' },
            ]}
          />
        </div>
      </div>

      {/* Step 4: Map Name */}
      <div className="step-block">
        <div className="step-title-row">
          <span className="step-number">4</span>
          <span>外掛角色所在地圖</span>
        </div>
        <Input
          label="所在地圖"
          placeholder="例如：地鐵一號線｜地區01"
          value={mapName}
          onChange={(e) => onMapNameChange(e.target.value)}
          required
          data-testid="report-map-name"
        />

        {(!mapOcrEnabled || ocrMapName || historicalMaps.length > 0) && (
          <>
            {!mapOcrEnabled && (
              <div
                role="status"
                data-testid="ocr-map-disabled-hint"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '0.78rem',
                  color: 'var(--color-status-warning)',
                  lineHeight: 1.3,
                }}
              >
                <AlertCircle size={14} style={{ flexShrink: 0, marginTop: '1px' }} />
                <span>
                  尚未啟用地圖文字辨識（OCR）；地圖名稱不會自動辨識，請手動輸入或從歷史紀錄選擇。
                </span>
              </div>
            )}
            {(ocrMapName || historicalMaps.length > 0) && (
              <>
                <div
                  style={{
                    fontSize: '0.78rem',
                    color: 'var(--color-text-secondary)',
                    marginTop: !mapOcrEnabled ? '4px' : '0px',
                  }}
                >
                  建議地圖：
                </div>
                <div
                  className="chip-group"
                  data-testid="map-suggestion-group"
                  aria-label="地圖建議"
                >
                  {ocrMapName && (
                    <button
                      type="button"
                      className={`chip ${mapName === ocrMapName ? 'active' : ''}`}
                      onClick={() => onMapNameChange(ocrMapName)}
                      data-testid="ocr-map-suggestion"
                      aria-pressed={mapName === ocrMapName}
                    >
                      辨識結果：{ocrMapName}
                    </button>
                  )}
                  {historicalMaps.map((map, idx) => (
                    <button
                      type="button"
                      key={`${map}-${idx}`}
                      className={`chip ${mapName === map ? 'active' : ''}`}
                      onClick={() => onMapNameChange(map)}
                      data-testid={`history-map-suggestion-${idx}`}
                      aria-pressed={mapName === map}
                    >
                      {map}
                    </button>
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>

      {/* Step 5: Notes */}
      <div className="step-block">
        <div className="step-title-row">
          <span className="step-number">5</span>
          <span>違規說明與備註</span>
        </div>
        <Textarea
          label="補充說明"
          placeholder="自動打怪／疑似外掛行為"
          value={note}
          rows={2}
          onChange={(e) => onNoteChange(e.target.value)}
          helperText={
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <AlertCircle size={14} style={{ flexShrink: 0 }} color="var(--color-warning)" />
              <span>提醒：由於官方檢舉表單限制，送出時換行將自動縮減合併為一行。</span>
            </span>
          }
        />
        {templates && templates.length > 0 && (
          <div style={{ marginTop: '8px' }}>
            <div
              style={{
                fontSize: '0.78rem',
                color: 'var(--color-text-secondary)',
                marginBottom: '4px',
              }}
            >
              常用違規範本（點選即可帶入）：
            </div>
            <div className="chip-group" data-testid="violation-template-chips">
              {templates.map((tpl, idx) => {
                const text = tpl.content || tpl.name;
                const isActive = note.trim() === text.trim();
                return (
                  <button
                    type="button"
                    key={`${tpl.name}-${idx}`}
                    className={`chip ${isActive ? 'active' : ''}`}
                    onClick={() => onNoteChange(text)}
                    data-testid={`template-chip-${idx}`}
                    aria-pressed={isActive}
                  >
                    {tpl.name}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Submission Mode: Background Headless Switch */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 14px',
          backgroundColor: 'var(--color-surface)',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Zap size={18} color="var(--color-primary)" />
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>背景靜默送出檢舉</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
              {formSubmitHeadless
                ? '已啟用背景模式：會在後台自動填寫表單'
                : '已關閉背景模式：將開啟可見瀏覽器視窗，展示填表與送出過程'}
            </div>
          </div>
        </div>
        <Switch
          checked={formSubmitHeadless}
          onChange={(val) => onFormSubmitHeadlessChange(val)}
        />
      </div>
    </>
  );
}
