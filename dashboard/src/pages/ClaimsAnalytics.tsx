import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  AreaChart, Area, Cell,
} from 'recharts';
import { Activity, AlertTriangle, Shield, DollarSign } from 'lucide-react';
import StatCard from '../components/StatCard';
import { StatCardSkeleton, ChartSkeleton } from '../components/Skeleton';
import { getClaimsAnalytics } from '../api/analytics';

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const ChartTooltipContent = ({ active, payload, label, formatter }: {
  active?: boolean;
  payload?: Array<{ value: number; name?: string }>;
  label?: string;
  formatter?: (v: number) => string;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200/60 bg-white/95 px-3 py-2 shadow-lg backdrop-blur-sm">
      <p className="text-[11px] font-medium text-slate-400">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-sm font-bold text-slate-800">
          {p.name}: {formatter ? formatter(p.value) : typeof p.value === 'number' ? p.value.toLocaleString() : p.value}
        </p>
      ))}
    </div>
  );
};

const TYPE_COLORS = ['#6366f1', '#f59e0b', '#ef4444', '#10b981', '#8b5cf6', '#ec4899'];

const ClaimsAnalytics: React.FC = () => {
  const { data, isLoading } = useQuery({
    queryKey: ['claims-analytics'],
    queryFn: () => getClaimsAnalytics(12),
  });

  if (isLoading || !data) {
    return (
      <div className="space-y-6">
        <div>
          <div className="skeleton-text mb-2" style={{ width: '280px', height: '28px' }} />
          <div className="skeleton-text" style={{ width: '320px', height: '14px' }} />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => <StatCardSkeleton key={i} />)}
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <ChartSkeleton /><ChartSkeleton />
        </div>
      </div>
    );
  }

  const { frequency_severity, reserve_development, fraud_distribution, claims_by_type } = data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Claims Analytics</h1>
        <p className="mt-0.5 text-sm text-slate-500">Frequency, severity, and fraud analysis across the claims book</p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Total Claims" value={data.total_claims} icon={<AlertTriangle size={20} />} />
        <StatCard title="Open Claims" value={data.total_open} icon={<Activity size={20} />} />
        <StatCard title="Total Incurred" value={money(data.total_incurred)} icon={<DollarSign size={20} />} />
        <StatCard
          title="Avg Fraud Score"
          value={data.avg_fraud_score.toFixed(2)}
          subtitle="0 = clean, 1 = suspicious"
          icon={<Shield size={20} />}
        />
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Frequency & Severity Trend */}
        <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-[var(--shadow-card)]">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Frequency & Severity Trend</h3>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={[...frequency_severity].reverse()}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="period" tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <YAxis yAxisId="left" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: '#94a3b8' }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
              <Tooltip content={<ChartTooltipContent />} />
              <Area yAxisId="left" type="monotone" dataKey="claim_count" stroke="#6366f1" fill="rgba(99,102,241,0.1)" strokeWidth={2} name="Claims" />
              <Area yAxisId="right" type="monotone" dataKey="avg_severity" stroke="#f59e0b" fill="rgba(245,158,11,0.1)" strokeWidth={2} name="Avg Severity" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Reserve Development */}
        <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-[var(--shadow-card)]">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Reserve Development</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={[...reserve_development].reverse()}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="period" tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
              <Tooltip content={<ChartTooltipContent formatter={(v) => money(v)} />} />
              <Bar dataKey="initial_reserve" fill="#c7d2fe" radius={[4, 4, 0, 0]} name="Initial" />
              <Bar dataKey="current_reserve" fill="#6366f1" radius={[4, 4, 0, 0]} name="Current" />
              <Bar dataKey="paid_to_date" fill="#10b981" radius={[4, 4, 0, 0]} name="Paid" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Fraud Score Distribution */}
        <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-[var(--shadow-card)]">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Fraud Score Distribution</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={fraud_distribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="range_start"
                tick={{ fontSize: 10, fill: '#94a3b8' }}
                tickFormatter={(v) => `${(v * 10).toFixed(0)}`}
              />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <Tooltip
                content={<ChartTooltipContent formatter={(v) => `${v} claims`} />}
                labelFormatter={(v) => `Score ${v}–${(parseFloat(String(v)) + 0.1).toFixed(1)}`}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {fraud_distribution.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.range_start >= 0.7 ? '#ef4444' : entry.range_start >= 0.4 ? '#f59e0b' : '#6366f1'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Severity by Type */}
        <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-[var(--shadow-card)]">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Severity by Claim Type</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={claims_by_type} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
              <YAxis
                dataKey="claim_type"
                type="category"
                tick={{ fontSize: 10, fill: '#94a3b8' }}
                width={120}
                tickFormatter={(v) => v.replace(/_/g, ' ')}
              />
              <Tooltip content={<ChartTooltipContent formatter={(v) => money(v)} />} />
              <Bar dataKey="avg_severity" radius={[0, 6, 6, 0]} name="Avg Severity">
                {claims_by_type.map((_entry, index) => (
                  <Cell key={`cell-${index}`} fill={TYPE_COLORS[index % TYPE_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default ClaimsAnalytics;
