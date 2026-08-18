import { useState } from 'react';
import { X, LucideIcon } from 'lucide-react';

export interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'prefix'> {
  label?: React.ReactNode;
  value?: string | number;
  prefixIcon?: LucideIcon;
  suffixIcon?: LucideIcon;
  clearable?: boolean;
  error?: string | null;
  wrapperStyle?: React.CSSProperties;
  inputStyle?: React.CSSProperties;
}

export default function Input({
  label,
  value,
  onChange,
  placeholder,
  type = 'text',
  prefixIcon: PrefixIcon,
  suffixIcon: SuffixIcon,
  clearable = false,
  error = null,
  disabled = false,
  required = false,
  className = '',
  wrapperStyle = {},
  inputStyle = {},
  onKeyDown,
  ...props
}: InputProps) {
  const [isFocused, setIsFocused] = useState(false);

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onChange) {
      const syntheticEvent = {
        target: { value: '' },
      } as React.ChangeEvent<HTMLInputElement>;
      onChange(syntheticEvent);
    }
  };

  return (
    <div className={`ui-input-container ${className}`.trim()} style={wrapperStyle}>
      {label && (
        <label className="ui-input-label">
          {label}
          {required && <span style={{ color: 'var(--color-danger)' }}>*</span>}
        </label>
      )}

      <div
        className={`ui-input-wrapper ${isFocused ? 'focused' : ''} ${error ? 'error' : ''} ${
          disabled ? 'disabled' : ''
        }`.trim()}
      >
        {PrefixIcon && (
          <span className="ui-input-prefix">
            <PrefixIcon size={16} />
          </span>
        )}

        <input
          type={type}
          className="ui-input-field"
          value={value ?? ''}
          placeholder={placeholder}
          disabled={disabled}
          required={required}
          style={inputStyle}
          onChange={onChange}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          onKeyDown={onKeyDown}
          {...props}
        />

        {clearable && value && !disabled && (
          <span className="ui-input-clear" onClick={handleClear} title="清除">
            <X size={14} />
          </span>
        )}

        {SuffixIcon && (
          <span className="ui-input-suffix">
            <SuffixIcon size={16} />
          </span>
        )}
      </div>

      {error && <span className="ui-input-error-msg">{error}</span>}
    </div>
  );
}
