import { useState } from 'react';

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: React.ReactNode;
  value?: string;
  helperText?: React.ReactNode;
  error?: string | null;
  wrapperStyle?: React.CSSProperties;
  textareaStyle?: React.CSSProperties;
}

export default function Textarea({
  label,
  value,
  onChange,
  placeholder,
  rows = 3,
  helperText,
  error = null,
  disabled = false,
  required = false,
  className = '',
  wrapperStyle = {},
  textareaStyle = {},
  onKeyDown,
  ...props
}: TextareaProps) {
  const [isFocused, setIsFocused] = useState(false);

  return (
    <div
      className={`ui-input-container ${className}`.trim()}
      style={wrapperStyle}
    >
      {label && (
        <label className="ui-input-label">
          {label}
          {required && <span style={{ color: 'var(--color-danger)' }}>*</span>}
        </label>
      )}

      <div
        className={`ui-textarea-wrapper ${isFocused ? 'focused' : ''} ${
          error ? 'error' : ''
        } ${disabled ? 'disabled' : ''}`.trim()}
      >
        <textarea
          rows={rows}
          className="ui-textarea-field"
          value={value ?? ''}
          placeholder={placeholder}
          disabled={disabled}
          required={required}
          style={textareaStyle}
          onChange={onChange}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          onKeyDown={onKeyDown}
          {...props}
        />
      </div>

      {helperText && !error && (
        <div className="ui-input-helper-text">{helperText}</div>
      )}

      {error && <span className="ui-input-error-msg">{error}</span>}
    </div>
  );
}
