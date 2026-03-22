import React from 'react';

interface Props {
  confidence: number;
  humanOversight: 'none' | 'recommended' | 'required';
  size?: 'sm' | 'md';
}

function getColor(confidence: number, oversight: string): 'green' | 'amber' | 'red' {
  if (confidence < 0.5 || oversight === 'required') return 'red';
  if (confidence < 0.8 || oversight === 'recommended') return 'amber';
  return 'green';
}

const colorMap = {
  green: { bg: 'bg-emerald-500', ring: 'ring-emerald-500/20', glow: 'shadow-emerald-500/30 shadow-sm', label: 'Low Risk' },
  amber: { bg: 'bg-amber-500',   ring: 'ring-amber-500/20',   glow: 'shadow-amber-500/30 shadow-sm',   label: 'Review' },
  red:   { bg: 'bg-red-500',     ring: 'ring-red-500/20',     glow: 'shadow-red-500/30 shadow-sm',     label: 'Action Needed' },
};

const TrafficLight: React.FC<Props> = ({ confidence, humanOversight, size = 'md' }) => {
  const color = getColor(confidence, humanOversight);
  const { bg, ring, glow, label } = colorMap[color];
  const dim = size === 'sm' ? 'h-2.5 w-2.5' : 'h-3.5 w-3.5';

  return (
    <span className="inline-flex items-center gap-1.5" title={label}>
      <span className={`${dim} rounded-full ${bg} ${glow} ring-2 ${ring}`} />
      {size === 'md' && (
        <span className="text-[11px] font-medium text-slate-600">{label}</span>
      )}
    </span>
  );
};

export default TrafficLight;
