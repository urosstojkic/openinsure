import React from 'react';

type Variant =
  | 'blue' | 'yellow' | 'orange' | 'green' | 'purple' | 'red' | 'gray'
  | 'cyan' | 'indigo';

const classes: Record<Variant, string> = {
  blue:   'bg-blue-100 text-blue-800',
  yellow: 'bg-yellow-100 text-yellow-800',
  orange: 'bg-orange-100 text-orange-800',
  green:  'bg-green-100 text-green-800',
  purple: 'bg-purple-100 text-purple-800',
  red:    'bg-red-100 text-red-800',
  gray:   'bg-gray-100 text-gray-800',
  cyan:   'bg-cyan-100 text-cyan-800',
  indigo: 'bg-indigo-100 text-indigo-800',
};

interface Props {
  label: string;
  variant: Variant;
  className?: string;
}

const StatusBadge: React.FC<Props> = ({ label, variant, className = '' }) => (
  <span
    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${classes[variant]} ${className}`}
  >
    {label}
  </span>
);

export default StatusBadge;
