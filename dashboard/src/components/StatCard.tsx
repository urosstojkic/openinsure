import React from 'react';

interface Props {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: { value: number; positive: boolean };
}

const StatCard: React.FC<Props> = ({ title, value, subtitle, icon, trend }) => (
  <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-sm hover:shadow-md transition-shadow">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-sm font-medium text-slate-500">{title}</p>
        <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
        {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
        {trend && (
          <p className={`mt-1 text-xs font-medium ${trend.positive ? 'text-emerald-600' : 'text-red-600'}`}>
            {trend.positive ? '▲' : '▼'} {Math.abs(trend.value)}%
          </p>
        )}
      </div>
      {icon && (
        <div className="rounded-xl bg-gradient-to-br from-indigo-50 to-indigo-100/50 p-2.5 text-indigo-600">{icon}</div>
      )}
    </div>
  </div>
);

export default StatCard;
