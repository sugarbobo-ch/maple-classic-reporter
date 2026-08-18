import React from 'react';
import { LucideIcon } from 'lucide-react';

export type BadgeVariant =
  | 'default'
  | 'primary'
  | 'success'
  | 'danger'
  | 'warning'
  | 'info'
  | 'important'
  | 'update'
  | 'event'
  | 'outline';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  children?: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
  icon?: LucideIcon;
  dot?: boolean;
  className?: string;
}

export default function Badge({
  children,
  variant = 'default',
  size = 'sm',
  icon: Icon,
  dot = false,
  className = '',
  ...props
}: BadgeProps) {
  const variantClass = `ui-badge-${variant}`;
  const sizeClass = `ui-badge-${size}`;

  return (
    <span className={`ui-badge ${variantClass} ${sizeClass} ${className}`.trim()} {...props}>
      {dot && (
        <span
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            backgroundColor: 'currentColor',
          }}
        />
      )}
      {Icon && <Icon size={size === 'sm' ? 12 : 14} />}
      {children}
    </span>
  );
}
