import React from 'react';

type Variant =
  | 'blue' | 'yellow' | 'orange' | 'green' | 'purple' | 'red' | 'gray'
  | 'cyan' | 'indigo';

const styles: Record<Variant, { dot: string; badge: string }> = {
  blue:   { dot: 'bg-blue-500',    badge: 'bg-blue-50 text-blue-700 ring-1 ring-blue-600/10' },
  yellow: { dot: 'bg-amber-500',   badge: 'bg-amber-50 text-amber-700 ring-1 ring-amber-600/10' },
  orange: { dot: 'bg-orange-500',  badge: 'bg-orange-50 text-orange-700 ring-1 ring-orange-600/10' },
  green:  { dot: 'bg-emerald-500', badge: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/10' },
  purple: { dot: 'bg-purple-500',  badge: 'bg-purple-50 text-purple-700 ring-1 ring-purple-600/10' },
  red:    { dot: 'bg-red-500',     badge: 'bg-red-50 text-red-700 ring-1 ring-red-600/10' },
  gray:   { dot: 'bg-slate-400',   badge: 'bg-slate-50 text-slate-600 ring-1 ring-slate-500/10' },
  cyan:   { dot: 'bg-cyan-500',    badge: 'bg-cyan-50 text-cyan-700 ring-1 ring-cyan-600/10' },
  indigo: { dot: 'bg-indigo-500',  badge: 'bg-indigo-50 text-indigo-700 ring-1 ring-indigo-600/10' },
};

interface Props {
  label: string;
  variant: Variant;
  className?: string;
  size?: 'sm' | 'md';
  showDot?: boolean;
}

const StatusBadge: React.FC<Props> = ({ label, variant, className = '', size = 'md', showDot = true }) => {
  const s = styles[variant] ?? styles.gray;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium ${s.badge} ${
        size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-0.5 text-xs'
      } ${className}`}
    >
      {showDot && (
        <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      )}
      {label}
    </span>
  );
};

export default StatusBadge;
