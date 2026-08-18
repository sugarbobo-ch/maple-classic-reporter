import React, { createContext, useContext } from 'react';

export interface RadioContextType {
  name?: string;
  value?: string | number;
  onChange?: (value: string | number) => void;
  disabled?: boolean;
}

const RadioContext = createContext<RadioContextType | null>(null);

export interface RadioProps {
  value: string | number;
  checked?: boolean;
  onChange?: (checked: boolean) => void;
  label?: React.ReactNode;
  disabled?: boolean;
  name?: string;
  className?: string;
}

export function Radio({
  value,
  checked: controlledChecked,
  onChange: controlledOnChange,
  label,
  disabled: itemDisabled,
  name: itemName,
  className = '',
  ...props
}: RadioProps) {
  const group = useContext(RadioContext);

  const isChecked = group ? group.value === value : (controlledChecked ?? false);
  const isDisabled = group?.disabled || itemDisabled || false;
  const name = group?.name || itemName;

  const handleClick = () => {
    if (isDisabled) return;
    if (group?.onChange) {
      group.onChange(value);
    } else if (controlledOnChange) {
      controlledOnChange(true);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (isDisabled) return;
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      handleClick();
    }
  };

  return (
    <label
      className={`ui-radio ${isChecked ? 'checked' : ''} ${isDisabled ? 'disabled' : ''} ${className}`.trim()}
      onClick={handleClick}
      tabIndex={isDisabled ? -1 : 0}
      onKeyDown={handleKeyDown}
      role="radio"
      aria-checked={isChecked}
      {...props}
    >
      <span className="ui-radio-circle">
        <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle
            className="ui-radio-outer"
            cx="10"
            cy="10"
            r="8"
            stroke="currentColor"
            strokeWidth="2"
            fill="var(--color-surface-card)"
          />
          <circle
            className="ui-radio-inner"
            cx="10"
            cy="10"
            r="4.25"
            fill="var(--color-primary)"
          />
        </svg>
      </span>
      {label && <span className="ui-radio-label">{label}</span>}
      <input
        type="radio"
        name={name}
        value={value}
        checked={isChecked}
        disabled={isDisabled}
        onChange={() => {}}
        style={{ display: 'none' }}
      />
    </label>
  );
}

export interface RadioOption<T = string | number> {
  value: T;
  label: React.ReactNode;
  disabled?: boolean;
}

export interface RadioGroupProps<T = string | number> {
  name?: string;
  value?: T;
  onChange?: (value: T) => void;
  options?: RadioOption<T>[];
  children?: React.ReactNode;
  direction?: 'horizontal' | 'vertical';
  disabled?: boolean;
  className?: string;
}

export function RadioGroup<T extends string | number = string>({
  name,
  value,
  onChange,
  options,
  children,
  direction = 'horizontal',
  disabled = false,
  className = '',
}: RadioGroupProps<T>) {
  return (
    <RadioContext.Provider
      value={{
        name,
        value,
        onChange: onChange as (val: string | number) => void,
        disabled,
      }}
    >
      <div className={`ui-radio-group ${direction} ${className}`.trim()} role="radiogroup">
        {options
          ? options.map((opt) => (
              <Radio
                key={String(opt.value)}
                value={opt.value}
                label={opt.label}
                disabled={opt.disabled || disabled}
              />
            ))
          : children}
      </div>
    </RadioContext.Provider>
  );
}

export default Radio;
