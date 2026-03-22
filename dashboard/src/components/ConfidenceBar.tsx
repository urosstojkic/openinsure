import React from 'react';

interface Props {
  value: number; // 0–1
  showLabel?: boolean;
  height?: string;
}

function barColor(v: number) {
  if (v >= 0.8) return 'from-emerald-400 to-emerald-500';
  if (v >= 0.5) return 'from-amber-400 to-amber-500';
  return 'from-red-400 to-red-500';
}

function trackColor(v: number) {
  if (v >= 0.8) return 'bg-emerald-100';
  if (v >= 0.5) return 'bg-amber-100';
  return 'bg-red-100';
}

const ConfidenceBar: React.FC<Props> = ({ value, showLabel = true, height = 'h-2' }) => {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2.5">
      <div className={`flex-1 overflow-hidden rounded-full ${trackColor(value)} ${height}`}>
        <div
          className={`${height} rounded-full bg-gradient-to-r ${barColor(value)} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className="min-w-[2.5rem] text-right text-xs font-semibold tabular-nums text-slate-600">
          {pct}%
        </span>
      )}
    </div>
  );
};

export default ConfidenceBar;
