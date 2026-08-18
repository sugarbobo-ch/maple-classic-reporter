import React from 'react';

export interface SwitchProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onChange'> {
  checked?: boolean;
  onChange?: (checked: boolean) => void;
  label?: React.ReactNode;
  disabled?: boolean;
  className?: string;
}

export default function Switch({
  checked = false,
  onChange,
  label = null,
  disabled = false,
  className = '',
  ...props
}: SwitchProps) {
  const handleToggle = () => {
    if (!disabled && onChange) {
      onChange(!checked);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      handleToggle();
    }
  };

  return (
    <div
      className={`ui-switch-container ${disabled ? 'disabled' : ''} ${className}`.trim()}
      onClick={handleToggle}
      role="switch"
      aria-checked={checked}
      tabIndex={disabled ? -1 : 0}
      onKeyDown={handleKeyDown}
      {...props}
    >
      <div className={`ui-switch-track ${checked ? 'checked' : ''}`}>
        <div className="ui-switch-thumb" />
      </div>
      {label && <span className="ui-switch-label">{label}</span>}
    </div>
  );
}
