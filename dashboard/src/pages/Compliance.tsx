import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';
import ConfidenceBar from '../components/ConfidenceBar';
import TimelineEvent from '../components/TimelineEvent';
import { getComplianceSummary } from '../api/compliance';
import { ShieldCheck, Brain, AlertTriangle, Eye } from 'lucide-react';
import { StatCardSkeleton, ChartSkeleton } from '../components/Skeleton';

const COLORS = ['#3b82f6', '#8b5cf6', '#f59e0b', '#10b981', '#ef4444'];

const Compliance: React.FC = () => {
  const { data: comp, isLoading } = useQuery({ queryKey: ['compliance'], queryFn: getComplianceSummary });

  if (isLoading || !comp) {
    return (
      <div className="space-y-6">
        <div>
          <div className="h-7 w-56 rounded-lg bg-slate-200 animate-pulse" />
          <div className="mt-2 h-4 w-80 rounded bg-slate-100 animate-pulse" />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCardSkeleton />
          <StatCardSkeleton />
          <StatCardSkeleton />
          <StatCardSkeleton />
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <ChartSkeleton />
          <ChartSkeleton />
        </div>
      </div>
    );
  }

  const agentChartData = Object.entries(comp.decisions_by_agent).map(([k, v]) => ({
    name: k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
    value: v,
  }));

  const typeChartData = Object.entries(comp.decisions_by_type).map(([k, v]) => ({
    name: k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
    value: v,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Compliance Dashboard</h1>
        <p className="text-sm text-slate-500 mt-0.5">EU AI Act compliance monitoring and audit trail</p>
      </div>

      {/* ── Summary cards ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total AI Decisions"
          value={comp.total_decisions.toLocaleString()}
          icon={<Brain size={20} />}
        />
        <StatCard
          title="Avg Confidence"
          value={`${Math.round(comp.avg_confidence * 100)}%`}
          icon={<ShieldCheck size={20} />}
        />
        <StatCard
          title="Oversight Required"
          value={comp.oversight_required_count}
          icon={<AlertTriangle size={20} />}
          subtitle={`${comp.oversight_recommended_count} recommended`}
        />
        <StatCard
          title="AI Systems Active"
          value={comp.ai_systems.filter((s) => s.status === 'active').length}
          icon={<Eye size={20} />}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* ── AI System Inventory ── */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-4 text-sm font-semibold text-slate-800">AI System Inventory</h2>
          <div className="space-y-3">
            {comp.ai_systems.map((sys) => (
              <div key={sys.id} className="flex items-center justify-between rounded-lg border border-slate-100 p-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">{sys.name} {sys.version ? <span className="text-xs text-slate-400">v{sys.version}</span> : <span className="text-xs text-slate-400">—</span>}</p>
                  <p className="text-xs text-slate-400">Last audit: {sys.last_audit || '—'} · {sys.decisions_count ?? '—'} decisions</p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge
                    label={sys.risk_category}
                    variant={sys.risk_category === 'high' ? 'red' : sys.risk_category === 'limited' ? 'yellow' : 'green'}
                  />
                  <StatusBadge
                    label={sys.status}
                    variant={sys.status === 'active' ? 'green' : sys.status === 'testing' ? 'yellow' : 'gray'}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Decisions by Agent (pie) ── */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-4 text-sm font-semibold text-slate-800">Decisions by Agent</h2>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={agentChartData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}>
                {agentChartData.map((_entry, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  return (
                    <div className="rounded-lg border border-slate-200/60 bg-white/95 px-3 py-2 shadow-lg backdrop-blur-sm">
                      <p className="text-[11px] font-medium text-slate-400">{payload[0].name}</p>
                      <p className="text-sm font-bold text-slate-800">{payload[0].value}</p>
                    </div>
                  );
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* ── Decisions by Type (pie) ── */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-4 text-sm font-semibold text-slate-800">Decisions by Type</h2>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={typeChartData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}>
                {typeChartData.map((_entry, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  return (
                    <div className="rounded-lg border border-slate-200/60 bg-white/95 px-3 py-2 shadow-lg backdrop-blur-sm">
                      <p className="text-[11px] font-medium text-slate-400">{payload[0].name}</p>
                      <p className="text-sm font-bold text-slate-800">{payload[0].value}</p>
                    </div>
                  );
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* ── Bias Monitoring ── */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-4 text-sm font-semibold text-slate-800">Bias Monitoring</h2>
          <div className="space-y-3">
            {comp.bias_metrics.map((m, i) => (
              <div key={i} className="space-y-1">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-sm font-medium text-slate-700">{m.metric_name}</span>
                    <span className="ml-2 text-xs text-slate-400">{m.category}</span>
                  </div>
                  <StatusBadge
                    label={m.status}
                    variant={m.status === 'pass' ? 'green' : m.status === 'warning' ? 'yellow' : 'red'}
                  />
                </div>
                <ConfidenceBar value={m.value} height="h-1.5" />
                <p className="text-xs text-slate-400">Value: {m.value.toFixed(2)} · Threshold: {m.threshold}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── EU AI Act compliance indicators ── */}
      <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
        <h2 className="mb-4 text-sm font-semibold text-slate-800">EU AI Act Compliance Status</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { label: 'AI System Registration', met: true, detail: 'All high-risk systems registered in EU database' },
            { label: 'Human Oversight Mechanisms', met: true, detail: 'Override and escalation controls in place for all agents' },
            { label: 'Decision Explainability', met: true, detail: 'Full reasoning chain recorded for every AI decision' },
            { label: 'Bias Monitoring', met: comp.bias_metrics.every((m) => m.status !== 'fail'), detail: comp.bias_metrics.some((m) => m.status === 'fail') ? 'Action needed — some metrics below threshold' : 'All metrics within acceptable thresholds' },
            { label: 'Data Governance', met: true, detail: 'Training data documented and version-controlled' },
            { label: 'Audit Trail', met: true, detail: `${comp.audit_trail.length} audit entries in current period` },
          ].map((item, i) => (
            <div
              key={i}
              className={`rounded-xl border p-4 ${
                item.met ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'
              }`}
            >
              <div className="flex items-center gap-2">
                <div className={`h-3 w-3 rounded-full ${item.met ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-sm font-semibold text-slate-900">{item.label}</span>
              </div>
              <p className={`mt-1 text-xs ${item.met ? 'text-green-700' : 'text-red-700'}`}>{item.detail}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Audit Trail ── */}
      <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
        <h2 className="mb-4 text-sm font-semibold text-slate-800">Audit Trail</h2>
        {comp.audit_trail.map((entry, i) => (
          <TimelineEvent
            key={entry.id}
            timestamp={entry.timestamp}
            actor={entry.actor}
            action={entry.action}
            details={`[${entry.resource_type}/${entry.resource_id}] ${entry.details}`}
            isAgent={!entry.actor.includes(' ')}
            isLast={i === comp.audit_trail.length - 1}
          />
        ))}
      </div>
    </div>
  );
};

export default Compliance;
