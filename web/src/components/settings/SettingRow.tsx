import React from 'react';

export interface SettingRowProps {
  label?: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  noBorder?: boolean;
  className?: string;
}

/** Shared settings row: explanatory copy on the left, one control group on the right. */
export default function SettingRow({
  label,
  description,
  children,
  noBorder = false,
  className = '',
}: SettingRowProps) {
  return (
    <div className={`setting-row${noBorder ? ' no-border' : ''}${className ? ` ${className}` : ''}`}>
      {label || description ? (
        <div className="setting-info">
          {label && <span className="setting-label">{label}</span>}
          {description && <span className="setting-desc">{description}</span>}
        </div>
      ) : null}
      <div className="setting-control">{children}</div>
    </div>
  );
}
