import React from 'react';

interface Props {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: { value: number; positive: boolean };
  sparklineData?: number[];
  onClick?: () => void;
}

/* Tiny inline sparkline — no dependencies */
function Sparkline({ data, positive }: { data: number[]; positive?: boolean }) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const h = 32;
  const w = 80;
  const step = w / (data.length - 1);
  const points = data.map((v, i) => `${i * step},${h - ((v - min) / range) * h}`).join(' ');
  const fillPoints = `0,${h} ${points} ${w},${h}`;
  const color = positive === false ? '#ef4444' : '#6366f1';
  const fillColor = positive === false ? 'rgba(239,68,68,0.08)' : 'rgba(99,102,241,0.08)';

  return (
    <svg width={w} height={h} className="sparkline overflow-visible">
      <polygon points={fillPoints} fill={fillColor} />
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

const StatCard: React.FC<Props> = ({ title, value, subtitle, icon, trend, sparklineData, onClick }) => (
  <div
    className={`group relative overflow-hidden rounded-2xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-card)] transition-all duration-200 hover:shadow-[var(--shadow-md)] hover:border-slate-200 ${
      onClick ? 'cursor-pointer active:scale-[0.99]' : ''
    }`}
    onClick={onClick}
  >
    <div className="flex items-start justify-between">
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium uppercase tracking-wider text-slate-400">{title}</p>
        <p className="mt-1.5 text-2xl font-bold tracking-tight text-slate-900">{value}</p>
        <div className="mt-1.5 flex items-center gap-2">
          {trend && (
            <span
              className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[11px] font-semibold ${
                trend.positive
                  ? 'bg-emerald-50 text-emerald-600'
                  : 'bg-red-50 text-red-600'
              }`}
            >
              {trend.positive ? '↑' : '↓'} {Math.abs(trend.value)}%
            </span>
          )}
          {subtitle && <p className="text-[11px] text-slate-400 truncate">{subtitle}</p>}
        </div>
      </div>
      <div className="flex flex-col items-end gap-2">
        {icon && (
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-50 to-indigo-100/60 text-indigo-600 ring-1 ring-indigo-100 transition-colors group-hover:from-indigo-100 group-hover:to-indigo-50">
            {icon}
          </div>
        )}
        {sparklineData && sparklineData.length > 1 && (
          <Sparkline data={sparklineData} positive={trend?.positive} />
        )}
      </div>
    </div>
  </div>
);

export default StatCard;
