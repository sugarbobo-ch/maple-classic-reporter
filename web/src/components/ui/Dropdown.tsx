import React, { useRef } from 'react';
import ReactDOM from 'react-dom';
import { ChevronDown, Check, LucideIcon } from 'lucide-react';
import { useAnchorPosition, useClickOutside, useDisclosure } from '../../hooks';

export interface DropdownOptionType<T = string | number> {
  value: T;
  label: string;
  icon?: LucideIcon;
}

export interface DropdownProps<T = string | number> {
  label?: React.ReactNode;
  options?: Array<DropdownOptionType<T> | T>;
  value?: T;
  onChange?: (value: T) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  triggerStyle?: React.CSSProperties;
  menuStyle?: React.CSSProperties;
  onOpen?: () => void;
  onClose?: () => void;
}

export default function Dropdown<T extends string | number = string>({
  label = null,
  options = [],
  value,
  onChange,
  placeholder = '請選擇...',
  disabled = false,
  className = '',
  triggerStyle = {},
  menuStyle = {},
  onOpen,
  onClose,
}: DropdownProps<T>) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const { isOpen, toggle, close } = useDisclosure({ onOpen, onClose });

  // Normalize options
  const normalizedOptions: DropdownOptionType<T>[] = options.map((opt) => {
    if (typeof opt === 'object' && opt !== null) {
      return {
        value: (opt as DropdownOptionType<T>).value,
        label: (opt as DropdownOptionType<T>).label ?? String((opt as DropdownOptionType<T>).value),
        icon: (opt as DropdownOptionType<T>).icon,
      };
    }
    return { value: opt as T, label: String(opt), icon: undefined };
  });

  const selectedOption = normalizedOptions.find((opt) => opt.value === value);

  // Position calculation via custom hook
  const { position: menuPosition } = useAnchorPosition(triggerRef, {
    enabled: isOpen,
    estimatedHeight: Math.min(normalizedOptions.length * 40 + 12, 280),
    autoFlip: true,
  });

  // Click outside via custom hook
  useClickOutside([triggerRef, menuRef], close, isOpen);

  const handleSelect = (val: T) => {
    if (onChange) {
      onChange(val);
    }
    close();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;
    if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
      e.preventDefault();
      toggle();
    } else if (e.key === 'Escape') {
      close();
    }
  };

  return (
    <div className={`ui-dropdown-container ${className}`.trim()}>
      {label && (
        <label className="ui-input-label" style={{ marginBottom: '4px' }}>
          {label}
        </label>
      )}

      <button
        type="button"
        ref={triggerRef}
        className={`ui-dropdown-trigger ${isOpen ? 'open' : ''}`}
        disabled={disabled}
        onClick={toggle}
        onKeyDown={handleKeyDown}
        style={triggerStyle}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span className="ui-dropdown-value">
          {selectedOption ? selectedOption.label : placeholder}
        </span>
        <ChevronDown size={16} className="ui-dropdown-arrow" />
      </button>

      {isOpen &&
        ReactDOM.createPortal(
          <div
            ref={menuRef}
            className="ui-dropdown-menu"
            style={{
              top: `${menuPosition.top}px`,
              left: `${menuPosition.left}px`,
              minWidth: `${menuPosition.width}px`,
              width: 'max-content',
              ...menuStyle,
            }}
            role="listbox"
          >
            {normalizedOptions.map((opt, idx) => {
              const isSelected = opt.value === value;
              const OptIcon = opt.icon;
              return (
                <div
                  key={idx}
                  className={`ui-dropdown-option ${isSelected ? 'selected' : ''}`}
                  onClick={() => handleSelect(opt.value)}
                  role="option"
                  aria-selected={isSelected}
                >
                  <div className="ui-dropdown-option-label">
                    {OptIcon && <OptIcon size={14} />}
                    <span>{opt.label}</span>
                  </div>
                  {isSelected && <Check size={14} className="ui-dropdown-check" />}
                </div>
              );
            })}
          </div>,
          document.body
        )}
    </div>
  );
}
