import { Clipboard, ShieldCheck, Check } from 'lucide-react';
import { Input, Button } from '../ui';
import { OcrResultData } from '../../types';

export interface SuspectSelectorProps {
  suspectId: string;
  whitelistMode: boolean;
  ocrResults: OcrResultData;
  existingWhitelist: string[];
  selectedForWhitelist: string[];
  idOcrEnabled?: boolean;
  onSuspectIdChange: (val: string) => void;
  onPasteClipboard: () => void;
  onToggleWhitelistChip: (id: string) => void;
  onEnterWhitelistMode: () => void;
  onCancelWhitelistMode: () => void;
  onFinishWhitelistMode: () => void;
}

export default function SuspectSelector({
  suspectId,
  whitelistMode,
  ocrResults,
  existingWhitelist,
  selectedForWhitelist,
  idOcrEnabled = true,
  onSuspectIdChange,
  onPasteClipboard,
  onToggleWhitelistChip,
  onEnterWhitelistMode,
  onCancelWhitelistMode,
  onFinishWhitelistMode,
}: SuspectSelectorProps) {
  const getSubtext = () => {
    if (whitelistMode) {
      return '選擇白名單：點選要排除的名稱；加入後，往後辨識將自動略過。';
    }
    if (!idOcrEnabled) {
      return ocrResults.suspect_ids && ocrResults.suspect_ids.length > 0
        ? 'OCR 辨識結果：已關閉自動填入，點選下方名稱可帶入角色 ID。'
        : '（已關閉自動辨識角色 ID，請手動輸入）';
    }
    if (ocrResults.suspect_ids && ocrResults.suspect_ids.length > 0) {
      return suspectId
        ? 'OCR 辨識結果：已自動填入首選角色 ID，點選下方名稱可快速替換。'
        : 'OCR 辨識結果：點選下方名稱即可帶入角色 ID。';
    }
    return '';
  };

  const subtext = getSubtext();

  return (
    <div className="step-block">
      <div className="step-title-row">
        <span className="step-number">2</span>
        <span>外掛玩家角色 ID</span>
      </div>

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <Input
          placeholder="請輸入或點選下方候選角色 ID"
          value={suspectId}
          onChange={(e) => onSuspectIdChange(e.target.value)}
          required
          data-testid="report-suspect-id"
        />
        <Button variant="secondary" size="md" icon={Clipboard} onClick={onPasteClipboard}>
          貼上
        </Button>
      </div>

      {/* Suggestions Chips Area */}
      <div style={{ marginTop: '2px' }}>
        {subtext && (
          <div
            style={{
              fontSize: '0.78rem',
              color: whitelistMode
                ? 'var(--color-status-success)'
                : !idOcrEnabled
                  ? 'var(--color-status-warning)'
                  : 'var(--color-text-secondary)',
              marginBottom: '6px',
              fontWeight: whitelistMode ? 700 : 400,
            }}
          >
            {subtext}
          </div>
        )}

        <div className={`chip-group ${whitelistMode ? 'whitelist-mode' : ''}`}>
          {ocrResults.suspect_ids && ocrResults.suspect_ids.length > 0 ? (
            ocrResults.suspect_ids.map((id, idx) => {
              const isAlreadyWhitelisted = existingWhitelist.includes(id);
              const isSelectedForWhitelist = selectedForWhitelist.includes(id);
              const isCurrentInputMatch = suspectId === id;

              if (whitelistMode) {
                return (
                  <div
                    key={idx}
                    className={`chip whitelist-chip ${isAlreadyWhitelisted ? 'disabled' : ''} ${
                      isSelectedForWhitelist ? 'success' : ''
                    }`}
                    onClick={() => onToggleWhitelistChip(id)}
                  >
                    {isSelectedForWhitelist && <Check size={12} />}
                    <span>{id}</span>
                    {isAlreadyWhitelisted && (
                      <span style={{ fontSize: '0.7rem', opacity: 0.8 }}>(已加入)</span>
                    )}
                  </div>
                );
              }

              return (
                <div
                  key={idx}
                  className={`chip ${isCurrentInputMatch ? 'active' : ''}`}
                  onClick={() => onSuspectIdChange(id)}
                >
                  {id}
                </div>
              );
            })
          ) : (
            <span style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)' }}>
              {!idOcrEnabled
                ? '(已關閉自動辨識角色 ID，請手動輸入)'
                : '(未辨識到角色 ID，請手動輸入)'}
            </span>
          )}
        </div>
      </div>

      {/* Whitelist Action Toolbar at Bottom of Section */}
      <div
        style={{
          marginTop: '4px',
          paddingTop: '8px',
          borderTop: '1px dashed var(--color-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        {!whitelistMode ? (
          <Button
            variant="outline"
            size="sm"
            icon={ShieldCheck}
            onClick={onEnterWhitelistMode}
            style={{ fontSize: '0.8rem' }}
          >
            從辨識結果管理白名單
          </Button>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--color-status-success)', fontWeight: 600 }}>
              正在選取白名單名單
            </span>
            <div style={{ display: 'flex', gap: '6px' }}>
              <Button variant="outline" size="sm" onClick={onCancelWhitelistMode}>
                取消
              </Button>
              <Button
                variant="success"
                size="sm"
                icon={Check}
                onClick={onFinishWhitelistMode}
              >
                完成設定
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
