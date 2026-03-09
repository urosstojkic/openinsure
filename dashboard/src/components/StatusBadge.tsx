import React from 'react';

type Variant =
  | 'blue' | 'yellow' | 'orange' | 'green' | 'purple' | 'red' | 'gray'
  | 'cyan' | 'indigo';

const classes: Record<Variant, string> = {
  blue:   'bg-blue-50 text-blue-700 ring-1 ring-blue-600/10',
  yellow: 'bg-amber-50 text-amber-700 ring-1 ring-amber-600/10',
  orange: 'bg-orange-50 text-orange-700 ring-1 ring-orange-600/10',
  green:  'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/10',
  purple: 'bg-purple-50 text-purple-700 ring-1 ring-purple-600/10',
  red:    'bg-red-50 text-red-700 ring-1 ring-red-600/10',
  gray:   'bg-slate-50 text-slate-700 ring-1 ring-slate-600/10',
  cyan:   'bg-cyan-50 text-cyan-700 ring-1 ring-cyan-600/10',
  indigo: 'bg-indigo-50 text-indigo-700 ring-1 ring-indigo-600/10',
};

interface Props {
  label: string;
  variant: Variant;
  className?: string;
}

const StatusBadge: React.FC<Props> = ({ label, variant, className = '' }) => (
  <span
    className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${classes[variant]} ${className}`}
  >
    {label}
  </span>
);

export default StatusBadge;
