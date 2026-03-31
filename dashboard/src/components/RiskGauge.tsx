import React from 'react';

interface Props {
  /** Value 0–100 */
  value: number;
  /** Size in px (default 120) */
  size?: number;
  /** Label below the value */
  label?: string;
  /** Stroke width (default 10) */
  strokeWidth?: number;
  /** Override color zones: [green, yellow, red] thresholds */
  thresholds?: [number, number];
}

/**
 * Circular SVG gauge — color-coded green / yellow / red.
 * Reused for risk scores, fraud scores, severity indicators.
 */
const RiskGauge: React.FC<Props> = ({
  value,
  size = 120,
  label,
  strokeWidth = 10,
  thresholds = [40, 70],
}) => {
  const clamped = Math.max(0, Math.min(100, value));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;

  const color =
    clamped < thresholds[0]
      ? '#10b981' // emerald-500
      : clamped < thresholds[1]
      ? '#f59e0b' // amber-500
      : '#ef4444'; // red-500

  const bgRing =
    clamped < thresholds[0]
      ? 'rgba(16,185,129,0.10)'
      : clamped < thresholds[1]
      ? 'rgba(245,158,11,0.10)'
      : 'rgba(239,68,68,0.10)';

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          {/* Background ring */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={bgRing}
            strokeWidth={strokeWidth}
          />
          {/* Filled arc */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-700 ease-out"
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold tabular-nums" style={{ color }}>
            {Math.round(clamped)}
          </span>
          {label && (
            <span className="text-[10px] font-medium text-slate-400 mt-0.5">
              {label}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default RiskGauge;
