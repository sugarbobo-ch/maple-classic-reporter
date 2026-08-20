import React from 'react';
import { LucideIcon } from 'lucide-react';
import Tooltip from './Tooltip';
import { Placement } from '../../hooks';

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: LucideIcon;
  size?: 'sm' | 'md' | 'lg';
  variant?:
    'default' | 'primary' | 'secondary' | 'outline' | 'danger' | 'success' | 'ghost' | 'plain';
  active?: boolean;
  tooltip?: string;
  tooltipPlacement?: Placement;
  tooltipOnFocus?: boolean;
  iconSize?: number;
}

export default function IconButton({
  icon: Icon,
  size = 'md',
  variant = 'default',
  active = false,
  tooltip,
  tooltipPlacement = 'bottom',
  tooltipOnFocus = true,
  iconSize,
  className = '',
  disabled = false,
  type = 'button',
  title,
  'aria-label': ariaLabel,
  onClick,
  ...props
}: IconButtonProps) {
  const computedIconSize = iconSize || (size === 'sm' ? 14 : size === 'lg' ? 20 : 16);

  const variantClass =
    variant === 'default' ? 'ui-btn-icon' : `ui-btn ui-btn-${variant} ui-btn-icon`;
  const sizeClass = size === 'sm' ? 'ui-btn-sm' : size === 'lg' ? 'ui-btn-lg' : '';
  const activeClass = active ? 'active' : '';

  // Use tooltip prop, fallback to aria-label or title
  const effectiveLabel = ariaLabel || tooltip || title;

  const buttonElement = (
    <button
      type={type}
      className={`${variantClass} ${sizeClass} ${activeClass} ${className}`.trim()}
      disabled={disabled}
      onClick={onClick}
      aria-label={effectiveLabel || undefined}
      {...props}
    >
      <Icon size={computedIconSize} aria-hidden="true" />
    </button>
  );

  if (effectiveLabel) {
    return (
      <Tooltip content={effectiveLabel} placement={tooltipPlacement} showOnFocus={tooltipOnFocus}>
        {buttonElement}
      </Tooltip>
    );
  }

  return buttonElement;
}
