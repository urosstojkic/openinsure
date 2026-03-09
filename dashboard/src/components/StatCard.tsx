import React from 'react';

interface Props {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: { value: number; positive: boolean };
}

const StatCard: React.FC<Props> = ({ title, value, subtitle, icon, trend }) => (
  <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-sm font-medium text-slate-500">{title}</p>
        <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
        {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
        {trend && (
          <p className={`mt-1 text-xs font-medium ${trend.positive ? 'text-green-600' : 'text-red-600'}`}>
            {trend.positive ? '▲' : '▼'} {Math.abs(trend.value)}%
          </p>
        )}
      </div>
      {icon && (
        <div className="rounded-lg bg-blue-50 p-2.5 text-blue-600">{icon}</div>
      )}
    </div>
  </div>
);

export default StatCard;
