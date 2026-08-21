import React from 'react';

export interface CircularProgressProps {
  value: number; // 0 to 1
  size?: number;
  strokeWidth?: number;
  trackColor?: string;
  progressColor?: string;
  transitionDuration?: string;
  centerDot?: boolean;
  centerDotRadius?: number;
  centerDotColor?: string;
  isClockHands?: boolean;
  isCancelIcon?: boolean;
  children?: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  ariaLabel?: string;
  ariaValueNow?: number;
}

export default function CircularProgress({
  value,
  size = 32,
  strokeWidth = 3,
  trackColor = 'rgba(200, 160, 96, 0.25)',
  progressColor = 'var(--color-primary)',
  transitionDuration = '0.25s linear',
  centerDot = false,
  centerDotRadius,
  centerDotColor,
  isClockHands = false,
  isCancelIcon = false,
  children,
  className = '',
  style,
  ariaLabel,
  ariaValueNow,
}: CircularProgressProps) {
  const center = size / 2;
  const radius = Math.max(1, (size - strokeWidth) / 2);
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(1, isNaN(value) ? 0 : value));
  const strokeDashoffset = circumference * (1 - clamped);
  const dotR = centerDotRadius || Math.max(2, radius * 0.45);

  return (
    <div
      className={`circular-progress-wrap ${className}`}
      role={ariaLabel ? 'progressbar' : undefined}
      aria-label={ariaLabel}
      aria-valuemin={ariaLabel ? 0 : undefined}
      aria-valuemax={ariaLabel ? 100 : undefined}
      aria-valuenow={ariaLabel ? ariaValueNow ?? clamped * 100 : undefined}
      style={{
        width: size,
        height: size,
        ...style,
      }}
    >
      <svg
        className="circular-progress-svg"
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
      >
        {/* Background Track Circle */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={trackColor}
          strokeWidth={strokeWidth}
        />

        {/* Dynamic Progress Arc (rotated -90deg so it starts at 12 o'clock) */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={progressColor}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          transform={`rotate(-90 ${center} ${center})`}
          style={{
            transition: `stroke-dashoffset ${transitionDuration}, stroke 0.2s ease`,
          }}
        />

        {/* Concentric Center Dot */}
        {centerDot && (
          <circle
            cx={center}
            cy={center}
            r={dotR}
            fill={centerDotColor || progressColor}
          />
        )}

        {/* Concentric Clock Hands */}
        {isClockHands && (
          <g stroke={progressColor} strokeWidth={1.5} strokeLinecap="round">
            <line x1={center} y1={center} x2={center} y2={center - radius * 0.55} />
            <line x1={center} y1={center} x2={center + radius * 0.45} y2={center} />
            <circle cx={center} cy={center} r={1.2} fill={progressColor} />
          </g>
        )}

        {/* Concentric Cancel X Icon */}
        {isCancelIcon && (
          <g stroke={progressColor} strokeWidth={2.4} strokeLinecap="round">
            <line
              x1={center - radius * 0.38}
              y1={center - radius * 0.38}
              x2={center + radius * 0.38}
              y2={center + radius * 0.38}
            />
            <line
              x1={center + radius * 0.38}
              y1={center - radius * 0.38}
              x2={center - radius * 0.38}
              y2={center + radius * 0.38}
            />
          </g>
        )}
      </svg>

      {children && <div className="circular-progress-content">{children}</div>}
    </div>
  );
}
