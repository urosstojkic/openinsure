import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  AreaChart, Area, Cell,
} from 'recharts';
import { TrendingUp, Target, Brain } from 'lucide-react';
import StatCard from '../components/StatCard';
import { StatCardSkeleton, ChartSkeleton } from '../components/Skeleton';
import { getUWAnalytics } from '../api/analytics';

const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

const ChartTooltipContent = ({ active, payload, label, formatter }: {
  active?: boolean;
  payload?: Array<{ value: number; name?: string; dataKey?: string }>;
  label?: string;
  formatter?: (v: number) => string;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200/60 bg-white/95 px-3 py-2 shadow-lg backdrop-blur-sm">
      <p className="text-[11px] font-medium text-slate-400">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-sm font-bold text-slate-800">
          {p.name}: {formatter ? formatter(p.value) : p.value}
        </p>
      ))}
    </div>
  );
};

const FUNNEL_COLORS = ['#6366f1', '#818cf8', '#a5b4fc', '#c7d2fe'];

const UWAnalytics: React.FC = () => {
  const { data, isLoading } = useQuery({
    queryKey: ['uw-analytics'],
    queryFn: () => getUWAnalytics(12),
  });

  if (isLoading || !data) {
    return (
      <div className="space-y-6">
        <div>
          <div className="skeleton-text mb-2" style={{ width: '300px', height: '28px' }} />
          <div className="skeleton-text" style={{ width: '350px', height: '14px' }} />
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

  const { conversion_funnel, hit_ratio, processing_time, agent_vs_human } = data;
  const hitRatioOverall = data.total_quoted / Math.max(data.total_submissions, 1);
  const bindRate = data.total_bound / Math.max(data.total_submissions, 1);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Underwriting Analytics</h1>
        <p className="mt-0.5 text-sm text-slate-500">Performance metrics across the submission pipeline</p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Total Submissions" value={data.total_submissions} icon={<TrendingUp size={20} />} />
        <StatCard title="Hit Ratio" value={pct(hitRatioOverall)} subtitle="Quotes / Submissions" icon={<Target size={20} />} />
        <StatCard title="Bind Rate" value={pct(bindRate)} subtitle="Bound / Submissions" icon={<Target size={20} />} />
        <StatCard
          title="Agent Accuracy"
          value={pct(agent_vs_human.agent_accuracy)}
          subtitle={`${agent_vs_human.human_overrides} overrides`}
          icon={<Brain size={20} />}
        />
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Conversion Funnel */}
        <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-[var(--shadow-card)]">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Conversion Funnel</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={conversion_funnel} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis dataKey="stage" type="category" tick={{ fontSize: 11, fill: '#94a3b8' }} width={80} />
              <Tooltip content={<ChartTooltipContent />} />
              <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                {conversion_funnel.map((_entry, index) => (
                  <Cell key={`cell-${index}`} fill={FUNNEL_COLORS[index % FUNNEL_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Hit Ratio Trend */}
        <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-[var(--shadow-card)]">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Hit Ratio Trend</h3>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={[...hit_ratio].reverse()}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="period" tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
              <Tooltip content={<ChartTooltipContent formatter={(v) => pct(v)} />} />
              <Area type="monotone" dataKey="hit_ratio" stroke="#6366f1" fill="rgba(99,102,241,0.1)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Processing Time */}
        <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-[var(--shadow-card)]">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Processing Time (hours)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={processing_time}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="stage" tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <Tooltip content={<ChartTooltipContent formatter={(v) => `${v.toFixed(1)}h`} />} />
              <Bar dataKey="avg_hours" fill="#6366f1" radius={[6, 6, 0, 0]} name="Average" />
              <Bar dataKey="p90_hours" fill="#c7d2fe" radius={[6, 6, 0, 0]} name="P90" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Agent vs Human */}
        <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-[var(--shadow-card)]">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Agent vs Human Decisions</h3>
          <div className="space-y-4 mt-6">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-500">Total Decisions</span>
              <span className="text-lg font-bold text-slate-900">{agent_vs_human.total_decisions}</span>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-slate-500">Agent Decisions</span>
                <span className="text-sm font-semibold text-indigo-600">{agent_vs_human.agent_decisions}</span>
              </div>
              <div className="h-2 rounded-full bg-slate-100">
                <div
                  className="h-2 rounded-full bg-indigo-500"
                  style={{ width: `${((agent_vs_human.agent_decisions / Math.max(agent_vs_human.total_decisions, 1)) * 100).toFixed(0)}%` }}
                />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-slate-500">Human Overrides</span>
                <span className="text-sm font-semibold text-amber-600">{agent_vs_human.human_overrides}</span>
              </div>
              <div className="h-2 rounded-full bg-slate-100">
                <div
                  className="h-2 rounded-full bg-amber-500"
                  style={{ width: `${(agent_vs_human.override_rate * 100).toFixed(0)}%` }}
                />
              </div>
            </div>
            <div className="flex items-center justify-between pt-2 border-t border-slate-100">
              <span className="text-sm text-slate-500">Agent Accuracy</span>
              <span className="text-lg font-bold text-emerald-600">{pct(agent_vs_human.agent_accuracy)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UWAnalytics;
