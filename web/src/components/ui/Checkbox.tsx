import React from 'react';

export type CheckboxVariant = 'primary' | 'danger';

export interface CheckboxProps extends Omit<
  React.InputHTMLAttributes<HTMLInputElement>,
  'type' | 'checked' | 'defaultChecked' | 'onChange' | 'className'
> {
  checked?: boolean;
  onChange?: (checked: boolean) => void;
  label?: React.ReactNode;
  variant?: CheckboxVariant;
  className?: string;
}

export function Checkbox({
  checked = false,
  onChange,
  label,
  variant = 'primary',
  disabled = false,
  className = '',
  ...inputProps
}: CheckboxProps) {
  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    onChange?.(event.target.checked);
  };

  return (
    <label
      className={`ui-checkbox ${checked ? 'checked' : ''} ${disabled ? 'disabled' : ''} ${variant === 'danger' ? 'ui-checkbox-danger' : ''} ${className}`.trim()}
    >
      <span className="ui-checkbox-box" aria-hidden="true">
        <svg
          width="18"
          height="18"
          viewBox="0 0 18 18"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect
            className="ui-checkbox-rect"
            x="1.5"
            y="1.5"
            width="15"
            height="15"
            rx="3"
            stroke="currentColor"
            strokeWidth="2"
          />
          <path
            className="ui-checkbox-check"
            d="M4.5 9.25L7.25 12L13.5 5.75"
            stroke="var(--color-primary-text)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      {label ? <span className="ui-checkbox-label">{label}</span> : null}
      <input
        {...inputProps}
        className="ui-checkbox-input"
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={handleChange}
      />
    </label>
  );
}

export default Checkbox;
