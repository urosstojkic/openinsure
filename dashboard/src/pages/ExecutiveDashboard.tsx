import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
  Area, AreaChart,
} from 'recharts';
import {
  DollarSign, TrendingUp, Percent, Activity, Zap, Sparkles,
} from 'lucide-react';
import StatCard from '../components/StatCard';
import { StatCardSkeleton, ChartSkeleton } from '../components/Skeleton';
import { getExecutiveDashboard } from '../api/workbench';
import { getAIInsights, type AIInsightsData } from '../api/analytics';

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const pct = (n: number) => `${Math.round(n * 100)}%`;

/* Custom tooltip */
const ChartTooltipContent = ({ active, payload, label, formatter }: { active?: boolean; payload?: Array<{ value: number; name?: string }>; label?: string; formatter?: (v: number) => string }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200/60 bg-white/95 px-3 py-2 shadow-lg backdrop-blur-sm">
      <p className="text-[11px] font-medium text-slate-400">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-sm font-bold text-slate-800">
          {formatter ? formatter(p.value) : p.value}
        </p>
      ))}
    </div>
  );
};

const ExecutiveDashboard: React.FC = () => {
  const { data, isLoading } = useQuery({ queryKey: ['executive'], queryFn: getExecutiveDashboard });

  const { data: aiInsights } = useQuery<AIInsightsData>({
    queryKey: ['ai-insights'],
    queryFn: () => getAIInsights(),
  });

  if (isLoading || !data) {
    return (
      <div className="space-y-6">
        <div>
          <div className="skeleton-text mb-2" style={{ width: '240px', height: '28px' }} />
          <div className="skeleton-text" style={{ width: '280px', height: '14px' }} />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {[1,2,3,4,5].map(i => <StatCardSkeleton key={i} />)}
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <ChartSkeleton /><ChartSkeleton /><ChartSkeleton />
        </div>
      </div>
    );
  }

  const { kpis, premium_trend, loss_ratio_by_lob, exposure_concentrations, pipeline, agent_impact } = data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Executive Dashboard</h1>
        <p className="mt-0.5 text-sm text-slate-500">Strategic overview — CEO / CUO view</p>
      </div>

      {/* ── Row 1: KPI Cards ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard title="Gross Written Premium" value={money(kpis.gwp)} icon={<DollarSign size={18} />} trend={{ value: Math.round(kpis.growth_rate * 100), positive: kpis.growth_rate > 0 }} subtitle="Year to date" sparklineData={[40, 42, 44, 43, 46, 48, 50]} />
        <StatCard title="Net Written Premium" value={money(kpis.nwp)} icon={<DollarSign size={18} />} subtitle="After reinsurance" sparklineData={[35, 37, 38, 36, 39, 41, 42]} />
        <StatCard title="Loss Ratio" value={pct(kpis.loss_ratio)} icon={<Percent size={18} />} subtitle="Target: <60%" trend={{ value: 3, positive: kpis.loss_ratio < 0.6 }} />
        <StatCard title="Combined Ratio" value={pct(kpis.combined_ratio)} icon={<Activity size={18} />} subtitle="Target: <95%" trend={{ value: 2, positive: kpis.combined_ratio < 0.95 }} />
        <StatCard title="Growth Rate" value={pct(kpis.growth_rate)} icon={<TrendingUp size={18} />} trend={{ value: Math.round(kpis.growth_rate * 100), positive: kpis.growth_rate > 0 }} />
      </div>

      {/* ── Row 2: Charts ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Premium Trend */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-1 text-sm font-semibold text-slate-800">Premium Trend</h2>
          <p className="mb-4 text-[11px] text-slate-400">12-month rolling view</p>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={premium_trend}>
              <defs>
                <linearGradient id="premiumGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366f1" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} tickFormatter={(v: number) => `$${(v / 1_000_000).toFixed(1)}M`} />
              <Tooltip content={<ChartTooltipContent formatter={(v) => money(v)} />} />
              <Area type="monotone" dataKey="premium" stroke="#6366f1" strokeWidth={2} fill="url(#premiumGradient)" dot={{ fill: '#6366f1', r: 3, strokeWidth: 0 }} activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Loss Ratio by LOB */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-1 text-sm font-semibold text-slate-800">Loss Ratio by LOB</h2>
          <p className="mb-4 text-[11px] text-slate-400">Performance by line of business</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={loss_ratio_by_lob} barCategoryGap="20%">
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="lob" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 1]} tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} tickFormatter={(v: number) => pct(v)} />
              <Tooltip content={<ChartTooltipContent formatter={(v) => pct(v)} />} />
              <Bar dataKey="loss_ratio" radius={[6, 6, 0, 0]} maxBarSize={40}>
                {loss_ratio_by_lob.map((entry, i) => (
                  <Cell key={i} fill={entry.loss_ratio > 0.6 ? '#ef4444' : entry.loss_ratio > 0.5 ? '#f59e0b' : '#10b981'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Exposure Concentrations */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-1 text-sm font-semibold text-slate-800">Top 5 Exposures</h2>
          <p className="mb-4 text-[11px] text-slate-400">Concentration risk monitoring</p>
          <div className="space-y-3.5">
            {exposure_concentrations.map((ec, i) => (
              <div key={i}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[13px] font-medium text-slate-700">{ec.name}</span>
                  <span className="text-[13px] font-semibold tabular-nums text-slate-800">{money(ec.exposure)}</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-2 rounded-full bg-gradient-to-r from-indigo-500 to-indigo-400 transition-all duration-500"
                    style={{ width: `${(ec.exposure / exposure_concentrations[0].exposure) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Row 3: Pipeline + Agent Impact ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Pipeline */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-1 text-sm font-semibold text-slate-800">Submission Pipeline</h2>
          <p className="mb-4 text-[11px] text-slate-400">Current funnel status</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={pipeline} layout="vertical" barCategoryGap="20%">
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis dataKey="stage" type="category" tick={{ fontSize: 11, fill: '#64748b' }} width={90} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltipContent />} />
              <defs>
                <linearGradient id="pipelineGradient" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#8b5cf6" />
                  <stop offset="100%" stopColor="#a78bfa" />
                </linearGradient>
              </defs>
              <Bar dataKey="count" fill="url(#pipelineGradient)" radius={[0, 6, 6, 0]} maxBarSize={28} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Agent Impact */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-1 text-sm font-semibold text-slate-800">AI Agent Impact</h2>
          <p className="mb-4 text-[11px] text-slate-400">Automation performance metrics</p>
          <div className="grid grid-cols-1 gap-3">
            <div className="rounded-xl border border-emerald-200/60 bg-gradient-to-r from-emerald-50 to-emerald-50/30 p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10">
                  <Zap size={18} className="text-emerald-600" />
                </div>
                <div>
                  <p className="text-xs font-medium text-emerald-600">Processing Time Reduction</p>
                  <p className="text-2xl font-bold tracking-tight text-emerald-900">{agent_impact.processing_time_reduction}%</p>
                  <p className="text-[11px] text-emerald-500">Avg time from submission to quote</p>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-blue-200/60 bg-gradient-to-br from-blue-50 to-blue-50/30 p-4">
                <p className="text-[11px] font-medium text-blue-500">Auto-Bind Rate</p>
                <p className="text-2xl font-bold tracking-tight text-blue-900">{agent_impact.auto_bind_rate}%</p>
                <p className="text-[11px] text-blue-400">Straight-through processing</p>
              </div>
              <div className="rounded-xl border border-amber-200/60 bg-gradient-to-br from-amber-50 to-amber-50/30 p-4">
                <p className="text-[11px] font-medium text-amber-500">Escalation Rate</p>
                <p className="text-2xl font-bold tracking-tight text-amber-900">{agent_impact.escalation_rate}%</p>
                <p className="text-[11px] text-amber-400">Needing human review</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* AI Insights (#83) */}
      {aiInsights && (
        <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-[var(--shadow-card)]">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles size={18} className="text-indigo-500" />
            <h3 className="text-sm font-semibold text-slate-700">AI Portfolio Insights</h3>
            <span className="ml-auto text-[10px] text-slate-400">
              {aiInsights.source === 'foundry' ? '🤖 Foundry' : '📊 System'} · {new Date(aiInsights.generated_at).toLocaleDateString()}
            </span>
          </div>
          {aiInsights.executive_summary && (
            <p className="text-sm text-slate-600 leading-relaxed mb-4">{aiInsights.executive_summary}</p>
          )}
          <div className="space-y-3">
            {aiInsights.insights.map((insight, i) => (
              <div key={i} className="rounded-xl border border-slate-200/60 bg-slate-50/30 p-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${
                    insight.severity === 'critical' ? 'bg-red-100 text-red-700' :
                    insight.severity === 'warning' ? 'bg-amber-100 text-amber-700' :
                    'bg-blue-100 text-blue-700'
                  }`}>
                    {insight.category}
                  </span>
                  <span className="text-sm font-semibold text-slate-800">{insight.title}</span>
                </div>
                <p className="text-xs text-slate-500 leading-relaxed">{insight.summary}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ExecutiveDashboard;
