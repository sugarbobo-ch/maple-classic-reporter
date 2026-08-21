import { Clipboard, ShieldCheck, Check, AlertCircle } from 'lucide-react';
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
  const hasCandidates = Boolean(ocrResults.suspect_ids && ocrResults.suspect_ids.length > 0);

  const getSubtext = () => {
    if (whitelistMode) {
      return '選擇略過名單（白名單）：點選要排除的名稱；加入後，之後辨識會自動略過。';
    }
    if (!idOcrEnabled) {
      return hasCandidates
        ? '文字辨識（OCR）結果：已關閉自動填入，點選下方名稱可帶入角色 ID。'
        : '已關閉自動辨識角色 ID，請手動輸入';
    }
    if (hasCandidates) {
      return suspectId
        ? '文字辨識（OCR）結果：已自動填入首選角色 ID，點選下方名稱可快速替換。'
        : '文字辨識（OCR）結果：點選下方名稱即可帶入角色 ID。';
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

      <div className="report-suspect-input-row">
        <Input
          label="疑似角色 ID"
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
      {(subtext || hasCandidates || idOcrEnabled) && (
        <div>
          {subtext && (
            <div
              role={!idOcrEnabled && !whitelistMode ? 'status' : undefined}
              data-testid={!idOcrEnabled && !whitelistMode ? 'ocr-id-disabled-hint' : undefined}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '0.78rem',
                color: whitelistMode
                  ? 'var(--color-status-success)'
                  : !idOcrEnabled
                    ? 'var(--color-status-warning)'
                    : 'var(--color-text-secondary)',
                marginBottom: hasCandidates ? '6px' : '0px',
                lineHeight: 1.3,
                fontWeight: whitelistMode ? 700 : 400,
              }}
            >
              {!idOcrEnabled && !whitelistMode && (
                <AlertCircle size={14} style={{ flexShrink: 0, marginTop: '1px' }} />
              )}
              <span>{subtext}</span>
            </div>
          )}

          {hasCandidates ? (
            <div className={`chip-group ${whitelistMode ? 'whitelist-mode' : ''}`}>
              {ocrResults.suspect_ids.map((id, idx) => {
                const isAlreadyWhitelisted = existingWhitelist.includes(id);
                const isSelectedForWhitelist = selectedForWhitelist.includes(id);
                const isCurrentInputMatch = suspectId === id;

                if (whitelistMode) {
                  return (
                    <button
                      type="button"
                      key={idx}
                      className={`chip whitelist-chip ${isAlreadyWhitelisted ? 'disabled' : ''} ${
                        isSelectedForWhitelist ? 'success' : ''
                      }`}
                      onClick={() => onToggleWhitelistChip(id)}
                      disabled={isAlreadyWhitelisted}
                      aria-pressed={isSelectedForWhitelist}
                    >
                      {isSelectedForWhitelist && <Check size={12} />}
                      <span>{id}</span>
                      {isAlreadyWhitelisted && (
                        <span style={{ fontSize: '0.7rem', opacity: 0.8 }}>(已加入)</span>
                      )}
                    </button>
                  );
                }

                return (
                  <button
                    type="button"
                    key={idx}
                    className={`chip ${isCurrentInputMatch ? 'active' : ''}`}
                    onClick={() => onSuspectIdChange(id)}
                    aria-pressed={isCurrentInputMatch}
                  >
                    {id}
                  </button>
                );
              })}
            </div>
          ) : (
            idOcrEnabled && (
              <div className="chip-group">
                <span style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)' }}>
                  (未辨識到角色 ID，請手動輸入)
                </span>
              </div>
            )
          )}
        </div>
      )}

      {/* Whitelist Action Toolbar at Bottom of Section */}
      <div className="whitelist-action-toolbar">
        {!whitelistMode ? (
          <div className="whitelist-entry-actions">
            <Button
              variant="outline"
              size="sm"
              icon={ShieldCheck}
              onClick={onEnterWhitelistMode}
              style={{ fontSize: '0.8rem' }}
            >
              管理略過名單
            </Button>
          </div>
        ) : (
          <div className="whitelist-selection-toolbar">
            <span className="whitelist-selection-label">正在選取略過名單</span>
            <div className="whitelist-selection-actions">
              <Button variant="outline" size="sm" onClick={onCancelWhitelistMode}>
                取消
              </Button>
              <Button variant="success" size="sm" icon={Check} onClick={onFinishWhitelistMode}>
                完成設定
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
