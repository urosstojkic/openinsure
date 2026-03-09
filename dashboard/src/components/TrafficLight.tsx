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
  green: { bg: 'bg-green-500', ring: 'ring-green-300', label: 'Low Risk' },
  amber: { bg: 'bg-amber-500', ring: 'ring-amber-300', label: 'Review' },
  red:   { bg: 'bg-red-500',   ring: 'ring-red-300',   label: 'Action Needed' },
};

const TrafficLight: React.FC<Props> = ({ confidence, humanOversight, size = 'md' }) => {
  const color = getColor(confidence, humanOversight);
  const { bg, ring, label } = colorMap[color];
  const dim = size === 'sm' ? 'h-3 w-3' : 'h-4 w-4';

  return (
    <span className="inline-flex items-center gap-1.5" title={label}>
      <span className={`${dim} rounded-full ${bg} ring-2 ${ring}`} />
      {size === 'md' && (
        <span className="text-xs text-slate-600">{label}</span>
      )}
    </span>
  );
};

export default TrafficLight;
