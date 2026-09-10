import { useId, useState } from 'react';
import { PenLine } from 'lucide-react';
import { Button, Textarea } from '../ui';

interface Props {
  names: string[];
  sharedNote: string;
  getOverride: (name: string) => string | undefined;
  disabled: boolean;
  onChange: (name: string, value: string) => void;
  onReset: (name: string) => void;
}

export default function IndividualNoteEditor({
  names,
  sharedNote,
  getOverride,
  disabled,
  onChange,
  onReset,
}: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const contentId = useId();
  const active = selected && names.includes(selected) ? selected : null;
  const customized = active !== null && getOverride(active) !== undefined;
  const customCount = names.filter((name) => getOverride(name) !== undefined).length;
  return (
    <section className="individual-notes" aria-label="個別說明">
      <div className="individual-notes-heading">
        <h3>個別說明</h3>
        <span>{customCount ? `${customCount} 人已自訂` : '所有角色使用共用說明'}</span>
      </div>
      <p>選擇需要補充的角色，其他人仍使用上方說明。</p>
      <div className="individual-notes-surface">
        <div className="individual-note-people" role="group" aria-label="選擇要編輯說明的角色">
          {names.map((name) => (
            <button
              type="button"
              className="report-person-chip"
              key={name}
              aria-label={`編輯 ${name} 的個別說明，${getOverride(name) !== undefined ? '已自訂說明' : '使用共用說明'}`}
              aria-pressed={active === name}
              aria-controls={contentId}
              disabled={disabled}
              onClick={() => setSelected(active === name ? null : name)}
            >
              <span>{name}</span>
              {getOverride(name) !== undefined && <PenLine size={14} aria-hidden="true" />}
            </button>
          ))}
        </div>
        <div id={contentId}>
          {active && (
            <div className="individual-note-content">
              <Textarea
                key={active}
                label={`${active} 的檢舉說明`}
                rows={3}
                value={getOverride(active) ?? sharedNote}
                disabled={disabled}
                onChange={(event) => onChange(active, event.target.value)}
              />
              <div className="individual-note-footer">
                <span role="status">{customized ? '只套用至這名角色' : '目前使用共用說明'}</span>
                {customized && (
                  <Button
                    variant="plain"
                    size="sm"
                    disabled={disabled}
                    onClick={() => onReset(active)}
                  >
                    恢復共用
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
