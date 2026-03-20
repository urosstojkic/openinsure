import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from 'recharts';
import {
  DollarSign, TrendingUp, Percent, Activity, Zap,
} from 'lucide-react';
import StatCard from '../components/StatCard';
import { getExecutiveDashboard } from '../api/workbench';

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const pct = (n: number) => `${Math.round(n * 100)}%`;

const ExecutiveDashboard: React.FC = () => {
  const { data, isLoading } = useQuery({ queryKey: ['executive'], queryFn: getExecutiveDashboard });

  if (isLoading || !data) {
    return <div className="flex h-64 items-center justify-center text-slate-400">Loading…</div>;
  }

  const { kpis, premium_trend, loss_ratio_by_lob, exposure_concentrations, pipeline, agent_impact } = data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Executive Dashboard</h1>
        <p className="text-sm text-slate-500">Strategic overview — CEO / CUO view</p>
      </div>

      {/* ── Row 1: KPI Cards ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard title="Gross Written Premium" value={money(kpis.gwp)} icon={<DollarSign size={20} />} trend={{ value: kpis.growth_rate * 100, positive: true }} />
        <StatCard title="Net Written Premium" value={money(kpis.nwp)} icon={<DollarSign size={20} />} />
        <StatCard title="Loss Ratio" value={pct(kpis.loss_ratio)} icon={<Percent size={20} />} subtitle="Target: <60%" />
        <StatCard title="Combined Ratio" value={pct(kpis.combined_ratio)} icon={<Activity size={20} />} subtitle="Target: <95%" />
        <StatCard title="Growth Rate" value={pct(kpis.growth_rate)} icon={<TrendingUp size={20} />} trend={{ value: kpis.growth_rate * 100, positive: true }} />
      </div>

      {/* ── Row 2: Charts ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Premium Trend */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">Premium Trend (12 Months)</h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={premium_trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: number) => `$${(v / 1_000_000).toFixed(1)}M`} />
              <Tooltip formatter={(v) => money(Number(v))} />
              <Line type="monotone" dataKey="premium" stroke="#3b82f6" strokeWidth={2} dot={{ fill: '#3b82f6', r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Loss Ratio by LOB */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">Loss Ratio by LOB</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={loss_ratio_by_lob}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="lob" tick={{ fontSize: 10 }} />
              <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} tickFormatter={(v: number) => pct(v)} />
              <Tooltip formatter={(v) => pct(Number(v))} />
              <Bar dataKey="loss_ratio" radius={[4, 4, 0, 0]}>
                {loss_ratio_by_lob.map((entry, i) => (
                  <Cell key={i} fill={entry.loss_ratio > 0.6 ? '#ef4444' : entry.loss_ratio > 0.5 ? '#f59e0b' : '#22c55e'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Exposure Concentrations */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">Top 5 Exposure Concentrations</h2>
          <div className="space-y-3">
            {exposure_concentrations.map((ec, i) => (
              <div key={i}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm text-slate-700">{ec.name}</span>
                  <span className="text-sm font-mono text-slate-900">{money(ec.exposure)}</span>
                </div>
                <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200">
                  <div
                    className="h-3 rounded-full bg-blue-500"
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
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">Submission Pipeline</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={pipeline} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis type="number" tick={{ fontSize: 10 }} />
              <YAxis dataKey="stage" type="category" tick={{ fontSize: 11 }} width={90} />
              <Tooltip />
              <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Agent Impact */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">AI Agent Impact</h2>
          <div className="grid grid-cols-1 gap-4">
            <div className="rounded-lg border border-green-200 bg-green-50 p-4">
              <div className="flex items-center gap-3">
                <Zap size={20} className="text-green-600" />
                <div>
                  <p className="text-sm text-green-800">Processing Time Reduction</p>
                  <p className="text-3xl font-bold text-green-900">{agent_impact.processing_time_reduction}%</p>
                  <p className="text-xs text-green-600">Average time from submission to quote</p>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
                <p className="text-xs text-blue-600">Auto-Bind Rate</p>
                <p className="text-2xl font-bold text-blue-900">{agent_impact.auto_bind_rate}%</p>
                <p className="text-xs text-blue-500">Straight-through processing</p>
              </div>
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
                <p className="text-xs text-amber-600">Escalation Rate</p>
                <p className="text-2xl font-bold text-amber-900">{agent_impact.escalation_rate}%</p>
                <p className="text-xs text-amber-500">Decisions needing human review</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ExecutiveDashboard;
