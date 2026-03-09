import React from 'react';

interface Props {
  value: number; // 0–1
  showLabel?: boolean;
  height?: string;
}

function barColor(v: number) {
  if (v >= 0.8) return 'bg-green-500';
  if (v >= 0.5) return 'bg-amber-500';
  return 'bg-red-500';
}

const ConfidenceBar: React.FC<Props> = ({ value, showLabel = true, height = 'h-2' }) => {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className={`flex-1 overflow-hidden rounded-full bg-slate-200 ${height}`}>
        <div className={`${height} rounded-full ${barColor(value)} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      {showLabel && <span className="min-w-[2.5rem] text-right text-xs font-medium text-slate-600">{pct}%</span>}
    </div>
  );
};

export default ConfidenceBar;
