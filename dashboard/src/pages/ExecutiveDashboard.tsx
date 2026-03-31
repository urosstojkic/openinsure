import React, { useState, useEffect } from 'react';
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

/* Relative time helper */
const timeAgo = (ts: number, now: number) => {
  const mins = Math.floor((now - ts) / 60_000);
  if (mins < 1) return 'just now';
  if (mins === 1) return '1 minute ago';
  if (mins < 60) return `${mins} minutes ago`;
  const hrs = Math.floor(mins / 60);
  return hrs === 1 ? '1 hour ago' : `${hrs} hours ago`;
};

/* KPI color-code ring helpers */
const lossRatioRing = (v: number) =>
  v > 0.7 ? 'ring-2 ring-red-400/70' : v > 0.6 ? 'ring-2 ring-amber-400/70' : 'ring-2 ring-emerald-400/70';
const combinedRatioRing = (v: number) =>
  v > 1.0 ? 'ring-2 ring-red-400/70' : v > 0.95 ? 'ring-2 ring-amber-400/70' : 'ring-2 ring-emerald-400/70';
const growthRateRing = (v: number) =>
  v > 0 ? 'ring-2 ring-emerald-400/70' : 'ring-2 ring-red-400/70';

/* ── SVG Pipeline Funnel ── */
const FUNNEL_COLORS = ['#8b5cf6', '#7c3aed', '#6d28d9', '#5b21b6', '#4c1d95'];

const PipelineFunnel: React.FC<{ data: Array<{ stage: string; count: number }> }> = ({ data }) => {
  if (!data?.length) return null;

  const stageH = 46;
  const gap = 3;
  const totalH = data.length * stageH + (data.length - 1) * gap;
  const svgW = 460;
  const maxW = svgW * 0.92;
  const minW = svgW * 0.26;

  return (
    <svg viewBox={`0 0 ${svgW} ${totalH}`} className="w-full" preserveAspectRatio="xMidYMid meet">
      {data.map((item, i) => {
        const t = data.length > 1 ? i / (data.length - 1) : 0;
        const tNext = data.length > 1 ? Math.min((i + 1) / (data.length - 1), 1) : 0;

        const topW = maxW - t * (maxW - minW);
        const botW = i === data.length - 1 ? topW * 0.82 : maxW - tNext * (maxW - minW);

        const y = i * (stageH + gap);
        const cx = svgW / 2;

        const x1 = cx - topW / 2;
        const x2 = cx + topW / 2;
        const x3 = cx + botW / 2;
        const x4 = cx - botW / 2;

        const color = FUNNEL_COLORS[i % FUNNEL_COLORS.length];

        return (
          <g key={i}>
            <path
              d={`M${x1},${y} L${x2},${y} L${x3},${y + stageH} L${x4},${y + stageH} Z`}
              fill={color}
              className="transition-opacity hover:opacity-80"
            />
            <text
              x={cx}
              y={y + stageH / 2 - 7}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="white"
              fontSize={11}
              fontWeight={600}
              opacity={0.95}
            >
              {item.stage}
            </text>
            <text
              x={cx}
              y={y + stageH / 2 + 9}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="white"
              fontSize={13}
              fontWeight={700}
            >
              {item.count.toLocaleString()}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

const ExecutiveDashboard: React.FC = () => {
  /* Tick for "last updated" relative time */
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);

  const { data, isLoading, dataUpdatedAt } = useQuery({ queryKey: ['executive'], queryFn: getExecutiveDashboard });

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
      {/* Header with live indicator */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Executive Dashboard</h1>
          <p className="mt-0.5 text-sm text-slate-500">Strategic overview — CEO / CUO view</p>
        </div>
        <div className="flex items-center gap-3">
          {dataUpdatedAt > 0 && (
            <span className="text-xs text-slate-400 tabular-nums">
              Last updated {timeAgo(dataUpdatedAt, now)}
            </span>
          )}
          <span className="flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 ring-1 ring-emerald-200/60">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            <span className="text-[11px] font-medium text-emerald-600">Live</span>
          </span>
        </div>
      </div>

      {/* ── Row 1: KPI Cards ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard title="Gross Written Premium" value={money(kpis.gwp)} icon={<DollarSign size={18} />} trend={{ value: Math.round(kpis.growth_rate * 100), positive: kpis.growth_rate > 0 }} subtitle="Year to date" sparklineData={[40, 42, 44, 43, 46, 48, 50]} />
        <StatCard title="Net Written Premium" value={money(kpis.nwp)} icon={<DollarSign size={18} />} subtitle="After reinsurance" sparklineData={[35, 37, 38, 36, 39, 41, 42]} />
        <div className={`rounded-xl ${lossRatioRing(kpis.loss_ratio)}`}>
          <StatCard title="Loss Ratio" value={pct(kpis.loss_ratio)} icon={<Percent size={18} />} subtitle="Target: <60%" trend={{ value: 3, positive: kpis.loss_ratio < 0.6 }} sparklineData={[62, 64, 61, 63, 65, 60, Math.round(kpis.loss_ratio * 100)]} />
        </div>
        <div className={`rounded-xl ${combinedRatioRing(kpis.combined_ratio)}`}>
          <StatCard title="Combined Ratio" value={pct(kpis.combined_ratio)} icon={<Activity size={18} />} subtitle="Target: <95%" trend={{ value: 2, positive: kpis.combined_ratio < 0.95 }} sparklineData={[96, 95, 97, 94, 93, 95, Math.round(kpis.combined_ratio * 100)]} />
        </div>
        <div className={`rounded-xl ${growthRateRing(kpis.growth_rate)}`}>
          <StatCard title="Growth Rate" value={pct(kpis.growth_rate)} icon={<TrendingUp size={18} />} trend={{ value: Math.round(kpis.growth_rate * 100), positive: kpis.growth_rate > 0 }} sparklineData={[8, 10, 9, 11, 12, 10, Math.round(kpis.growth_rate * 100)]} />
        </div>
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
        {/* Pipeline Funnel */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-1 text-sm font-semibold text-slate-800">Submission Pipeline</h2>
          <p className="mb-4 text-[11px] text-slate-400">Current funnel status</p>
          <div className="px-4">
            <PipelineFunnel data={pipeline} />
          </div>
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
