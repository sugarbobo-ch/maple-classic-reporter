import { useRef } from 'react';
import type { ReactNode } from 'react';
import { X } from 'lucide-react';
import { appendSuspects } from '../../domain/suspects';

interface Props {
  names: string[];
  input: string;
  onNamesChange: (names: string[]) => void;
  onInputChange: (value: string) => void;
  pasteAction?: ReactNode;
}

export default function SuspectTags({
  names,
  input,
  onNamesChange,
  onInputChange,
  pasteAction,
}: Props) {
  const composing = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const commit = (value: string) => {
    onNamesChange(appendSuspects(names, value));
    onInputChange('');
  };
  return (
    <div className="suspect-input-layout">
      <label className="ui-input-label" htmlFor="suspect-tag-input">
        疑似角色 ID
        <span className="suspect-required-mark" aria-hidden="true">*</span>
      </label>
      <div className="suspect-tags">
        <div className="suspect-tags-list">
          {names.map((name) => (
            <span className="suspect-tag report-person-chip" key={name}>
              <span>{name}</span>
              <button
                type="button"
                aria-label={`刪除 ${name}`}
                onClick={() => {
                  onNamesChange(names.filter((item) => item !== name));
                  inputRef.current?.focus();
                }}
              >
                <X size={16} />
              </button>
            </span>
          ))}
          <input
            ref={inputRef}
            id="suspect-tag-input"
            data-testid="report-suspect-id"
            data-has-names={names.length > 0}
            aria-required={names.length === 0}
            value={input}
            placeholder={names.length ? '新增名字' : '輸入或貼上角色 ID'}
            aria-describedby="suspect-tags-help"
            autoComplete="off"
            onCompositionStart={() => {
              composing.current = true;
            }}
            onCompositionEnd={(event) => {
              composing.current = false;
              const value = event.currentTarget.value;
              if (/[\s,，]/u.test(value)) commit(value);
              else onInputChange(value);
            }}
            onChange={(event) => {
              const value = event.target.value;
              if (!composing.current && /[\s,，]/u.test(value)) commit(value);
              else onInputChange(value);
            }}
            onBlur={() => {
              if (!composing.current && input.trim()) commit(input);
            }}
            onKeyDown={(event) => {
              if (composing.current || event.nativeEvent.isComposing || event.keyCode === 229)
                return;
              if (event.key === 'Enter' || /^[\s,，]$/u.test(event.key)) {
                event.preventDefault();
                commit(input);
              }
            }}
            onPaste={(event) => {
              if (composing.current) return;
              event.preventDefault();
              const target = event.currentTarget;
              const value =
                input.slice(0, target.selectionStart ?? input.length) +
                event.clipboardData.getData('text') +
                input.slice(target.selectionEnd ?? input.length);
              commit(value);
            }}
          />
        </div>
        <div className="suspect-input-actions">
          {pasteAction}
          <button
            type="button"
            className="suspect-tags-clear"
            title="全部刪除"
            aria-label="全部刪除"
            disabled={!names.length && !input}
            onClick={() => {
              onNamesChange([]);
              onInputChange('');
              inputRef.current?.focus();
            }}
          >
            <X size={16} />
          </button>
        </div>
      </div>

      <div className="suspect-tags-help" id="suspect-tags-help">
        <span>以空白、逗號或 Enter 加入名字，也可一次貼上多個名字。</span>
        <span role="status">已加入 {names.length} 人</span>
      </div>
    </div>
  );
}
