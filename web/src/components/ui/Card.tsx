import React from 'react';
import { LucideIcon } from 'lucide-react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
  variant?: 'default' | 'raised' | 'inner' | 'primary' | 'interactive';
  headerTitle?: React.ReactNode;
  title?: any;
  titleIcon?: LucideIcon;
  headerAction?: React.ReactNode;
  footer?: React.ReactNode;
}

export default function Card({
  children,
  variant = 'default',
  headerTitle = null,
  title = null,
  titleIcon: TitleIcon,
  headerAction = null,
  footer = null,
  className = '',
  onClick,
  style = {},
  ...props
}: CardProps) {
  const variantClass =
    {
      default: 'ui-card',
      raised: 'ui-card ui-card-raised',
      inner: 'ui-card ui-card-inner',
      primary: 'ui-card ui-card-primary',
      interactive: 'ui-card ui-card-interactive',
    }[variant] || 'ui-card';

  // Only render a card header section if headerTitle is explicitly set,
  // or if titleIcon/headerAction is provided.
  const effectiveHeaderTitle = headerTitle || (TitleIcon || headerAction ? title : null);

  return (
    <div
      className={`${variantClass} ${className}`.trim()}
      onClick={onClick}
      style={style}
      {...props}
    >
      {(effectiveHeaderTitle || headerAction) && (
        <div className="ui-card-header">
          {effectiveHeaderTitle && (
            <div className="ui-card-title">
              {TitleIcon && <TitleIcon size={16} color="var(--color-primary)" />}
              <span>{effectiveHeaderTitle}</span>
            </div>
          )}
          {headerAction && <div>{headerAction}</div>}
        </div>
      )}

      {children}

      {footer && <div style={{ marginTop: '12px' }}>{footer}</div>}
    </div>
  );
}

Card.Header = function CardHeader({
  children,
  className = '',
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`ui-card-header ${className}`.trim()}>{children}</div>;
};

Card.Title = function CardTitle({
  children,
  icon: Icon,
  className = '',
}: {
  children: React.ReactNode;
  icon?: LucideIcon;
  className?: string;
}) {
  return (
    <div className={`ui-card-title ${className}`.trim()}>
      {Icon && <Icon size={16} color="var(--color-primary)" />}
      <span>{children}</span>
    </div>
  );
};
